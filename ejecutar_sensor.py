import csv
import time
import board
import busio
import json
from datetime import datetime
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ==========================================
# CONFIGURACIÓN GENERAL (Ajusta aquí)
# ==========================================
# 0: Suculentas, 1: Hierba, 2: Arbol, 3: Helecho
TIPO_PLANTA = 1  

plant_type_map = {0: "Suculentas", 1: "Hierba", 2: "Arbol", 3: "Helecho"}

# Umbral: (Mínimo histórico para activar riego, Máximo deseado)
watering_thresholds = {
    0: (35, 70),  # Suculentas
    1: (40, 80),  # Hierba
    2: (50, 90),  # Arbol
    3: (45, 75)   # Helecho
}

# ==========================================
# INICIALIZACIÓN DE HARDWARE Y CONFIG
# ==========================================
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1

# Cargar calibración
with open("cap_config.json") as json_data_file:
    config_data = json.load(json_data_file)

ZERO_SAT = config_data["zero_saturation"]
FULL_SAT = config_data["full_saturation"]

# Instanciar canal analógico (Pin A0 del ADS1115)
chan = AnalogIn(ads, 0)

# Config del archivo CSV
csv_filename = "soil_moisture_data.csv"
header = ["Date", "Time", "Plant_Type", "Moisture_Level", "Moisture_Percentage", "Water_Needed"]

try:
    with open(csv_filename, mode="x", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        print(f"Se crea el archivo '{csv_filename}'")
except FileExistsError:
    print(f"Archivo '{csv_filename}' detectado. Agregando datos.")

# ==========================================
# FUNCIONES LÓGICAS
# ==========================================
def read_moisture_stable(muestras=15):
    """Toma varias lecturas para mitigar el ruido analógico"""
    valores = []
    for _ in range(muestras):
        valores.append(chan.value)
        time.sleep(0.05)
    return int(sum(valores) / len(valores))

def percent_translation(raw_val):
    """Transforma la lectura analógica a un porcentaje de 0 a 100%"""
    per_val = ((ZERO_SAT - raw_val) / (ZERO_SAT - FULL_SAT)) * 100
    return round(max(0.0, min(100.0, per_val)), 2)

def label_watering_time(moisture_percentage):
    """
    Etiqueta pura para Machine Learning: 
    Solo evalúa la necesidad física de la planta.
    """
    min_threshold, _ = watering_thresholds[TIPO_PLANTA]
    if moisture_percentage < min_threshold:
        return 1  # La planta necesita agua físicamente
    return 0

def log_to_csv(date, time_str, moisture_level, moisture_percentage, water_needed):
    with open(csv_filename, mode="a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([date, time_str, plant_type_map[TIPO_PLANTA], moisture_level, moisture_percentage, water_needed])
        print(f"[{time_str}] H: {moisture_percentage}% | RAW: {moisture_level} | ¿Regar?: {water_needed}")

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
try:
    print(f"Monitoreo activo para: {plant_type_map[TIPO_PLANTA]}. Intervalo: 10 min.")
    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        
        # Captura y procesamiento
        moisture_level = read_moisture_stable()
        moisture_percentage = percent_translation(moisture_level)
        
        # Evaluar necesidad de riego
        water_needed = label_watering_time(moisture_percentage)
        
        # Persistencia
        log_to_csv(current_date, current_time, moisture_level, moisture_percentage, water_needed)
        
        # Esperar 10 minutos (600 segundos)
        time.sleep(600)

except KeyboardInterrupt:
    print("\nMonitoreo detenido por el usuario.")
