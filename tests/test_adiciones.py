"""Pruebas de las adiciones oficiales.

Fijan las trampas que introduce la nomenclatura mexicana. Si alguien reordena el
diccionario o toca el emparejador, estas pruebas avisan.
"""
import re
import sys
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))


def norma(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def cargar():
    return yaml.safe_load((RAIZ / "config" / "colorantes_adiciones.yaml")
                          .read_text(encoding="utf-8"))


def indice(a):
    return {norma(t): (cod, bloque)
            for bloque in ("sinteticos", "naturales", "minerales")
            for cod, v in (a.get(bloque) or {}).items()
            for t in (v if isinstance(v, list) else v.get("terminos", []))}


def test_azules_no_invertidos():
    """La numeracion mexicana va al reves de la FD&C. Si alguien la 'corrige'
    guiandose por el nombre, invierte los dos azules."""
    i = indice(cargar())
    assert i["azul alimentos 1"][0] == "E132", "azul alimentos 1 es INDIGOTINA"
    assert i["azul alimentos 2"][0] == "E133", "azul alimentos 2 es AZUL BRILLANTE"


def test_beta_caroteno_sintetico_es_sintetico():
    """Los 10 productos que lo declaran se contaban como natural."""
    i = indice(cargar())
    cod, bloque = i["beta caroteno sintetico"]
    assert bloque == "sinteticos" and cod == "E160a-i"


def test_el_sintetico_gana_por_longitud():
    """El emparejador ordena de termino mas largo a mas corto y consume el
    texto. «beta caroteno sintetico» tiene que ser mas largo que «beta caroteno»
    para que la trampa se resuelva sola."""
    assert len("beta caroteno sintetico") > len("beta caroteno")
    assert len("azafran indio") > len("azafran")


def test_azafran_exige_contexto():
    a = cargar()
    assert a["naturales"]["E164"].get("requiere_contexto") is True


def test_anaranjado_alimentos_5_queda_fuera():
    """La ley lo da como sinonimo de la entrada sintetica Y de la natural.
    Asignarlo a cualquiera de las dos seria inventar."""
    a = cargar()
    assert "anaranjado alimentos 5" in a["excluidas"]
    assert "anaranjado alimentos 5" not in indice(a)


def test_sin_duplicados_entre_bloques():
    a = cargar()
    vistos = []
    for bloque in ("sinteticos", "naturales", "minerales"):
        for v in (a.get(bloque) or {}).values():
            vistos += [norma(t) for t in
                       (v if isinstance(v, list) else v.get("terminos", []))]
    assert len(vistos) == len(set(vistos)), "hay terminos repetidos"
