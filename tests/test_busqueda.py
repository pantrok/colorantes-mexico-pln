"""Pruebas del paso 13 v3.

Lo que se fija aqui es que las EXIGENCIAS SALGAN DE LA CONSULTA. Ese fue el
agujero de la v2: la bitacora prometia una verificacion que el YAML no hacia,
porque sus reglas eran raices sueltas. Las pruebas de regresion de abajo llevan
los casos reales de la corrida del 29 de agosto.
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


def fila(titulo, resumen="", doi=""):
    return {"titulo": titulo, "resumen": resumen, "doi": doi}


def cfg():
    return yaml.safe_load((RAIZ / "config" / "busqueda_antecedentes.yaml")
                          .read_text(encoding="utf-8"))


# --------------------------------------------------- regresiones de la v2

def test_no_pasa_el_aditivo_para_leitoes():
    """Caso real. La consulta pedia «aditivos alimentarios» y «preenvasados»;
    la regla del YAML solo exigia la raiz «aditivo», asi que entro esto."""
    q = '"aditivos alimentarios" preenvasados'
    regla = {"requiere_todos": ["aditivo"]}
    ruido = fila("Aditivos fitogenicos e butirato de sodio como promotores de "
                 "crescimento de leitoes desmamados")
    assert p13.cumple_reglas_yaml(ruido, regla)          # la v2 lo confirmaba
    assert p13.clasifica(ruido, regla, q) == "laxo"      # la v3 no lo cuenta


def test_no_pasa_la_celda_solar():
    """Otro caso real: '"synthetic dyes" "packaged foods"' exigia solo «dye»."""
    q = '"synthetic dyes" "packaged foods"'
    regla = {"requiere_todos": ["dye"]}
    ruido = fila("Dye-sensitized solar cells with natural dyes extracted from "
                 "achiote seeds")
    assert p13.clasifica(ruido, regla, q) == "laxo"


def test_si_pasa_el_que_trae_las_dos_frases():
    q = '"synthetic dyes" "packaged foods"'
    regla = {"requiere_todos": ["dye"]}
    bueno = fila("All the colors of the rainbow",
                 "Prevalence of synthetic dyes in US packaged foods and beverages")
    assert p13.clasifica(bueno, regla, q) == "estricto"


def test_tira_el_ruido_que_hundio_el_bloque_D():
    q = 'Open Food Facts Mexico'
    regla = {"requiere_alguno": ["open food facts", "openfoodfacts"]}
    ruido = fila("Plantas medicinales para los nervios en Mexico",
                 "Estudio etnobotanico en comunidades de Oaxaca")
    assert p13.clasifica(ruido, regla, q) == "fuera"


# --------------------------------------------------- los tres cajones

def test_falla_la_regla_del_yaml_y_cae_fuera():
    q = '"food colorants" "packaged food"'
    regla = {"requiere_todos": ["colorant"]}
    assert p13.clasifica(fila("Sodio en alimentos"), regla, q) == "fuera"


def test_cumple_regla_pero_le_falta_la_frase_y_queda_laxo():
    q = '"food colorants" "packaged food"'
    regla = {"requiere_todos": ["colorant"]}
    f = fila("Anthocyanin food colorant in pH-responsive films")
    assert p13.clasifica(f, regla, q) == "laxo"


def test_las_frases_se_suman_no_sustituyen():
    """Si el YAML exige algo que la consulta no dice, se sigue exigiendo."""
    q = '"food additives"'
    regla = {"requiere_todos": ["mexico"]}
    assert p13.clasifica(fila("Food additives in Chile"), regla, q) == "fuera"
    assert p13.clasifica(fila("Food additives in Mexico"), regla, q) == "estricto"


def test_se_puede_volver_al_comportamiento_v2():
    q = '"aditivos alimentarios" preenvasados'
    regla = {"requiere_todos": ["aditivo"]}
    ruido = fila("Aditivos fitogenicos para leitoes")
    assert p13.clasifica(ruido, regla, q, usar_frases=False) == "estricto"


# --------------------------------------------------- normalizacion

def test_la_frase_con_guion_casa_igual():
    """«pre-packaged foods» normalizado deja doble espacio si no se aplana.
    Sin esto la consulta que busca a Chiu nunca confirmaria nada."""
    q = '"food colors" "pre-packaged foods"'
    regla = {}
    f = fila("Prevalence of food colors use in local and imported pre-packaged "
             "foods in Hong Kong")
    assert p13.clasifica(f, regla, q) == "estricto"


def test_ignora_acentos_y_mayusculas():
    assert p13.clasifica(fila("La CÚRCUMA como colorante"),
                         {"requiere_todos": ["curcuma"]}, "") == "estricto"


def test_busca_tambien_en_el_resumen():
    assert p13.clasifica(fila("Un titulo cualquiera", "datos de openfoodfacts"),
                         {}, 'openfoodfacts "openfoodfacts"') == "estricto"


def test_frases_de_extrae_solo_lo_entrecomillado():
    assert p13.frases_de('"food dyes" prevalence') == ["food dyes"]
    assert p13.frases_de('colorantes etiquetado Mexico') == []


def test_clave_doi_normaliza_prefijo_y_mayusculas():
    assert p13.clave_doi("https://doi.org/10.1108/BFJ-12-2023-1130") == \
        "10.1108/bfj-12-2023-1130"


# --------------------------------------------------- contrato del YAML

def test_el_yaml_declara_reglas_en_todas_las_consultas():
    for nombre, b in cfg()["bloques"].items():
        for c in b["consultas"]:
            assert c.get("requiere_todos") or c.get("requiere_alguno"), \
                f"{nombre}: «{c['q'].strip()}» no exige nada"


def test_el_bloque_D_ya_no_dice_mexico():
    for c in cfg()["bloques"]["D_calidad_open_food_facts"]["consultas"]:
        assert "mexico" not in c["q"].lower()


def test_el_control_de_recuperacion_existe_y_trae_doi():
    ctrl = cfg().get("control_recuperacion")
    assert ctrl and len(ctrl) >= 4
    for c in ctrl:
        assert c["doi"].startswith("10."), c


def test_hay_una_consulta_que_apunta_a_cada_blanco_no_recuperado():
    """Chiu y Tseng no salieron en la v2. Si alguien borra estas cadenas, el
    control de recuperacion vuelve a fallar y nadie sabe por que."""
    todas = " ".join(c["q"].lower()
                     for b in cfg()["bloques"].values() for c in b["consultas"])
    assert "pre-packaged foods" in todas          # Chiu
    assert "sensory-related industrial additives" in todas   # Tseng


# --------------------------------------------------- control y salidas

def test_control_distingue_donde_murio_cada_uno():
    conf = {"control_recuperacion": [
        {"etiqueta": "en corpus", "doi": "10.1/a"},
        {"etiqueta": "laxo", "doi": "10.1/b"},
        {"etiqueta": "descartado", "doi": "10.1/c"},
        {"etiqueta": "nunca vino", "doi": "10.1/d"}]}
    corpus = pd.DataFrame([{"doi": "10.1/A"}])
    estados = {c["etiqueta"]: c["estado"] for c in p13.revisa_control(
        conf, corpus, [{"doi": "10.1/b"}], [{"doi": "https://doi.org/10.1/C"}])}
    assert estados == {"en corpus": "en el corpus",
                       "laxo": "solo por revisar",
                       "descartado": "recuperado y descartado",
                       "nunca vino": "no recuperado"}


def test_ris_lleva_autores_resumen_y_no_trunca():
    df = pd.DataFrame([{"titulo": f"Trabajo {i}", "autores": "Perez, Ana; Li, Wei",
                        "anio": 2024, "revista": "Rev", "doi": f"10.1/{i}",
                        "url": "https://x", "idioma": "en",
                        "resumen": "Un resumen.", "bloque": "A"}
                       for i in range(250)])
    ris = p13.a_ris(df)
    assert ris.count("TY  - JOUR") == 250          # la v2 cortaba en 200
    assert "AU  - Perez, Ana" in ris and "AU  - Li, Wei" in ris
    assert "AB  - Un resumen." in ris


def test_ris_tolera_anio_y_autores_faltantes():
    df = pd.DataFrame([{"titulo": "Sin nada", "autores": "", "anio": float("nan"),
                        "revista": "", "doi": "", "url": "", "idioma": "",
                        "resumen": "", "bloque": "B"}])
    ris = p13.a_ris(df)
    assert ris.count("TY  - JOUR") == 1
    assert "AU  -" not in ris and "PY  -" not in ris


def test_resumen_invertido_se_reconstruye_en_orden():
    inv = {"Los": [0], "colorantes": [1], "son": [2], "caros": [3]}
    assert p13.texto_de_abstract(inv) == "Los colorantes son caros"
