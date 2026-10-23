"""Entrena y evalúa el sistema de riego basado en árboles de decisión.

Uso:
    python entrenar_modelo.py                     # usa soil_moisture_data.csv
    python entrenar_modelo.py --csv datos.csv     # otro dataset
    python entrenar_modelo.py --min-rows 10       # menos filas para entrenar
    python entrenar_modelo.py --require-window-ok # falla si la ventana no se aprende

Genera:
    decision_tree_model.pkl   -> modelo (lo usan app.py y el sensor)
    model_metadata.json       -> features, orden de columnas y versión de sklearn

Por qué DOS árboles y no uno:
    La decisión final es "planteta tiene sed Y es una hora segura". Esa conjunción
    no es aprendible con un árbol porque (1) con un target mayoritariamente "sí"
    predecir siempre "sí" ya maximiza la exactitud, y (2) el umbral de humedad
    cambia según la hora (dentro de 11-16h sólo se riega si es emergencia).
    Por eso se entrena:
        Thirsty   <- Plant_Type + Moisture_Percentage
        Can_Water <- Hour (+ humedad y tipo, para el riego de emergencia)
    y la decisión final se compone en tiempo de ejecución: Regar = Thirsty AND Can_Water.
"""

import argparse
import json
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import accuracy_score, f1_score
from sklearn.tree import DecisionTreeClassifier, export_text

import etiquetas

CSV_FILE = "soil_moisture_data.csv"
MODEL_FILE = "decision_tree_model.pkl"
METADATA_FILE = "model_metadata.json"

DEPTH_CANDIDATES = [2, 3, 4, 5, 6, 8]
MIN_SAMPLES_LEAF = 2

# Cada target usa sólo las features que pueden explicarlo. Meter todas en ambos
# es lo que hace que el árbol elija el atajo (p.ej. predecir con la hora lo que
# debería depender de la humedad).
TARGET_FEATURES = {
    etiquetas.THIRSTY: ["Plant_Type", "Moisture_Percentage"],
    etiquetas.CAN_WATER: ["Plant_Type", "Moisture_Percentage", "Hour"],
}


def load_dataset(csv_path):
    if not os.path.exists(csv_path):
        sys.exit(f"[ERROR] No existe '{csv_path}'. Copia el CSV del sensor o pasa --csv.")
    data = pd.read_csv(csv_path)
    required = {"Date", "Time", "Plant_Type", "Moisture_Percentage"}
    missing = required - set(data.columns)
    if missing:
        sys.exit(f"[ERROR] Al CSV le faltan columnas: {sorted(missing)}")

    data["Date"] = pd.to_datetime(data["Date"])
    # Hora con decimales: 18:30 -> 18.5. Un entero pierde el 18:30 y el modelo
    # nunca podrá aprender el límite exacto de 16:00 si sólo ve horas enteras.
    t = pd.to_datetime(data["Time"].astype(str).str.strip(), format="%H:%M:%S", errors="coerce")
    data["Hour"] = t.dt.hour + t.dt.minute / 60.0
    data["Plant_Type"] = data["Plant_Type"].map(etiquetas.normalize_plant_type)

    if "Temp_C" in data.columns:
        data["Temp_C"] = pd.to_numeric(data["Temp_C"], errors="coerce")

    before = len(data)
    data = data.dropna(subset=["Moisture_Percentage", "Hour"]).reset_index(drop=True)
    if len(data) != before:
        print(f"[WARN] Se descartaron {before - len(data)} filas sin humedad u hora válidas.")

    # Sobre las filas con hora válida, decidimos qué etiqueta usar.
    data["Rule_Label"] = [
        etiquetas.ground_truth_label(h, m, p)
        for h, m, p in zip(data["Hour"], data["Moisture_Percentage"], data["Plant_Type"])
    ]
    data["Thirsty"] = [etiquetas.thirsty_label(m, p) for m, p in zip(data["Moisture_Percentage"], data["Plant_Type"])]
    data["Can_Water"] = [
        etiquetas.can_water_label(h, m, p)
        for h, m, p in zip(data["Hour"], data["Moisture_Percentage"], data["Plant_Type"])
    ]

    if "Water_Needed" in data.columns:
        old = pd.to_numeric(data["Water_Needed"], errors="coerce")
        diff = int((old != data["Rule_Label"]).sum())
        if diff > 0:
            print(
                f"[WARN] {diff}/{len(data)} filas del CSV tienen una etiqueta distinta a la regla "
                f"actual (regla vieja: sólo humedad, sin hora).\n"
                f"       No se descartan: las etiquetas del CSV se IGNORAN y el modelo se entrena "
                f"con la regla de etiquetas.py."
            )
    data["Water_Needed"] = data["Rule_Label"]

    return data


