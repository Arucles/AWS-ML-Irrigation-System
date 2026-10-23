# Lista de compras — expansión del sistema de riego

Estado: **en cotización**. No se escribe código hasta que los sensores estén en la casa.

---

## Lo que motiva la compra

El sensor actual (capacitivo analógico) **solo mide humedad de sustrato**. No puede medir
temperatura ni luz: su salida depende únicamente de la constante dieléctrica del medio.
Tampoco tiene dirección I2C (es analógico), lo que impide poner muchos en un mismo bus.

Objetivo final: **una planta medida de forma autónoma**, sin tirar cable hasta la Raspberry Pi.

---

## Prioridad 1 — indispensable: ambiente

| Elemento | Qué aporta | Bus / conexión | Precio ref. |
|---|---|---|---|
| **BME280** | Temperatura **+ humedad de aire** (+ presión, de regalo) | I2C, 0x77 por defecto / 0x76 con puente SDO→GND | $2.000–4.000 CLP (US$14.95 Adafruit) |

Por qué primero: la humedad del aire pesa más que la temperatura para predecir riego.
Un día a 25 °C con 80% de humedad seca el sustrato mucho menos que uno a 25 °C con 25%.

**No choca con lo que ya hay:** el ADS1115 ocupa 0x48. El BME280 entra en 0x76 u 0x77.
Librería: `adafruit-circuitpython-bme280` (ya compatible con el venv + Blinka de la Pi).

---

## Prioridad 2 — luz

| Elemento | Qué aporta | Bus / conexión | Precio ref. |
|---|---|---|---|
| **BH1750** | Luz en **lux calibrados** | I2C, 0x23 (o 0x5C con ADDR) | ~$2.500 CLP |
| *alternativa barata:* **LDR + resistencia 10 kΩ** | Luz como valor crudo (hay que mapearlo a mano) | Analógico → canal A1–A3 del ADS1115 | ~$500 CLP |

Recomendado el BH1750: no ocupa canales del ADC (quedan los 3 libres para otra cosa) y
entrega lux de verdad en vez de un número que hay que calibrar contra otra referencia.

---

## Prioridad 3 — varias plantas SIN cables: ESP32

| Elemento | Qué aporta | Detalle | Precio ref. |
|---|---|---|---|
| **ESP32 DevKit** (1 por planta) | WiFi integrado + ADC + I2C, hace de "nodo" de la planta | ~$4.000 CLP c/u | según nº de plantas |
| **Batería 18650 + portapila** o powerbank | Alimentar cada nodo sin cable | ~$3.000–5.000 CLP c/u | opcional al inicio |
| *(opcional)* **Panel solar 5V + TP4056** | Autonomía permanente | ~$4.000 CLP c/u | opcional |

**Arquitectura:** cada ESP32 lee sus sensores y hace POST/HTTP a `riego-api`.
La Pi deja de ser la única fuente de datos. Firmware sugerido: **ESPHome** (YAML,
sin programar), que ya trae drivers para ADC, BME280 y BH1750.

Ojo con la RAM: la Pi tiene **415 MB** y ya usa ~197 MB con 3 servicios.
Si algún día se agrega MQTT (Mosquitto), revisar antes de instalarlo. POST directo pesa menos.

---

## Prioridad 4 — todo en uno para el sustrato

| Elemento | Qué aporta | Limitación | Precio ref. |
|---|---|---|---|
| **Adafruit STEMMA Soil Sensor** | Humedad **capacitiva + temperatura del suelo** en un pincho | **Dirección I2C fija** → solo 1 por bus (o usar TCA9548A) | US$7.50 + US$1.50 cable |
| *(opcional)* **TCA9548A** multiplexor I2C | Permite varios sensores con dirección fija en un bus | 8 canales, ~$2.000 CLP | solo si se va por cable |

La temperatura que entrega es la del **suelo** (sensor interno del micro, ±2 °C), no del aire.
Se complementa con el BME280, no lo reemplaza.

---

## Lo que NO hay que comprar (y por qué)

- **Más sensores capacitivos analógicos** para varias plantas: obligan a más ADS1115 + TCA9548A +
  un cable por maceta. Más plata, más cobre, y la misma limitación.
- **Sensores resistivos de 2 púas**: se oxidan, la lectura deriva y hay que recalibrar siempre.
- **Módulos WiFi sueltos** para la Pi: el ESP32 ya trae WiFi, no se necesita módulo aparte.

---

## Checklist de compra mínima para empezar

- [ ] 1 × BME280
- [ ] 1 × BH1750 (o LDR + R 10 kΩ si se quiere gastar menos)
- [ ] Cables/jumpers I2C cortos (si el BME280 no viene con STEMMA QT)

Eso completa **una** planta con humedad de suelo + temperatura/aire + luz.
Los ESP32 vienen después, como etapa aparte, cuando se decida cuántas plantas se miden.

---

## Pendiente antes de programar

El sensor actual todavía **no está enterrado**: las últimas lecturas (`raw ~19250 → 10 %`)
son del sensor **al aire**, no del sustrato de la Hierba. Hay que enterrarlo para validar
que el umbral de 40 % es el correcto para esa maceta.
