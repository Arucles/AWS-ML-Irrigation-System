import argparse
import csv
import os
import time
from datetime import datetime

import requests

import etiquetas
import modelo as modelo_riego

try:  # En la Raspberry Pi están instalados; en el PC de desarrollo no hacen falta.
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    HARDWARE_OK = True
except ImportError:
    HARDWARE_OK = False

# Webhook de Discord: se lee de la variable de entorno DISCORD_WEBHOOK_URL (no se commitea)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# ==========================================
# CONFIGURACIÓN GENERAL (Ajusta aquí)
# ==========================================
# 0: Suculentas, 1: Hierba, 2: Arbol, 3: Helecho
TIPO_PLANTA = etiquetas.HIERBA

# Intervalo de muestreo en segundos (2 horas)
INTERVALO = 7200

# Archivo CSV (se puede sobreescribir con la variable de entorno CSV_FILE)
csv_filename = os.environ.get("CSV_FILE", "soil_moisture_data.csv")
header = ["Date", "Time", "Plant_Type", "Moisture_Level", "Moisture_Percentage", "Water_Needed"]


def init_hardware():
    """Inicializa ADS1115 + sensor capacitivo y devuelve (chan, zero_sat, full_sat)."""
    if not HARDWARE_OK:
        raise RuntimeError(
            "Faltan librerías de hardware (board, busio, adafruit_ads1x15). "
            "En la Raspberry Pi: pip install adafruit-blinka adafruit-circuitpython-ads1x15\n"
            "En el PC puedes probar con: python ejecutar_sensor.py --demo"
        )
    import json

    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    ads.gain = 1
    chan = AnalogIn(ads, 0)

    # La calibración se ejecuta con calibrar_sensor.py
    with open("cap_config.json") as json_data_file:
        config_data = json.load(json_data_file)
    return chan, config_data["zero_saturation"], config_data["full_saturation"]


def ensure_csv():
    try:
        with open(csv_filename, mode="x", newline="") as csvfile:
            csv.writer(csvfile).writerow(header)
            print(f"Se crea el archivo '{csv_filename}'")
    except FileExistsError:
        print(f"Archivo '{csv_filename}' detectado. Agregando datos.")


# ==========================================
# FUNCIONES LÓGICAS
# ==========================================
def read_moisture_stable(chan, muestras=15):
    """Toma varias lecturas para mitigar el ruido analógico"""
    valores = []
    for _ in range(muestras):
        valores.append(chan.value)
        time.sleep(0.05)
    return int(sum(valores) / len(valores))


def percent_translation(raw_val, zero_sat, full_sat):
    """Transforma la lectura analógica a un porcentaje de 0 a 100%"""
    per_val = ((zero_sat - raw_val) / (zero_sat - full_sat)) * 100
    return round(max(0.0, min(100.0, per_val)), 2)


def label_watering_time(hour, moisture_percentage, plant_type):
    """Etiqueta de negocio: humedad por planta + ventana horaria (etiquetas.py).

    OJO: antes esta función sólo miraba la humedad. Por eso el árbol nunca
    podía aprender nada sobre la hora. Ahora usa la regla completa, la misma
    que entrena el modelo.
    """
    return etiquetas.sensor_label(hour, moisture_percentage, plant_type)


def log_to_csv(date, time_str, moisture_level, moisture_percentage, water_needed):
    with open(csv_filename, mode="a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([date, time_str, etiquetas.PLANT_TYPE_MAP[TIPO_PLANTA],
                         moisture_level, moisture_percentage, water_needed])
        print(f"[{time_str}] H: {moisture_percentage}% | RAW: {moisture_level} | ¿Regar?: {water_needed}")


def enviar_alerta_discord(time_str, moisture_percentage, water_needed, decision=None):
    # Armar un formato bonito con emojis para el canal
    umbral = etiquetas.thresholds_for(TIPO_PLANTA)[0]
    emoji_estado = "🌱" if moisture_percentage >= umbral else "🍂"
    if water_needed == 1:
        alerta_riego = "💦 **Toca regar** (suelo seco y hora valida)."
    elif decision and decision.get("thirsty") and decision.get("in_no_water_window"):
        alerta_riego = "🌞 Suelo seco, pero **no se riega ahora** (11:00-16:00). Se regará al refrescar."
    else:
        alerta_riego = "✅ Planta hidratada."

    mensaje = (
        f"{emoji_estado} **Reporte de Humedad** [{time_str}] · {etiquetas.PLANT_TYPE_MAP[TIPO_PLANTA]}\n"
        f"• Humedad Actual: `{moisture_percentage}%`\n"
        f"• Estado: {alerta_riego}"
    )

    payload = {"content": mensaje}

    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL no está definida; no se envía el reporte.")
        return

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code != 204:
            print(f"Error enviando a Discord: {response.status_code}")
    except Exception as e:
        print(f"No se pudo conectar con Discord: {e}")

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Lee el sensor de humedad y decide si regar")
    parser.add_argument("--demo", action="store_true",
                        help="Simula lecturas (sin hardware) para probar en el PC")
    parser.add_argument("--once", action="store_true", help="Hace una sola lectura y termina")
    parser.add_argument("--interval", type=int, default=INTERVALO, help="Segundos entre lecturas")
    args = parser.parse_args()

    bundle = modelo_riego.load_model()
    ensure_csv()
    chan = zero_sat = full_sat = None
    if not args.demo:
        chan, zero_sat, full_sat = init_hardware()

    print(f"Monitoreo activo para: {etiquetas.PLANT_TYPE_MAP[TIPO_PLANTA]}. "
          f"Intervalo: {args.interval // 60} min.{' (MODO DEMO)' if args.demo else ''}")

    try:
        while True:
            now = datetime.now()
            hour = now.hour + now.minute / 60.0

            # Captura y procesamiento
            if args.demo:
                # Rampa determinista de humedad 25% -> 85% para probar la lógica.
                moisture_percentage = round(25 + (now.minute % 60) / 60 * 60, 2)
                moisture_level = 0
            else:
                moisture_level = read_moisture_stable(chan)
                moisture_percentage = percent_translation(moisture_level, zero_sat, full_sat)

            # Decisión del modelo compuesto (Thirsty AND Can_Water)
            decision = modelo_riego.decide(bundle, moisture_percentage, hour, TIPO_PLANTA)
            water_needed = 1 if decision["regar"] else 0

            # Persistencia
            log_to_csv(now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                       moisture_level, moisture_percentage, water_needed)
            print(f"    modelo -> thirsty={decision['thirsty']}, "
                  f"can_water={decision['can_water']}, ventana_prohibida={decision['in_no_water_window']}")

            # Enviar reporte a tu canal de Discord
            enviar_alerta_discord(now.strftime("%H:%M:%S"), moisture_percentage,
                                  water_needed, decision)

            if args.once:
                break
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nMonitoreo detenido por el usuario.")


if __name__ == "__main__":
    main()

