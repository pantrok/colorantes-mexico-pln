"""Pruebas de quitar_advertencia_trazas (parche 14, 05/09/2026).

Fija el comportamiento que corrige el falso positivo de la anotacion: 13 de
600 productos de la muestra anotada declaraban un colorante SOLO dentro de
una advertencia de trazas ("puede contener... amarillo 5") y el flujo los
contaba como deteccion real. Ver util.py::quitar_advertencia_trazas y
BITACORA_PARCHES.md.

    pytest -q
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from util import normalizar, quitar_advertencia_trazas


def test_colorante_solo_en_advertencia_no_cuenta():
    """Caso real, 7501030421313: el colorante solo aparece tras 'puede
    contener'. Debe desaparecer del texto para detectar."""
    texto = normalizar(
        "Piel de cerdo, sal yodada, aceite vegetal. "
        "Puede contener: soya, leche, gluten, amarillo 5.")
    texto_det, roto = quitar_advertencia_trazas(texto)
    assert not roto
    assert "amarillo 5" not in texto_det


def test_colorante_antes_y_dentro_de_la_advertencia_cuenta_una_vez():
    """Si el colorante aparece ANTES del marcador ademas de dentro, sigue
    contando: el tramo anterior al marcador no se toca."""
    texto = normalizar(
        "Agua, azucar, colorante amarillo 5, acido citrico. "
        "Puede contener trazas de amarillo 5 y soya.")
    texto_det, roto = quitar_advertencia_trazas(texto)
    assert not roto
    assert "amarillo 5" in texto_det
    # solo debe quedar la mencion de antes del marcador, no las dos
    assert texto_det.count("amarillo 5") == 1


def test_contiene_no_es_marcador_de_advertencia():
    """'CONTIENE:' es la declaracion obligatoria de alergenos -el producto SI
    los lleva-, no una advertencia de trazas. No debe recortar nada."""
    texto = normalizar(
        "Leche parcialmente descremada, azucar. Contiene: leche, tartrazina.")
    texto_det, roto = quitar_advertencia_trazas(texto)
    assert not roto
    assert texto_det == texto
    assert "tartrazina" in texto_det


def test_marcador_muy_al_principio_se_marca_como_texto_roto():
    """Caso real, 7500525199010 (OCR revuelto): el marcador aparece en la
    posicion 0. No se recorta -se perderia la lista de ingredientes real- y
    se marca texto_roto=True para revision aparte."""
    texto = normalizar(
        "PUEDE CONTENER: TRAZAS ingredientes: harina de trigo, "
        "colorante amarillo 5, sal yodada")
    texto_det, roto = quitar_advertencia_trazas(texto)
    assert roto
    assert texto_det == texto
    assert "amarillo 5" in texto_det


def test_sin_marcador_no_cambia_nada():
    texto = normalizar("Agua, azucar, acido citrico, tartrazina")
    texto_det, roto = quitar_advertencia_trazas(texto)
    assert not roto
    assert texto_det == texto
