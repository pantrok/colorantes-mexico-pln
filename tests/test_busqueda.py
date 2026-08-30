"""Pruebas del paso 13 v2.

Lo que se fija aqui es la VERIFICACION POSTERIOR, que es el arreglo de fondo:
no depende de que la API se porte bien, asi que si el buscador trae ruido el
filtro lo tira. Si alguien la afloja, estas pruebas avisan.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "p13", RAIZ / "src" / "13_buscar_antecedentes.py")
p13 = importlib.util.module_from_spec(_spec)
sys.modules["p13"] = p13
_spec.loader.exec_module(p13)


def fila(titulo, resumen=""):
    return {"titulo": titulo, "resumen": resumen}


def test_tira_el_ruido_que_hundio_el_bloque_D():
    """Caso real de la corrida del 27: la consulta «Open Food Facts Mexico»
    devolvio pulque y plantas medicinales porque el buscador solo engancho
    «Mexico»."""
    regla = {"requiere_alguno": ["open food facts", "openfoodfacts"]}
    ruido = fila("Plantas medicinales para los nervios en Mexico",
                 "Estudio etnobotanico en comunidades de Oaxaca")
    bueno = fila("Food additives in 126,000 products",
                 "We used the Open Food Facts database to characterise additives")
    assert not p13.confirma(ruido, regla)
    assert p13.confirma(bueno, regla)


def test_requiere_todos_exige_cada_uno():
    regla = {"requiere_todos": ["colorante", "mexico"]}
    assert p13.confirma(fila("Colorantes en alimentos de Mexico"), regla)
    assert not p13.confirma(fila("Colorantes en alimentos de Chile"), regla)


def test_requiere_alguno_basta_con_uno():
    regla = {"requiere_alguno": ["mexico", "mexicano"]}
    assert p13.confirma(fila("Etiquetado mexicano de aditivos"), regla)
    assert not p13.confirma(fila("Food labelling in Canada"), regla)


def test_combina_las_dos_reglas():
    regla = {"requiere_todos": ["colorante"], "requiere_alguno": ["mexico", "chile"]}
    assert p13.confirma(fila("Colorantes en Chile"), regla)
    assert not p13.confirma(fila("Aditivos en Chile"), regla)      # falta colorante
    assert not p13.confirma(fila("Colorantes en Peru"), regla)     # falta pais


def test_sin_reglas_todo_pasa():
    assert p13.confirma(fila("Cualquier cosa"), {})


def test_ignora_acentos_y_mayusculas():
    regla = {"requiere_todos": ["curcuma"]}
    assert p13.confirma(fila("La CÚRCUMA como colorante"), regla)


def test_busca_tambien_en_el_resumen():
    regla = {"requiere_todos": ["openfoodfacts"]}
    assert p13.confirma(fila("Un titulo cualquiera", "datos de openfoodfacts"), regla)


def test_el_yaml_declara_reglas_en_todas_las_consultas():
    """Una consulta sin reglas no filtra nada y reintroduce el problema."""
    cfg = yaml.safe_load((RAIZ / "config" / "busqueda_antecedentes.yaml")
                         .read_text(encoding="utf-8"))
    for nombre, b in cfg["bloques"].items():
        for c in b["consultas"]:
            assert c.get("requiere_todos") or c.get("requiere_alguno"), \
                f"{nombre}: «{c['q'].strip()}» no exige nada"


def test_el_bloque_D_ya_no_dice_mexico():
    """Esa palabra secuestraba el emparejamiento en un corpus mundial."""
    cfg = yaml.safe_load((RAIZ / "config" / "busqueda_antecedentes.yaml")
                         .read_text(encoding="utf-8"))
    for c in cfg["bloques"]["D_calidad_open_food_facts"]["consultas"]:
        assert "mexico" not in c["q"].lower()


def test_resumen_invertido_se_reconstruye_en_orden():
    inv = {"Los": [0], "colorantes": [1], "son": [2], "caros": [3]}
    assert p13.texto_de_abstract(inv) == "Los colorantes son caros"


def test_ris_incluye_doi_y_tolera_anio_faltante():
    df = pd.DataFrame([{"titulo": "Con DOI", "anio": 2024, "revista": "Rev",
                        "doi": "10.1/x", "bloque": "A"},
                       {"titulo": "Sin anio", "anio": float("nan"), "revista": "",
                        "doi": "", "bloque": "B"}])
    ris = p13.a_ris(df)
    assert "DO  - 10.1/x" in ris and ris.count("TY  - JOUR") == 2
    assert ris.count("PY  -") == 1
