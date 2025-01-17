import time
import json
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

max_val = None
min_val = None

# Genera la instancia del conversor de señal análoga a digital(ADC)
i2c = busio.I2C(board.SCL, board.SDA)

# Crea el objeto del Conversor ADC usando el driver de la libreria de python.
ads = ADS.ADS1115(i2c)

# Se asigna el PIN de la raspberry que estará recibiendo los datos del sensor (P0)
chan = AnalogIn(ads, ADS.P0)

primer_check = input("El sensor está seco? (ingresa 'y' para continuar): ")
if primer_check == 'y':
    max_val = chan.value
    print("------{:>5}\t{:>5}".format("raw", "v"))
for x in range(0, 10):
    if chan.value > max_val:
        max_val = chan.value
    print("CHAN 0: "+"{:>5}\t{:>5.3f}".format(chan.value, chan.voltage))
time.sleep(0.5)

print('\n')

segundo_check = input("El sensor esta sumergido en agua? (ingresa 'y' para continuar): ")
if segundo_check == 'y':
    min_val = chan.value
    print("------{:>5}\t{:>5}".format("raw", "v"))
for x in range(0, 10):
    if chan.value < min_val:
        min_val = chan.value
    print("CHAN 0: "+"{:>5}\t{:>5.3f}".format(chan.value, chan.voltage))
time.sleep(0.5)

config_data = dict()
config_data["full_saturation"] = min_val
config_data["zero_saturation"] = max_val
with open('cap_config.json', 'w') as outfile:
    json.dump(config_data, outfile)
    print('\n')
    print(config_data)
time.sleep(0.5)