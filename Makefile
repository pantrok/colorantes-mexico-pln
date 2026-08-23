# Volcado de Open Food Facts. Sobrescribir con: make VOLCADO=ruta/al/food.parquet
VOLCADO ?= hf://datasets/openfoodfacts/product-database/food.parquet
PY = python

.PHONY: entorno esquema subconjunto brecha sesgo calidad todo limpiar

entorno:
	$(PY) -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	@echo "Listo. Activa con: source .venv/bin/activate"

esquema:       ; $(PY) src/00_explorar_esquema.py $(VOLCADO)
subconjunto:   ; $(PY) src/01_subconjunto_mx.py $(VOLCADO)
brecha:        ; $(PY) src/02_brecha_tags.py
sesgo:         ; $(PY) src/03_cobertura_sesgo.py
calidad:       ; $(PY) src/04_calidad_texto.py

# Orden de importancia: la brecha primero, decide el encuadre del articulo.
todo: subconjunto brecha calidad sesgo

pruebas:      ; $(PY) -m pytest tests/ -q

limpiar:       ; rm -rf datos/intermedio/* reportes/*
