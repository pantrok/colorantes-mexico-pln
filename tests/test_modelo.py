"""Pruebas del ajuste de Firth.

Fijan dos cosas: que bajo separacion perfecta devuelva estimacion FINITA (que es
la razon de existir del metodo), y que cuando no hay separacion coincida con la
maxima verosimilitud ordinaria hasta la primera decimal de la razon de momios.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modelo import firth, separacion


def _celdas_reales():
    return pd.DataFrame([
        ("sint", 1, 0, 2192, 526), ("sint", 0, 0, 381, 340),
        ("nat", 1, 0, 145, 104), ("nat", 1, 1, 11, 11),
        ("nat", 0, 0, 170, 163), ("nat", 0, 1, 63, 63),
    ], columns=["clase", "vocab", "mand", "n", "sin"])


def test_estimacion_finita_bajo_separacion():
    d = _celdas_reales()
    X = pd.DataFrame({"natural": (d.clase == "nat").astype(int),
                      "fuera_vocab": 1 - d.vocab, "mandatory": d["mand"]})
    t = firth(X, d["sin"].values, d.n.values)
    fila = t[t.termino == "mandatory"].iloc[0]
    assert np.isfinite(fila.OR) and fila.OR > 1, "mandatory debe quedar finito y positivo"
    assert fila.IC_bajo is not None and fila.IC_bajo > 1


def test_no_distorsiona_los_terminos_bien_identificados():
    """natural y fuera_vocab no tienen separacion: Firth casi no los mueve
    respecto a los valores de maxima verosimilitud de la corrida del 27."""
    d = _celdas_reales()
    X = pd.DataFrame({"natural": (d.clase == "nat").astype(int),
                      "fuera_vocab": 1 - d.vocab, "mandatory": d["mand"]})
    t = firth(X, d["sin"].values, d.n.values).set_index("termino")
    assert abs(t.loc["natural", "OR"] - 7.0) < 0.5
    assert abs(t.loc["fuera_vocab", "OR"] - 23.4) < 1.0


def test_detecta_la_separacion():
    d = _celdas_reales()
    d = d.assign(mandatory=d["mand"])
    avisos = separacion(d, "sin", "n", ["mandatory"])
    assert any(a["valor"] == 1 and a["tasa"] == 1.0 for a in avisos)


def test_sin_separacion_coincide_con_maxima_verosimilitud():
    d = pd.DataFrame([(1, 1000, 300), (0, 1000, 150)], columns=["x", "n", "y"])
    t = firth(pd.DataFrame({"x": d.x}), d.y.values, d.n.values).set_index("termino")
    esperado = (300 / 700) / (150 / 850)      # razon de momios cruda
    assert abs(t.loc["x", "OR"] - esperado) < 0.05
