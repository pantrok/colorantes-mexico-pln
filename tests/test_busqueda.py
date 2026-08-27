"""Pruebas de las partes del paso 13 que NO necesitan red.

Como el script no se pudo probar contra las APIs reales, al menos queda fijado
lo que si es comprobable sin salir: la reconstruccion del resumen invertido de
OpenAlex, la deduplicacion, el puntaje de relevancia y el RIS.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "p13", RAIZ / "src" / "13_buscar_antecedentes.py")
p13 = importlib.util.module_from_spec(_spec)
sys.modules["p13"] = p13
_spec.loader.exec_module(p13)

REGLAS = {"terminos_fuertes": ["colorante", "open food facts"],
          "terminos_pais": ["mexico"], "idiomas_interes": ["es", "en"]}


def test_resumen_invertido_se_reconstruye_en_orden():
    inv = {"Los": [0], "colorantes": [1], "naturales": [2], "son": [3], "caros": [4]}
    assert p13.texto_de_abstract(inv) == "Los colorantes naturales son caros"


def test_resumen_vacio_no_revienta():
    assert p13.texto_de_abstract(None) == ""
    assert p13.texto_de_abstract({}) == ""


def test_clave_de_titulo_ignora_acentos_y_puntuacion():
    a = p13.clave_titulo("Colorantes en Alimentos: un análisis")
    b = p13.clave_titulo("colorantes en alimentos  un analisis")
    assert a == b


def test_relevancia_premia_mexico():
    mx = {"titulo": "Colorantes en alimentos de Mexico", "resumen": "", "revista": "",
          "paises": "MX", "idioma": "es"}
    otro = {"titulo": "Food colorants in Japan", "resumen": "", "revista": "",
            "paises": "JP", "idioma": "en"}
    assert p13.puntuar(mx, REGLAS) > p13.puntuar(otro, REGLAS)


def test_relevancia_premia_open_food_facts():
    con = {"titulo": "Validating Open Food Facts additives", "resumen": "",
           "revista": "", "paises": "", "idioma": "en"}
    sin = {"titulo": "Something unrelated entirely", "resumen": "",
           "revista": "", "paises": "", "idioma": "en"}
    assert p13.puntuar(con, REGLAS) > p13.puntuar(sin, REGLAS)


def test_ris_incluye_doi_y_bloque():
    df = pd.DataFrame([{"titulo": "Prueba", "anio": 2024, "revista": "Rev",
                        "doi": "10.1/x", "bloque": "A_x"}])
    ris = p13.a_ris(df)
    assert "TY  - JOUR" in ris and "DO  - 10.1/x" in ris
    assert "KW  - bloque:A_x" in ris and ris.rstrip().endswith("ER  -")


def test_ris_tolera_anio_faltante():
    df = pd.DataFrame([{"titulo": "Sin anio", "anio": float("nan"), "revista": "",
                        "doi": "", "bloque": "B"}])
    assert "PY  -" not in p13.a_ris(df)
