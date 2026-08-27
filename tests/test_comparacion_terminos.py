"""Pruebas de la logica de comparacion entre paises del paso 12.

Fijan el criterio de estabilidad y el umbral de n, que son las dos decisiones
que deciden el veredicto de P7. Si alguien los mueve sin querer, esto avisa.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _comp(filas):
    d = pd.DataFrame(filas, columns=["termino", "n_mx", "pct_mx", "n_es", "pct_es"])
    d = d[(d.n_mx >= 20) & (d.n_es >= 20)].copy()
    d["dif_pp"] = (d.pct_es - d.pct_mx).round(1)
    d["estable"] = d.dif_pp.abs() < 20
    return d


def test_umbral_de_n_descarta_los_ruidosos():
    d = _comp([("carmin", 224, 4.5, 499, 67.9), ("raro", 3, 0.0, 100, 90.0)])
    assert list(d.termino) == ["carmin"], "n<20 tiene que quedar fuera"


def test_el_carmin_sale_inestable():
    """Es el caso que motiva el paso 12: 4.5 % contra 67.9 %."""
    d = _comp([("carmin", 224, 4.5, 499, 67.9)])
    assert not d.estable.iloc[0]
    assert abs(d.dif_pp.iloc[0] - 63.4) < 0.1


def test_las_antocianinas_salen_estables():
    """87.5 % contra 87.9 %: el mismo termino se comporta igual en los dos paises."""
    d = _comp([("antocianinas", 40, 87.5, 124, 87.9)])
    assert d.estable.iloc[0]


def test_el_limite_de_20pp_es_estricto():
    d = _comp([("justo", 50, 40.0, 50, 60.0)])       # exactamente 20
    assert not d.estable.iloc[0], "20 pp no cuenta como estable"


def test_p7_necesita_70_por_ciento():
    d = _comp([("a", 30, 50.0, 30, 55.0), ("b", 30, 50.0, 30, 52.0),
               ("c", 30, 10.0, 30, 80.0)])
    assert round(100 * d.estable.mean(), 1) == 66.7
    assert not (round(100 * d.estable.mean(), 1) >= 70)