def build_features(data):
    """Matriz numérica de features. El CSV guarda Plant_Type como texto ("Hierba")."""
    frame = pd.DataFrame({
        "Plant_Type": data["Plant_Type"].map(etiquetas.normalize_plant_type).astype(float),
        "Moisture_Percentage": pd.to_numeric(data["Moisture_Percentage"], errors="coerce"),
        "Hour": pd.to_numeric(data["Hour"], errors="coerce"),
    })
    bad = int(frame.isna().any(axis=1).sum())
    if bad:
        print(f"[WARN] {bad} filas con features no numéricas; se descartan.")
        keep = ~frame.isna().any(axis=1)
        data = data.loc[keep].reset_index(drop=True)
        frame = frame.loc[keep].reset_index(drop=True)
    return frame, data


def summarize(data):
    print("\n=== DATASET ===")
    print(f"Filas útiles       : {len(data)}")
    print(f"Rango de fechas    : {data['Date'].min().date()} -> {data['Date'].max().date()}")
    counts = data["Plant_Type"].map(etiquetas.PLANT_TYPE_MAP).value_counts()
    print(f"Plantas            : {dict(counts)}")
    print(f"Humedad            : {data['Moisture_Percentage'].min():.2f}% .. {data['Moisture_Percentage'].max():.2f}%")
    print("\nPor qué el target 'Regar' solo no se puede aprender con un árbol:")
    print(f"  Regar=1 en {int(data['Water_Needed'].sum())}/{len(data)} muestras "
          f"({data['Water_Needed'].mean():.0%}) -> la clase mayoritaria ya 'acierta' ese porcentaje.")
    ct = pd.crosstab(data["Can_Water"], data["Thirsty"])
    print("  Crosstab Can_Water (filas) x Thirsty (columnas):")
    print(ct.to_string())


def holdout(n, test_frac=0.25):
    """Corte cronológico: el último 25% (en el tiempo) es el conjunto de prueba."""
    n_train = n - max(1, int(round(n * test_frac)))
    return n_train if n_train > 1 else None


def train_target(name, X, y, n_train):
    """Entrena un árbol para un target y elige la profundidad más simple que empata."""
    print(f"\n--- Target {name} ({int(y.sum())} positivos / {len(y)}) ---")
    print("depth | train acc | test acc | hojas")
    results = {}
    for depth in DEPTH_CANDIDATES:
        clf = DecisionTreeClassifier(
            max_depth=depth, criterion="entropy", min_samples_leaf=MIN_SAMPLES_LEAF, random_state=42
        )
        if n_train:
            clf.fit(X[:n_train], y[:n_train])
            train_acc = accuracy_score(y[:n_train], clf.predict(X[:n_train]))
            test_acc = accuracy_score(y[n_train:], clf.predict(X[n_train:]))
        else:
            clf.fit(X, y)
            train_acc = test_acc = accuracy_score(y, clf.predict(X))
        leaves = clf.get_n_leaves()
        results[depth] = test_acc
        print(f"{depth:5d} | {train_acc:9.2%} | {test_acc:8.2%} | {leaves:5d}")

    best_acc = max(results.values())
    depth = min(d for d, acc in results.items() if acc >= best_acc - 1e-9)
    clf = DecisionTreeClassifier(
        max_depth=depth, criterion="entropy", min_samples_leaf=MIN_SAMPLES_LEAF, random_state=42
    )
    clf.fit(X, y)
    print(f"Profundidad elegida: {depth} (test acc {best_acc:.2%})")
    return clf


def compose_predict(clf_thirsty, clf_can, X, names):
    """Regar = Thirsty AND Can_Water, usando la vista de features de cada modelo."""
    thirsty = clf_thirsty.predict(X[names[etiquetas.THIRSTY]].values)
    can = clf_can.predict(X[names[etiquetas.CAN_WATER]].values)
    return (thirsty.astype(int) & can.astype(int))


