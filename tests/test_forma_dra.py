"""Pruebas del parche 17: la clasificacion ciega de la coautora.

Fijan que la incorporacion de sus etiquetas es fiel a lo que ella entrego
-nueve diferencias y ni una mas-, que la errata de transcripcion se
normaliza, y que una categoria en separacion perfecta se reporta como no
estimable en vez de imprimir una razon de momios de catorce cifras.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_spec = importlib.util.spec_from_file_location(
    "p17", Path(__file__).resolve().parents[1] / "src" / "17_forma_dra.py")
p17 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p17)
p16 = p17.p16
p15 = p16.p15


def test_solo_hay_nueve_diferencias_con_la_dra():
    assert len(p17.FORMA_DRA_DIFERENCIAS) == 9


def test_la_dra_coincide_en_188_de_197():
    ordenados = p15.terminos_ordenados(p15.cargar_diccionario())
    vocab, _ = p15.leer_taxonomia_off(p15.EXTERNO / "additives.txt")
    tabla = p17.tabla_tres_clasificadores(ordenados, vocab)
    assert len(tabla) == 197
    assert int(tabla.coinciden_v2_y_dra.sum()) == 188


def test_los_carotenoides_pasan_a_nombre_tecnico():
    """Su regla: el termino nombra la molecula, no el organismo."""
    for t in ("caroteno", "carotenos", "beta caroteno", "betacaroteno",
              "carotenos mixtos", "caroteno natural", "extracto de betalaina"):
        assert p17.forma_dra(t, "nombre_comun_planta") == "nombre_tecnico", t


def test_la_errata_espiriulina_se_normaliza():
    """En el archivo que se le mando decia `espiriulina`. Su respuesta fue
    nombre de la fuente, igual que forma_v2, asi que al normalizar no debe
    aparecer como desacuerdo."""
    assert p17.forma_dra("espiriulina", "nombre_comun_planta") == "nombre_comun_planta"
    assert p17.forma_dra("espirulina", "nombre_comun_planta") == "nombre_comun_planta"


def test_anaranjado_3_va_con_sus_hermanos():
    assert p17.forma_fina_corregida("anaranjado 3") == "indice_de_color"
    assert p17.forma_fina_corregida("anaranjado alimentos 6") == "indice_de_color"
    assert p17.forma_v2_corregida("anaranjado 3") == "numero_codigo"
    # y coincide con lo que dijo la Dra. por su cuenta
    assert p17.FORMA_DRA_DIFERENCIAS["anaranjado 3"] == "numero_codigo"


def test_separacion_no_imprime_una_razon_de_momios_absurda():
    """Con |coef| enorme el IC no es un intervalo y la RM no es una
    estimacion: las dos tienen que salir como no estimables."""
    assert p16.ic_wald(35.0, 500.0) == [None, None]
    assert p16.ic_wald(2.0, float("nan")) == [None, None]
    # un caso normal si devuelve intervalo
    lo, hi = p16.ic_wald(0.5, 0.2)
    assert lo is not None and hi is not None and lo < np.exp(0.5) < hi
