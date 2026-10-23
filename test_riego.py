"""Pruebas del sistema de riego (sin hardware).

Ejecutar:  python -m unittest test_riego -v
"""

import json
import unittest
import urllib.error
import urllib.request

import etiquetas
import modelo


class TestReglas(unittest.TestCase):
    def test_ventana_prohibida(self):
        self.assertFalse(etiquetas.in_blocked_window(10.99))
        self.assertTrue(etiquetas.in_blocked_window(11.0))
        self.assertTrue(etiquetas.in_blocked_window(15.99))
        self.assertFalse(etiquetas.in_blocked_window(16.0))

    def test_hora_decimal_y_texto(self):
        self.assertAlmostEqual(etiquetas.normalize_hour("14:30"), 14.5)
        self.assertAlmostEqual(etiquetas.normalize_hour("14:30:00"), 14.5)
        self.assertAlmostEqual(etiquetas.normalize_hour(14), 14.0)
        with self.assertRaises(ValueError):
            etiquetas.normalize_hour(25)

    def test_tipo_de_planta_por_nombre_y_codigo(self):
        self.assertEqual(etiquetas.normalize_plant_type("Hierba"), etiquetas.HIERBA)
        self.assertEqual(etiquetas.normalize_plant_type("árbol"), etiquetas.ARBOL)
        self.assertEqual(etiquetas.normalize_plant_type("2"), etiquetas.ARBOL)
        self.assertEqual(etiquetas.normalize_plant_type("desconocida"), etiquetas.DEFAULT_PLANT_TYPE)

    def test_regla_de_negocio(self):
        h = etiquetas.HIERBA  # min 40, objetivo 80
        min_thr, _ = etiquetas.thresholds_for(h)
        critical = min_thr - etiquetas.CRITICAL_DELTA - 1  # por debajo del umbral de emergencia
        self.assertEqual(etiquetas.ground_truth_label(6, 30, h), 1)   # seco, mañana
        self.assertEqual(etiquetas.ground_truth_label(13, 30, h), 0)  # seco, sol encima
        self.assertEqual(etiquetas.ground_truth_label(13, critical, h), 1)  # emergencia
        self.assertEqual(etiquetas.ground_truth_label(19, 30, h), 1)  # seco, tarde
        self.assertEqual(etiquetas.ground_truth_label(6, 85, h), 0)   # húmedo
        self.assertEqual(etiquetas.thirsty_label(30, h), 1)
        self.assertEqual(etiquetas.can_water_label(13, 30, h), 0)
        self.assertEqual(etiquetas.can_water_label(6, 90, h), 1)


class TestModeloEntrenado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = modelo.load_model()

    def test_no_riega_con_sol_encima_aunque_este_seco(self):
        for hour in (11.0, 12.5, 15.9):
            d = modelo.decide(self.bundle, 30, hour, etiquetas.HIERBA)
            self.assertEqual(d["thirsty"], 1)
            self.assertEqual(d["can_water"], 0)
            self.assertEqual(d["prediction"], "No regar")

    def test_riega_en_manana_y_tarde_si_esta_seco(self):
        for hour in (3, 7, 9, 16.0, 18.5, 21):
            d = modelo.decide(self.bundle, 30, hour, etiquetas.HIERBA)
            self.assertEqual(d["prediction"], "Regar", f"hora {hour}")

    def test_no_riega_si_esta_humeda(self):
        for hour in (3, 9, 13, 19):
            d = modelo.decide(self.bundle, 85, hour, etiquetas.HIERBA)
            self.assertEqual(d["prediction"], "No regar", f"hora {hour}")

    def test_acepta_hora_texto_y_planta_texto(self):
        d = modelo.decide(self.bundle, 30, "14:30", "Hierba")
        self.assertEqual(d["prediction"], "No regar")
        self.assertEqual(d["plant_type"], "Hierba")

    def test_valores_fuera_de_rango(self):
        with self.assertRaises(ValueError):
            modelo.decide(self.bundle, 150, 10)
        with self.assertRaises(ValueError):
            modelo.decide(self.bundle, 30, "99:99")


class TestAPI(unittest.TestCase):
    """Pruebas HTTP contra un app.py ya arrancado (se saltan si no responde)."""

    BASE = "http://127.0.0.1:5000"

    def setUp(self):
        try:
            urllib.request.urlopen(f"{self.BASE}/health", timeout=2).read()
        except Exception:
            self.skipTest("app.py no está corriendo en 127.0.0.1:5000")

    def post(self, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(f"{self.BASE}/predict", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def test_health(self):
        with urllib.request.urlopen(f"{self.BASE}/health", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["no_water_window"], [11.0, 16.0])
        self.assertIn("Thirsty", data["features"])

    def test_no_riega_a_mediodia(self):
        status, data = self.post({"Moisture_Percentage": 30, "Hour": 13, "Plant_Type": "Hierba"})
        self.assertEqual(status, 200)
        self.assertIs(data["regar"], False)
        self.assertEqual(data["thirsty"], 1)

    def test_riega_con_hora_texto_y_acentos(self):
        status, data = self.post({"Moisture_Percentage": 30, "Hour": "18:30", "Plant_Type": "árbol"})
        self.assertEqual(status, 200, data)
        self.assertIs(data["regar"], True)
        self.assertEqual(data["plant_type"], "Arbol")
        self.assertEqual(data["hour"], 18.5)

    def test_validacion(self):
        self.assertEqual(self.post({"Moisture_Percentage": 30})[0], 400)
        self.assertEqual(self.post({"Moisture_Percentage": 500, "Hour": 6})[0], 400)
        self.assertEqual(self.post({"Moisture_Percentage": 30, "Hour": "99:99"})[0], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