def coverage_check(models, names, data):
    """Verifica que el sistema compuesto distinga los escenarios que pediste."""
    print("\n=== COBERTURA: DECISIÓN = Thirsty AND Can_Water ===")
    hours = [3, 9, 11, 13, 16, 19]
    print(f"{'planta':>9} {'humedad':>8} | " + " ".join(f"{h:>4}h" for h in hours))
    ok = True
    rows = []
    for ptype in sorted(data["Plant_Type"].unique()):
        min_thr, _ = etiquetas.thresholds_for(ptype)
        for moisture in [min_thr - 20, min_thr - 5, min_thr + 10, 90]:
            m = max(0.0, min(100.0, moisture))
            decisions = []
            for h in hours:
                X = pd.DataFrame([{"Plant_Type": ptype, "Moisture_Percentage": m, "Hour": h}])
                decisions.append(int(compose_predict(models[etiquetas.THIRSTY],
                                                    models[etiquetas.CAN_WATER], X, names)[0]))
            rows.append((ptype, m, decisions))
            print(f"{etiquetas.PLANT_TYPE_MAP[ptype]:>9} {m:7.1f}% | " + " ".join(f"{d:>5}" for d in decisions))

    # Comprobaciones de negocio:
    #  - 11h y 13h: nunca regar salvo humedad por debajo del umbral de emergencia.
    #  - 3h, 9h y 19h: regar si la humedad está por debajo del mínimo de la planta.
    #  - 16h en adelante ya es hora válida.
    predictions = {3: 0, 9: 1, 11: 2, 13: 3, 16: 4, 19: 5}
    for ptype, m, decisions in rows:
        if decisions[2] != 0 or decisions[3] != 0:
            emergency = etiquetas.is_critical(m, ptype)
            if not emergency:
                ok = False
        if m < etiquetas.thresholds_for(ptype)[0]:
            for idx in (predictions[3], predictions[9], predictions[19]):
                if decisions[idx] != 1:
                    ok = False
    print("\n0 = no regar, 1 = regar.")
    print("RESULTADO:", "OK: respeta la ventana 11:00-16:00 y riega por la mañana/tarde." if ok else
          "FALLA: revisa el dataset y las reglas (faltan muestras en alguna zona).")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Entrena el sistema de decisión de riego")
    parser.add_argument("--csv", default=CSV_FILE, help=f"CSV de entrenamiento (por defecto {CSV_FILE})")
    parser.add_argument("--min-rows", type=int, default=20, help="Mínimo de filas para entrenar")
    parser.add_argument("--save", default=MODEL_FILE, help=f"Archivo del modelo (por defecto {MODEL_FILE})")
    parser.add_argument("--require-window-ok", action="store_true",
                        help="Sale con código 1 si la ventana 11:00-16:00 no se respeta")
    args = parser.parse_args()

    print(f"scikit-learn {sklearn.__version__} | pandas {pd.__version__} | numpy {np.__version__}")
    data = load_dataset(args.csv)
    frame, data = build_features(data)
    summarize(data)

    if len(data) < args.min_rows:
        sys.exit(f"\n[ERROR] Solo hay {len(data)} filas de entrenamiento (se requieren {args.min_rows}).\n"
                 f"        Deja correr el sensor unos días más o baja --min-rows.")

    n_train = holdout(len(data)) if len(data) >= 8 else None
    models, names, depths = {}, {}, {}
    for target in etiquetas.TARGETS:
        cols = TARGET_FEATURES[target]
        y = data[target].astype(int).values
        if len(np.unique(y)) < 2:
            print(f"\n[WARN] {target} tiene una sola clase en el dataset: el árbol será trivial.")
        models[target] = train_target(target, frame[cols].values, y, n_train)
        names[target] = cols
        depths[target] = int(models[target].get_depth())

    print("\n=== REGLAS APRENDIDAS ===")
    for target in etiquetas.TARGETS:
        print(f"\n[{target}]  features={names[target]}")
        print(export_text(models[target], feature_names=names[target]))

    predicted = compose_predict(models[etiquetas.THIRSTY], models[etiquetas.CAN_WATER], frame, names)
    truth = data["Water_Needed"].astype(int).values
    print(f"\n=== SISTEMA COMPLETO (Regar = Thirsty AND Can_Water) ===")
    print(f"Accuracy vs regla de negocio : {accuracy_score(truth, predicted):.2%}")
    print(f"F1 (clase Regar)             : {f1_score(truth, predicted, zero_division=0):.3f}")
    print(f"Prevalencia real vs predicha : {truth.mean():.0%} vs {predicted.mean():.0%}")
    ok = coverage_check(models, names, data)

    joblib.dump({
        "models": models,
        "features": names,
        "targets": etiquetas.TARGETS,
        "source_csv": args.csv,
    }, args.save)

    metadata = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "n_rows": int(len(data)),
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "features": {t: names[t] for t in etiquetas.TARGETS},
        "max_depth": depths,
        "decision_rule": "Regar = Thirsty AND Can_Water (composición en runtime)",
        "labels_source": "etiquetas.py (humedad/tipo + ventana horaria)",
        "no_water_window": [etiquetas.NO_WATER_START_HOUR, etiquetas.NO_WATER_END_HOUR],
        "plant_thresholds": {etiquetas.PLANT_TYPE_MAP[k]: list(v)
                             for k, v in etiquetas.WATERING_THRESHOLDS.items()},
        "system_accuracy": round(float(accuracy_score(truth, predicted)), 4),
        "water_window_ok": bool(ok),
    }
    with open(METADATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, ensure_ascii=False)
    print(f"\nModelo guardado en '{args.save}' | metadata en '{METADATA_FILE}'")

    if args.require_window_ok and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
