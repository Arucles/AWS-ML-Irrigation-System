"""API de predicción del sistema de riego.

Ejecutar:  python app.py
Probar:    curl -X POST http://127.0.0.1:5000/predict -H "Content-Type: application/json" -d "{\"Moisture_Percentage\": 35, \"Hour\": 14}"

El modelo es "Regar = Thirsty AND Can_Water":
  * Thirsty   : humedad por debajo del mínimo de la planta.
  * Can_Water : fuera de la ventana 11:00-16:00 (cuando el sol está encima).
"""

import os

from flask import Flask, jsonify, request

import etiquetas
import modelo

app = Flask(__name__)
BUNDLE = modelo.load_model(os.environ.get("MODEL_FILE", modelo.MODEL_FILE))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "features": BUNDLE["features"],
        "no_water_window": [etiquetas.NO_WATER_START_HOUR, etiquetas.NO_WATER_END_HOUR],
    })


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    # Se aceptan los nombres históricos del CSV (Moisture_Percentage / Hour) y
    # además plant_type, necesario para soportar varias plantas.
    moisture = data.get("Moisture_Percentage", data.get("moisture"))
    hour = data.get("Hour", data.get("hour"))
    plant_type = data.get("plant_type", data.get("Plant_Type", etiquetas.DEFAULT_PLANT_TYPE))

    if moisture is None or hour is None:
        return jsonify({"error": "Se requieren 'Moisture_Percentage' y 'Hour'"}), 400

    try:
        result = modelo.decide(BUNDLE, moisture, hour, plant_type)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


if __name__ == "__main__":
    # host=0.0.0.0 permite que la app móvil u otros equipos de la LAN la consulten.
    # debug=True activa el reloader de Werkzeug, que lanza un SEGUNDO proceso Python
    # (~87 MB extra). En la Raspberry Pi de 512 MB eso provoca swap; se activa con DEBUG=1.
    debug = os.environ.get("DEBUG", "") == "1"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=debug)

