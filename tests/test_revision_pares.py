"""Pruebas de las funciones nuevas del parche 15 (revision por pares).

No corre el flujo completo (necesita el parquet intermedio); fija el
comportamiento de las funciones puras que decide el resto del script:
la clasificacion forma_del_nombre (una DECISION, igual que forma_de() en
07 - ver test_forma_termino.py), la descomposicion de Kitagawa y el
estimador de ICC por metodo de momentos.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_spec = importlib.util.spec_from_file_location(
    "p15", Path(__file__).resolve().parents[1] / "src" / "15_revision_pares.py")
p15 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p15)


# ------------------------------------------------------- forma_del_nombre

def test_numero_codigo():
    for t in ("rojo 40", "azul 1", "amarillo 5", "e-120", "e 129", "ci 15985", "amarillo 6"):
        assert p15.forma_del_nombre(t) == "numero_codigo", t


def test_nombre_tecnico():
    for t in ("curcumina", "tartrazina", "azul brillante", "eritrosina", "amarillo ocaso"):
        assert p15.forma_del_nombre(t) == "nombre_tecnico", t


def test_nombre_comun_planta():
    for t in ("curcuma", "achiote", "paprika", "beta caroteno", "betacaroteno",
             "extracto de zanahoria", "cochinilla"):
        assert p15.forma_del_nombre(t) == "nombre_comun_planta", t


# ------------------------------------------------------------- kitagawa

def test_kitagawa_media_ponderada():
    """Caso de juguete con pesos y tasas exactas: verifica a mano que la
    estandarizacion pondera bien y que la direccion espejo (B) usa la tasa
    cruda del OTRO origen, no la estandarizada."""
    celdas = pd.DataFrame([
        {"clase": "sintetico", "en_vocab_off": False, "n": 100, "sin_tag": 90},
        {"clase": "sintetico", "en_vocab_off": True, "n": 300, "sin_tag": 30},
        {"clase": "natural_botanico", "en_vocab_off": False, "n": 50, "sin_tag": 50},
        {"clase": "natural_botanico", "en_vocab_off": True, "n": 50, "sin_tag": 25},
    ])
    crudas = celdas.groupby("clase")[["n", "sin_tag"]].sum().reset_index()
    r = p15.kitagawa(celdas, crudas)
    # tasa natural estandarizada con pesos del sintetico (100/400 fuera_vocab=False,
    # 300/400 en_vocab=True): 0.25*1.0 + 0.75*0.5 = 0.625 -> 62.5 %
    dir_a = r["direccion_A_peso_sintetico_sobre_tasas_naturales"]
    assert abs(dir_a["tasa_natural_estandarizada_pct"] - 62.5) < 1e-6
    # diferencia cruda: natural crudo 75/100=75% menos sintetico crudo 120/400=30%
    assert abs(r["diferencia_cruda_pp"] - 45.0) < 1e-6


def test_kitagawa_sin_celdas_comunes_devuelve_none():
    celdas = pd.DataFrame([
        {"clase": "sintetico", "en_vocab_off": True, "n": 10, "sin_tag": 1},
    ])
    crudas = pd.DataFrame([
        {"clase": "sintetico", "n": 10, "sin_tag": 1},
        {"clase": "natural_botanico", "n": 10, "sin_tag": 5},
    ])
    assert p15.kitagawa(celdas, crudas) is None


# -------------------------------------------------------- icc_por_codigo

def test_icc_cero_cuando_todos_los_codigos_igual_tasa():
    """Si todos los codigos tienen exactamente la misma tasa, no hay
    variacion ENTRE codigos y el ICC deberia salir en (o muy cerca de) cero."""
    filas = []
    for cod in ("A", "B", "C", "D"):
        for i in range(100):
            filas.append({"codigo": cod, "en_tags": i >= 30})  # 70% sin_tag en los 4
    det = pd.DataFrame(filas)
    r = p15.icc_por_codigo(det)
    assert r["ICC"] < 0.01
    assert r["design_effect"] < 1.1


def test_icc_alto_cuando_codigos_muy_distintos():
    """Codigos con tasas extremas y opuestas (0 % y 100 %) deberian dar un
    ICC alto -la varianza esta toda ENTRE codigos, no dentro-."""
    filas = []
    for cod, todos_sin_tag in (("A", True), ("B", True), ("C", False), ("D", False)):
        for i in range(50):
            filas.append({"codigo": cod, "en_tags": not todos_sin_tag})
    det = pd.DataFrame(filas)
    r = p15.icc_por_codigo(det)
    assert r["ICC"] > 0.9
