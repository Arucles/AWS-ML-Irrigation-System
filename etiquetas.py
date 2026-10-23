"""Reglas de negocio y configuración por tipo de planta.

Este módulo es la UNICA fuente de verdad para decidir "que hubiera sido lo
correcto" (la etiqueta de negocio). Lo usan tanto el entrenador del modelo
como el script del sensor, para que nunca se desincronicen.
"""

# Codigos de tipo de planta (se guardan en la columna Plant_Type del CSV)
SUCULENTA, HIERBA, ARBOL, HELECHO = 0, 1, 2, 3

PLANT_TYPE_MAP = {
    SUCULENTA: "Suculentas",
    HIERBA: "Hierba",
    ARBOL: "Arbol",
    HELECHO: "Helecho",
}

# Por planta: (pct_minimo_de_humedad, pct_objetivo)
# pct_minimo  -> por debajo de esto la planta SI necesita agua
# pct_objetivo-> por debajo de esto todavia se riega si estas en una hora valida
# Si se desconoce el tipo, se usa la configuracion de la hierba (por defecto).
WATERING_THRESHOLDS = {
    SUCULENTA: (35.0, 70.0),
    HIERBA: (40.0, 80.0),
    ARBOL: (50.0, 90.0),
    HELECHO: (45.0, 75.0),
}
DEFAULT_PLANT_TYPE = HIERBA

# Ventana prohibida: el sol pega mas fuerte (hora local, puede ser decimal,
# p.ej. 16.5 = 16:30). Dentro de esta ventana NO se riega nunca, aunque el
# suelo este seco. Incluye el inicio y excluye el fin: [11, 16) => 11:00-15:59.
NO_WATER_START_HOUR = 11.0
NO_WATER_END_HOUR = 16.0

# Riego de emergencia: si la planta esta mas seca que este porcentaje
# (critico = minimo - CRITICAL_DELTA), se riega incluso en la ventana prohibida,
# porque esperar hasta las 16:00 podria matarla.
#   * CRITICAL_DELTA = 10 -> la hierba (min 40%) riega a mediodia por debajo del 30%.
#   * CRITICAL_DELTA = 100 -> desactiva el riego de emergencia por completo.
CRITICAL_DELTA = 10.0


# Nombre -> codigo, en minusculas y sin acentos, para aceptar "Arbol", "árbol"...
_PLANT_TYPE_BY_NAME = {
    "suculenta": SUCULENTA, "suculentas": SUCULENTA,
    "hierba": HIERBA, "pasto": HIERBA, "cesped": HIERBA,
    "arbol": ARBOL, "arboles": ARBOL,
    "helecho": HELECHO, "helechos": HELECHO,
}


def normalize_plant_type(plant_type):
    """Devuelve un codigo de planta valido; nunca lanza excepcion.

    Acepta el codigo numerico (0-3) o el nombre que escribe el sensor
    ("Hierba", "Arbol", ...). Si no lo reconoce, usa DEFAULT_PLANT_TYPE.
    """
    try:
        return int(plant_type)
    except (TypeError, ValueError):
        pass
    name = str(plant_type).strip().lower()
    for accent, plain in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        name = name.replace(accent, plain)
    return _PLANT_TYPE_BY_NAME.get(name, DEFAULT_PLANT_TYPE)


def normalize_hour(hour):
    """Acepta la hora como numero (entero o decimal) o como 'HH:MM' / 'HH:MM:SS'."""
    if isinstance(hour, str):
        parts = hour.strip().split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            raise ValueError(f"Hora invalida: {hour!r}")
        hour = h + m / 60.0
    hour = float(hour)
    if not 0.0 <= hour <= 24.0:
        raise ValueError(f"La hora debe estar entre 0 y 24, se recibio {hour!r}")
    return hour


def thresholds_for(plant_type):
    return WATERING_THRESHOLDS.get(normalize_plant_type(plant_type), WATERING_THRESHOLDS[DEFAULT_PLANT_TYPE])


def in_blocked_window(hour):
    """True si la hora cae en la franja donde no se debe regar (sol encima)."""
    return NO_WATER_START_HOUR <= normalize_hour(hour) < NO_WATER_END_HOUR


def needs_water_physically(moisture_percentage, plant_type=DEFAULT_PLANT_TYPE):
    """True si la planta esta por debajo de su minimo (hace falta agua)."""
    min_threshold, _ = thresholds_for(plant_type)
    return float(moisture_percentage) < min_threshold


def is_critical(moisture_percentage, plant_type=DEFAULT_PLANT_TYPE):
    """True si la planta esta tan seca que se riega aunque el sol este encima."""
    if CRITICAL_DELTA > 100:
        return False
    min_threshold, _ = thresholds_for(plant_type)
    return float(moisture_percentage) < (min_threshold - CRITICAL_DELTA)


# ---------------------------------------------------------------------------
# IMPORTANTE: por que hay DOS objetivos y no uno
# ---------------------------------------------------------------------------
# La decision final ("regar hoy") es una CONJUNCION:  hora_valida AND suelo_seco.
# Si se entrena un solo arbol con esa etiqueta, el arbol casi nunca aprende la
# conjuncion: si la mayor parte de las muestras son "si" (porque el suelo suele
# estar seco y casi todo el dia es hora valida), predecir siempre "si" ya acierta
# casi todo y los arboles eligen eso. Ademas, el umbral de humedad dentro de la
# ventana prohibida es distinto (solo riego de emergencia), asi que "suelo seco"
# no es una funcion unica de la humedad: NO se puede aprender con un arbol.
#
# Solucion: separar en dos salidas y combinarlas en tiempo de ejecucion.
#   * THIRSTY  : la planta necesita agua (funcion de humedad + tipo). Aprendible.
#   * CAN_WATER: a esta hora el riego es seguro (funcion de hora). Aprendible.
#   * ACCION   : THIRSTY AND CAN_WATER  -> se calcula, no se aprende.
# ---------------------------------------------------------------------------
THIRSTY, CAN_WATER, DECISION = "Thirsty", "Can_Water", "Regar"

TARGETS = [THIRSTY, CAN_WATER]


def ground_truth_label(hour, moisture_percentage, plant_type=DEFAULT_PLANT_TYPE):
    """Decision final por reglas: 1 = regar, 0 = no regar.

    Es la referencia (ground truth) contra la que se valida el sistema completo.
    """
    t = thirsty_label(moisture_percentage, plant_type)
    c = can_water_label(hour, moisture_percentage, plant_type)
    return int(t and c)


def thirsty_label(moisture_percentage, plant_type=DEFAULT_PLANT_TYPE):
    """Target THIRSTY: 1 si la humedad esta por debajo del minimo de la planta."""
    return int(needs_water_physically(moisture_percentage, plant_type))


def can_water_label(hour, moisture_percentage, plant_type=DEFAULT_PLANT_TYPE):
    """Target CAN_WATER: 1 si a esta hora es seguro regar con esta humedad.

    Es la parte "de horario" de la decision: prohibe la ventana central del dia
    salvo riego de emergencia para plantas muy secas.
    """
    if in_blocked_window(hour):
        return int(is_critical(moisture_percentage, plant_type))
    return 1


def sensor_label(hour, moisture_percentage, plant_type=DEFAULT_PLANT_TYPE):
    """Alias historico: la decision que se guarda en el CSV."""
    return ground_truth_label(hour, moisture_percentage, plant_type)
