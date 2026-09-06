"""Pruebas del diccionario de colorantes.

Las dos primeras son las trampas del dominio y son la razon de que el orden de
emparejamiento sea por termino y no por sustancia. Si estas fallan, el conteo de
sinteticos frente a naturales sale mal y con el todo el articulo.

    pytest -q
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from util import (cargar_diccionario, construir_matchers, detectar, normalizar,
                  terminos_ordenados)

DIC = cargar_diccionario()
MATCHERS = construir_matchers(DIC)


def detectados(texto: str) -> set[str]:
    return set(detectar(normalizar(texto), MATCHERS))


CASOS = [
    # --- trampas ---
    ("Agua, azucar, acido citrico, ROJO COCHINILLA A, benzoato de sodio", {"E124"}),
    ("Colorantes: carmin de indigo y azul brillante", {"E132", "E133"}),
    # --- declaracion por nombre de compuesto, que es como se etiqueta en Mexico ---
    ("Extracto de betalaina, acido carminico", {"E162", "E120"}),
    ("Colorante: cochinilla (E-120)", {"E120"}),
    ("Jugo de betabel concentrado", {"E162"}),
    ("Betacaroteno, extracto de achiote, paprika", {"E160a", "E160b", "E160c"}),
    # --- nomenclatura estadounidense, comun en producto importado ---
    ("Contiene: Rojo No. 40, Amarillo 5, Azul 1", {"E129", "E102", "E133"}),
    # --- fuera del eje ---
    ("Agua carbonatada, color caramelo clase IV, cafeina", {"E150"}),
    # --- no debe inventar ---
    ("Agua, azucar, sal, conservador benzoato de sodio", set()),
]


@pytest.mark.parametrize("texto,esperado", CASOS)
def test_deteccion(texto, esperado):
    assert detectados(texto) == esperado


def test_orden_es_por_termino_no_por_sustancia():
    """Regresion: el termino mas largo del diccionario debe ir primero, sea de quien sea.

    Se comprueba sobre los terminos, no sobre los patrones: el escapado de regex
    altera las longitudes y haria la prueba inutil.
    """
    largos = [len(t) for t, _, _ in terminos_ordenados(DIC)]
    assert largos == sorted(largos, reverse=True)

    # El caso concreto que motivo el arreglo.
    orden = [t for t, _, _ in terminos_ordenados(DIC)]
    assert orden.index("rojo cochinilla a") < orden.index("cochinilla")
    assert orden.index("carmin de indigo") < orden.index("carmin")


def test_ambiguos_marcados():
    """Los codigos de origen indeterminado deben estar declarados como tales.

    E101 salio de esta lista al congelar el diccionario (parche 12/13, veredicto
    de la Dra. Granados-Balbuena del 01/09/2026): no es que su origen siga
    indeterminado, es que dejo de ser colorante -fortificacion con vitamina B2,
    no color- y salio del diccionario por completo. Ver
    config/decisiones_dra.yaml y config/DICCIONARIO_CONGELADO.md.
    """
    for codigo in ("E160a", "E140"):
        assert DIC["naturales"][codigo].get("origen_indeterminado") is True, codigo
    assert "E101" not in DIC["naturales"], "E140 y E160a siguen ambiguos; E101 ya no esta"


def test_carmin_se_reporta_aparte():
    assert DIC["naturales"]["E120"].get("reportar_aparte") is True


def test_caramelo_fuera_del_eje():
    assert "E150" in DIC["fuera_de_eje"]
    assert "E150" not in DIC["naturales"] and "E150" not in DIC["sinteticos"]


def test_normalizacion():
    assert normalizar("  Rojo  ALLURA (AC)  ") == "rojo allura ac"
    assert normalizar("Cúrcuma") == "curcuma"
    assert normalizar(None) == ""


def test_orden_de_terminos_es_determinista():
    """El orden de `terminos_ordenados` no puede depender del proceso.

    Antes lo hacia: `terminos_norm` se ordenaba con `key=len` sobre un SET, y
    el orden de iteracion de un set de cadenas depende de PYTHONHASHSEED, que
    Python aleatoriza en cada proceso. Como `sorted` es estable, los terminos
    de igual longitud salian en un orden distinto en cada corrida -los tres
    de E160b de 7 caracteres, por ejemplo- y eso movia el termino
    representante de cada deteccion y con el la RM del modelo de forma del
    nombre. Detectado en el parche 16.
    """
    orden = [t for t, _, _ in terminos_ordenados(cargar_diccionario())]
    # 1) longitud no creciente
    assert all(len(a) >= len(b) for a, b in zip(orden, orden[1:]))
    # 2) dentro de cada longitud, alfabetico: eso es lo que fija el desempate
    for largo in {len(t) for t in orden}:
        iguales = [t for t in orden if len(t) == largo]
        assert iguales == sorted(iguales), f"empate no determinista en longitud {largo}"


def test_orden_estable_entre_cargas_del_diccionario():
    """Dos cargas independientes dentro del mismo proceso tienen que dar el
    mismo orden. La prueba entre PROCESOS distintos la cubre el desempate
    alfabetico de arriba, que es una propiedad verificable sin relanzar."""
    a = [t for t, _, _ in terminos_ordenados(cargar_diccionario())]
    b = [t for t, _, _ in terminos_ordenados(cargar_diccionario())]
    assert a == b
