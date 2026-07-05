import time
import json
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# Inicialización del bus I2C y el ADC
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan = AnalogIn(ads, 0)

def obtener_lectura_estable(muestras=15):
    """Toma varias lecturas espaciadas en el tiempo para promediar el ruido analógico"""
    valores = []
    for _ in range(muestras):
        valores.append(chan.value)
        time.sleep(0.1) # Pausa de 100ms entre muestras para estabilidad
    return int(sum(valores) / len(valores))

print("=== SCRIPT DE CALIBRACIÓN PARA SISTEMA DE RIEGO ===")

primer_check = input("\n1. ¿El sensor está completamente SECO? (ingresa 'y' para continuar): ")
if primer_check.lower() == 'y':
    print("Leyendo entorno seco...")
    max_val = obtener_lectura_estable()
    print(f"-> Valor registrado para 0% humedad (Seco): {max_val}")
else:
    print("Calibración cancelada.")
    exit()

segundo_check = input("\n2. ¿El sensor está SUMERGIDO en agua? (ingresa 'y' para continuar): ")
if segundo_check.lower() == 'y':
    print("Leyendo entorno húmedo...")
    min_val = obtener_lectura_estable()
    print(f"-> Valor registrado para 100% humedad (Agua): {min_val}")
else:
    print("Calibración cancelada.")
    exit()

# Guardar configuración de forma ordenada
config_data = {
    "zero_saturation": max_val,      # El valor analógico más alto (seco)
    "full_saturation": min_val       # El valor analógico más bajo (agua)
}

with open('cap_config.json', 'w') as outfile:
    json.dump(config_data, outfile, indent=4)
    print('\n[ÉXITO] Archivo cap_config.json guardado con éxito:')
    print(json.dumps(config_data, indent=4))
