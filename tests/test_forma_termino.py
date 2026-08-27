"""Pruebas de la clasificacion termino -> forma del script 07.

La clasificacion es una DECISION, no un hecho observado, y de ella depende el
veredicto del falsador 1. Estas pruebas fijan los casos que ya sabemos que
importan para que un cambio en la lista FUENTES no los rompa en silencio.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "p07", Path(__file__).resolve().parents[1] / "src" / "07_forma_y_clase.py")
p07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p07)
forma_de = p07.forma_de


def test_codigos_e():
    for t in ("E102", "e 129", "e-160b", "CI 16035", "ci 42090"):
        assert forma_de(t) == "codigo_e", t


def test_codigo_embebido():
    # un termino que trae el codigo dentro cuenta como codigo
    assert forma_de("rojo allura ac (e129)") == "codigo_e"


def test_nombres_de_sustancia():
    for t in ("tartrazina", "indigotina", "acido carminico", "betalaina",
              "dioxido de titanio"):
        assert forma_de(t) == "nombre_sustancia", t


def test_nombres_de_fuente():
    for t in ("cochinilla", "achiote", "paprika", "jamaica", "espirulina",
              "extracto de betabel", "jugo de zanahoria", "concentrado de sauco"):
        assert forma_de(t) == "nombre_fuente", t


def test_trampas_del_dominio():
    # las trampas de nombre siguen siendo nombres de sustancia, no de fuente:
    # "rojo cochinilla a" es E124 sintetico y NO debe leerse como fuente
    assert forma_de("rojo cochinilla a") == "nombre_sustancia"
    assert forma_de("carmin de indigo") == "nombre_sustancia"
    # pero "carmin de cochinilla" si nombra la fuente
    assert forma_de("carmin de cochinilla") == "nombre_fuente"
