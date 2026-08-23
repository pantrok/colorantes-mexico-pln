# Colorantes naturales y sintéticos en el mercado alimentario mexicano

Análisis exploratorio previo a la planeación del manuscrito para **CienciaUAT**.

Todo el contexto del proyecto, las decisiones ya tomadas y lo que **no** hay que
hacer en esta fase está en **`CLAUDE.md`**. Léelo antes de correr nada.

## Uso

```bash
make entorno
source .venv/bin/activate

# 0. Introspecciona el esquema del volcado. Obligatorio: cambia entre versiones.
make esquema VOLCADO=datos/crudo/food.parquet

# 1-4. En orden de importancia.
make todo VOLCADO=datos/crudo/food.parquet
```

Las salidas quedan en `reportes/`.

## Los cuatro números

| Script | Pregunta | Decide |
|---|---|---|
| `02_brecha_tags.py` | ¿Cuántos colorantes nombrados en el texto no están en `additives_tags`? | El título y el encuadre |
| `03_cobertura_sesgo.py` | ¿Qué tan sesgado está el subconjunto? | El párrafo de limitaciones |
| `04_calidad_texto.py` | ¿Sirve `ingredients_text` para PLN? | Si el aporte metodológico es viable |
| `01_subconjunto_mx.py` | ¿Cuántos productos hay? | Prerrequisito |

## Datos

Volcado público de **Open Food Facts**, licencia **ODbL**: hay que citar la fuente
y respetar la cláusula de atribución compartida. La procedencia exacta del volcado
usado queda registrada en `reportes/procedencia.json`.

No se incluyen datos en el repositorio. `datos/` está en `.gitignore`.
