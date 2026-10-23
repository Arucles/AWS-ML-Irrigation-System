"""Carga del modelo entrenado y predicción, compartido por app.py, el sensor y post.py.

El modelo guardado es un dict:
    {"models": {"Thirsty": arbol, "Can_Water": arbol}, "features": {...}, ...}

La decisión final se COMPONE en tiempo de ejecución (no se aprende):
    Regar = Thirsty AND Can_Water
"""

import os
import sys

import joblib
import pandas as pd

import etiquetas

MODEL_FILE = "decision_tree_model.pkl"
_REQUIRED_KEYS = ("models", "features")


def load_model(path=MODEL_FILE):
    """Carga el modelo y avisa si el .pkl es del formato viejo."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe '{path}'. Ejecuta: python entrenar_modelo.py")
    bundle = joblib.load(path)
    if not (isinstance(bundle, dict) and all(k in bundle for k in _REQUIRED_KEYS)):
        raise RuntimeError(
            f"'{path}' fue entrenado con el formato antiguo (un único árbol). "
            f"Vuelve a entrenar: python entrenar_modelo.py"
        )
    return bundle


def decide(bundle, moisture_percentage, hour, plant_type=etiquetas.DEFAULT_PLANT_TYPE):
    """Devuelve un dict con la decisión y el detalle de cada modelo.

    moisture_percentage : humedad 0-100
    hour                : hora local, admite 14.5 (14:30) o "14:30"
    plant_type          : código 0-3 o nombre ("Hierba")
    """
    moisture = float(moisture_percentage)
    if not 0.0 <= moisture <= 100.0:
        raise ValueError(f"Moisture_Percentage debe estar entre 0 y 100, se recibió {moisture!r}")
    hour = etiquetas.normalize_hour(hour)
    ptype = etiquetas.normalize_plant_type(plant_type)

    row = pd.DataFrame([{
        "Plant_Type": float(ptype),
        "Moisture_Percentage": moisture,
        "Hour": hour,
    }])
    models = bundle["models"]
    features = bundle["features"]

    thirsty = int(models[etiquetas.THIRSTY].predict(row[features[etiquetas.THIRSTY]].values)[0])
    can_water = int(models[etiquetas.CAN_WATER].predict(row[features[etiquetas.CAN_WATER]].values)[0])
    regar = bool(thirsty and can_water)

    return {
        "prediction": "Regar" if regar else "No regar",
        "regar": regar,
        "thirsty": thirsty,
        "can_water": can_water,
        "moisture_percentage": moisture,
        "hour": round(hour, 3),
        "plant_type": etiquetas.PLANT_TYPE_MAP.get(ptype, str(ptype)),
        "in_no_water_window": etiquetas.in_blocked_window(hour),
        "thresholds": list(etiquetas.thresholds_for(ptype)),
    }


if __name__ == "__main__":
    # Prueba manual rápida: python modelo.py 35 14
    bundle = load_model()
    moisture = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0
    hour = sys.argv[2] if len(sys.argv) > 2 else 14
    print(decide(bundle, moisture, hour))
