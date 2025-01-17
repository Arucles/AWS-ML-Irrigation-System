import csv
import time
import board
import busio
import json
from datetime import datetime
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn  # se requiere para lecturas de un punto

# Crea el bus I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Crea el conversor de Analogo a digital
ads = ADS.ADS1115(i2c)
GAIN = 1  # Se ajusta la ganancia de voltaje del conversor
ads.gain = GAIN  # y se asigna al objeto del conversor.

# Se cargan los datos de configuracion
with open("cap_config.json") as json_data_file:
    config_data = json.load(json_data_file)

# Crear el diccionario de tipos de plantas
plant_type_map = {
    0: "Suculentas",
    1: "Hierba",
    2: "Arbol",
    3: "Helecho"
}

# Definir los limites de porcentaje de humedad para regar
watering_thresholds = {
    0: (35, 70),  # Suculentas
    1: (40, 80),  # Hierba
    2: (50, 90),  # Arbol
    3: (45, 75)   # Helecho
}

# Se le pregunta al usuario el tipo de planta que estará leyendo el sensor
print("Elige un tipo de planta(numero):")
for num, name in plant_type_map.items():
    print(f"{num}: {name}")

while True:
    try:
        plant_type_num = int(input("Ingresa el numero correspondiente al tipo: ").strip())
        if plant_type_num in plant_type_map:
            plant_type = plant_type_map[plant_type_num]
            print(f"Tipo de planta seleccionado: {plant_type}")
            break
        else:
            print("Seleccion invalida. Intentalo de nuevo")
    except ValueError:
        print("Ingreso no valido, selecciona otro numero.")

# Config del archivo csv
csv_filename = "soil_moisture_data.csv"
header = ["Date", "Time", "Plant_Type", "Moisture_Level", "Moisture_Percentage", "Water_Needed"]

# Crea el archivo csv
try:
    with open(csv_filename, mode="x", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        print(f"Se crea el archivo '{csv_filename}' con enbezado: {header}")
except FileExistsError:
    print(f"Archivo '{csv_filename}' ya existe. Agregando datos.")

# Funcion para transformar la humedad a porcentaje
def percent_translation(raw_val):
    per_val = abs((raw_val - config_data["zero_saturation"]) / (config_data["full_saturation"] - config_data["zero_saturation"])) * 100
    return round(per_val, 3)

# Funcion para obtener el porcentaje de humedad usando el sensor.
def read_moisture():
    # Se usa el channel 0 para obtener los datos
    chan = AnalogIn(ads, ADS.P0)  # Se puede cambiar de canal si lo desea. P1, P2, P3 etc.
    return chan.value

# Funcion para determinar si necesita riego o no
# Si necesita, devolverá 1, sino devolverá 0
def label_watering_time(row):
    # Extraer datos de la fila
    plant_type_num = row["Plant_Type"]
    time = row["Time"]
    moisture_percentage = row["Moisture_Percentage"]

    # Definir el rango de tiempo para regar
    if 8 <= time <= 20:  # Solo entre 8:00 y 20:00
        min_threshold, max_threshold = watering_thresholds[plant_type_num]
        if min_threshold <= moisture_percentage <= max_threshold:
            return 1  # Regar
    return 0  # No regar

# Guardar los datos en el archivo csv
def log_to_csv(date, time, plant_type_num, moisture_level, moisture_percentage, water_needed):
    with open(csv_filename, mode="a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([date, time, plant_type_num, moisture_level, moisture_percentage, water_needed])
        print(f"Datos guardados - Fecha: {date}, Hora: {time}, Tipo planta(num): {plant_type_num}, "
              f"Nivel humedad: {moisture_level}, % Humedad: {moisture_percentage}, Requiere agua: {water_needed}")

# Ciclo principal para recolectar los datos
try:
    print("Comienza recoleccion de datos. CTRL+C para cancelar")
    while True:
        # Obtener fecha, hora y nivel de humedad
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        current_hour = now.hour  # Obtener solo la hora
        moisture_level = read_moisture()
        moisture_percentage = percent_translation(moisture_level)

        # Crear una fila temporal para calcular si necesita riego
        temp_row = {
            "Plant_Type": plant_type_num,
            "Time": current_hour,
            "Moisture_Percentage": moisture_percentage
        }

        # Determina si se necesita regar
        water_needed = label_watering_time(temp_row)

        # Guardar datos al csv
        log_to_csv(current_date, current_time, plant_type_num, moisture_level, moisture_percentage, water_needed)

        # Esperar hasta la siguiente lectura en segundos
        time.sleep(600)  # Ajustar el intervalo a lo que se desee

except KeyboardInterrupt:
    print("\nRecoleccion detenida.")
