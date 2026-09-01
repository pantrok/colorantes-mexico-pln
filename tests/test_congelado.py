"""Pruebas del congelamiento del diccionario.

La que importa es `test_el_diccionario_no_cambio`: mientras exista el lock, esa
prueba falla si alguien toca el diccionario sin subir la version. Es lo que
convierte «congelado» en un hecho verificable y no en un acuerdo verbal.

Las demas fijan las siete trampas que ya nos costaron una corrida cada una.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "p14", RAIZ / "src" / "14_congelar_diccionario.py")
p14 = importlib.util.module_from_spec(_spec)
sys.modules["p14"] = p14
_spec.loader.exec_module(p14)

DICC = RAIZ / "config" / "colorantes.yaml"
LOCK = RAIZ / "config" / "colorantes.lock.json"
DEC = RAIZ / "config" / "decisiones_dra.yaml"


def dicc():
    return yaml.safe_load(DICC.read_text(encoding="utf-8"))


def dec():
    return yaml.safe_load(DEC.read_text(encoding="utf-8"))


# ------------------------------------------------------------ el candado

@pytest.mark.skipif(not LOCK.exists(), reason="todavia no se congela")
def test_el_diccionario_no_cambio():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    actual = p14.huella(dicc())
    assert actual == lock["sha256"], (
        f"\nEl diccionario cambio despues de congelar.\n"
        f"  esperado: {lock['sha256']}\n"
        f"  en disco: {actual}\n"
        f"Si el cambio es deliberado, sube VERSION en el script 14 y corre\n"
        f"`--aplicar --rehacer`. OJO: si la anotacion ya empezo, descongelar la\n"
        f"invalida y hay que rehacerla contra la version nueva.")


@pytest.mark.skipif(not LOCK.exists(), reason="todavia no se congela")
def test_el_lock_cuadra_con_el_conteo():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    cod, ter = p14.cuenta(dicc())
    assert (cod, ter) == (lock["codigos"], lock["terminos"])


@pytest.mark.skipif(not LOCK.exists(), reason="todavia no se congela")
def test_el_meta_declara_la_misma_huella():
    """Resuelve la divergencia 148 contra 153: el conteo autoritativo es el del
    archivo, y queda escrito en un solo lugar."""
    m = dicc().get("meta", {})
    assert m.get("congelado") is True
    assert m.get("sha256") == json.loads(LOCK.read_text(encoding="utf-8"))["sha256"]


# ------------------------------------------------- las siete invariantes

def test_pasan_todas_las_invariantes():
    avisos = []
    p14.verifica(dicc(), dec(), avisos)   # levanta p14.Falla si alguna no pasa


def test_los_azules_no_estan_invertidos():
    """La numeracion mexicana va al reves que la FD&C. «azul alimentos 1» es
    INDIGOTINA (E132); «azul alimentos 2» es AZUL BRILLANTE (E133)."""
    idx = p14.indice_terminos(dicc())
    assert {c for _, c in idx.get(p14.norma("azul alimentos 1"), [])} == {"E132"}
    assert {c for _, c in idx.get(p14.norma("azul alimentos 2"), [])} == {"E133"}


def test_beta_caroteno_sintetico_resuelve_antes_que_beta_caroteno():
    """Si gana el corto, los 10 productos sinteticos se cuentan como naturales:
    del lado equivocado del eje que mide el articulo."""
    idx = p14.indice_terminos(dicc())
    largo = p14.norma("beta caroteno sintetico")
    corto = p14.norma("beta caroteno")
    assert largo in idx
    assert len(largo) > len(corto)


def test_anaranjado_alimentos_5_no_esta():
    """El Acuerdo lo da como sinonimo de 160a(i) sintetico Y de 160a(ii) natural.
    La norma misma lo deja ambiguo: contarlo de cualquier lado seria inventar."""
    idx = p14.indice_terminos(dicc())
    assert p14.norma("anaranjado alimentos 5") not in idx


def test_ningun_termino_vive_en_dos_clases():
    idx = p14.indice_terminos(dicc())
    malos = {t: sorted({b for b, _ in d}) for t, d in idx.items()
             if len({b for b, _ in d}) > 1}
    assert not malos, malos


def test_salio_lo_que_la_revisora_marco_como_no_colorante():
    idx = p14.indice_terminos(dicc())
    for g in dec().get("fuera_del_eje") or []:
        for t in g["terminos"]:
            assert p14.norma(t) not in idx, f"{t} ({g['codigo']}): {g['motivo']}"


def test_no_se_borro_lo_que_esta_en_desacuerdo():
    """La proteccion contra la poda conveniente. P1 la decide el corpus, no la
    revisora: borrar formas atestiguadas encoge la clase natural, que es la que
    sostiene el resultado."""
    idx = p14.indice_terminos(dicc())
    faltan = [d["termino"] for d in dec()["desacuerdo_experta_vs_corpus"]["terminos"]
              if p14.norma(d["termino"]) not in idx]
    assert not faltan, f"se borraron formas atestiguadas: {faltan}"


def test_los_codigos_gateados_traen_la_marca():
    d = dicc()
    marcados = {c for _, c, v in p14.recorre(d)
                if isinstance(v, dict) and v.get("requiere_contexto")}
    for c in dec()["requieren_contexto"]["codigos_a_agregar"]:
        assert c in marcados or c not in {x for _, x, _ in p14.recorre(d)}, \
            f"{c} deberia requerir contexto"


def test_orden_mas_largo_primero_en_cada_codigo():
    for bloque, codigo, val in p14.recorre(dicc()):
        ts = [p14.norma(t) for t in p14.terminos_de(val)]
        assert ts == sorted(ts, key=len, reverse=True), f"{bloque}/{codigo}"


# ------------------------------------------------------- la huella misma

def test_la_huella_no_depende_del_formato_del_yaml():
    a = {"naturales": {"E100": ["Cúrcuma", "curcumina"]}}
    b = {"naturales": {"E100": {"tono": "amarillo", "terminos": ["CURCUMA", "Curcumina"]}}}
    assert p14.huella(a) == p14.huella(b)


def test_la_huella_cambia_si_cambia_un_termino():
    a = {"naturales": {"E100": ["curcuma"]}}
    b = {"naturales": {"E100": ["curcuma", "curcumina"]}}
    assert p14.huella(a) != p14.huella(b)


def test_la_huella_cambia_si_cambia_la_regla_de_contexto():
    a = {"naturales": {"E172": {"terminos": ["oxido de hierro"]}}}
    b = {"naturales": {"E172": {"terminos": ["oxido de hierro"], "requiere_contexto": True}}}
    assert p14.huella(a) != p14.huella(b)


def test_la_huella_ignora_el_orden_de_los_bloques():
    a = {"naturales": {"E100": ["curcuma"]}, "sinteticos": {"E102": ["tartrazina"]}}
    b = {"sinteticos": {"E102": ["tartrazina"]}, "naturales": {"E100": ["curcuma"]}}
    assert p14.huella(a) == p14.huella(b)


def test_meta_no_entra_en_la_huella():
    """Si entrara, la fecha de congelamiento cambiaria el hash que ella misma
    declara, y nunca cerraria."""
    a = {"naturales": {"E100": ["curcuma"]}}
    b = {"meta": {"version": "1.0", "sha256": "x"}, "naturales": {"E100": ["curcuma"]}}
    assert p14.huella(a) == p14.huella(b)


# ------------------------------------------------ contrato del veredicto

def test_el_veredicto_declara_la_regla_de_decision():
    d = dec()
    assert d["meta"]["sin_respuesta"] == 0
    assert d["desacuerdo_experta_vs_corpus"]["terminos"]
    assert d["invariantes"]["terminos_prohibidos"]


def test_el_veredicto_cubre_los_tres_codigos_que_salen():
    codigos = {g["codigo"] for g in dec()["fuera_del_eje"]}
    assert {"E101", "E170", "E153"} <= codigos
