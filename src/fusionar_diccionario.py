"""Fusiona config/colorantes_adiciones.yaml en config/colorantes.yaml.

    python src/fusionar_diccionario.py            # simulacro, no escribe
    python src/fusionar_diccionario.py --aplicar  # escribe, con respaldo

NO reemplaza el diccionario: lo amplia. Antes de escribir deja
`config/colorantes.yaml.bak-<fecha>` y reporta termino por termino que se
anadio, que se ignoro por duplicado y que bloques se crearon.

Se hace asi, y no reescribiendo el YAML, porque el diccionario es el
instrumento del articulo: tiene que poder auditarse el antes y el despues.

DESPUES DE APLICAR hay que hacer dos cosas a mano:

  1. Anadir E164 a `REQUIEREN_CONTEXTO` en src/util.py. «azafran» a secas es
     especia antes que colorante y sin contexto va a dar falsos positivos.

  2. Volver a correr TODA la tuberia. El universo cambia, asi que la muestra de
     anotacion de los 600 hay que sortearla de nuevo. No empezar a anotar antes.
"""
from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "config" / "colorantes.yaml"
ADIC = RAIZ / "config" / "colorantes_adiciones.yaml"
# donde vive cada bloque de las adiciones dentro del YAML base
DESTINO = {"sinteticos": "sinteticos", "naturales": "naturales", "minerales": "naturales"}


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="escribe los cambios")
    args = ap.parse_args()

    if not BASE.exists() or not ADIC.exists():
        raise SystemExit(f"Falta {BASE if not BASE.exists() else ADIC}")
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    adic = yaml.safe_load(ADIC.read_text(encoding="utf-8"))

    existentes = {norma(t) for b in ("sinteticos", "naturales", "fuera_de_eje")
                  for info in (base.get(b) or {}).values()
                  for t in info.get("terminos", [])}

    anadidos, duplicados, nuevos_codigos = [], [], []
    for bloque, destino in DESTINO.items():
        for codigo, valor in (adic.get(bloque) or {}).items():
            terminos = valor if isinstance(valor, list) else valor.get("terminos", [])
            base.setdefault(destino, {})
            if codigo not in base[destino]:
                if isinstance(valor, dict):
                    base[destino][codigo] = {k: v for k, v in valor.items()
                                             if k != "terminos"}
                    base[destino][codigo]["terminos"] = []
                else:
                    base[destino][codigo] = {"terminos": []}
                nuevos_codigos.append(f"{codigo} -> {destino}")
            base[destino][codigo].setdefault("terminos", [])
            for t in terminos:
                if norma(t) in existentes:
                    duplicados.append(f"{codigo}: {t}")
                else:
                    base[destino][codigo]["terminos"].append(t)
                    existentes.add(norma(t))
                    anadidos.append(f"{codigo}: {t}")

    print(f"  codigos nuevos ({len(nuevos_codigos)}):")
    for x in nuevos_codigos:
        print(f"    {x}")
    print(f"\n  terminos anadidos ({len(anadidos)}):")
    for x in anadidos:
        print(f"    {x}")
    if duplicados:
        print(f"\n  ignorados por duplicado ({len(duplicados)}):")
        for x in duplicados:
            print(f"    {x}")
    if adic.get("excluidas"):
        print(f"\n  excluidas a proposito ({len(adic['excluidas'])}): "
              + ", ".join(adic["excluidas"]))

    if not args.aplicar:
        print("\n  SIMULACRO. Nada se escribio. Vuelve a correr con --aplicar.")
        return

    resp = BASE.with_suffix(f".yaml.bak-{date.today().isoformat()}")
    shutil.copy2(BASE, resp)
    base.setdefault("meta", {})
    base["meta"]["fusion_acuerdo"] = adic["meta"]["fecha"]
    with open(BASE, "w", encoding="utf-8") as f:
        yaml.safe_dump(base, f, allow_unicode=True, sort_keys=False, width=100)
    print(f"\n  respaldo -> {resp.name}")
    print(f"  escrito  -> {BASE.name}")
    print("\n  FALTA A MANO: anadir 'E164' a REQUIEREN_CONTEXTO en src/util.py")
    print("  Y volver a correr toda la tuberia: el universo cambio.")


if __name__ == "__main__":
    main()
