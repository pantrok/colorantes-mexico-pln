# Datos externos

## Taxonomías de Open Food Facts

Necesarias para `src/08_vocabulario_off.py`. **Las tres**, no solo la primera:

    B=https://raw.githubusercontent.com/openfoodfacts/openfoodfacts-server/main/taxonomies
    curl -sL $B/additives.txt -o datos/externo/additives.txt
    curl -sL $B/vitamins.txt  -o datos/externo/vitamins.txt
    curl -sL $B/minerals.txt  -o datos/externo/minerals.txt

`vitamins.txt` y `minerals.txt` son las que faltaban en la corrida anterior. Sin
ellas el mecanismo M3 no se evalúa: Open Food Facts saca las vitaminas y los
minerales de `additives_tags` por diseño, así que E101 riboflavina y E170
carbonato de calcio aparecen como «omitidos» cuando en realidad están
etiquetados en otro campo, y bajo su nombre en inglés, no bajo su código E.

Anota el commit exacto de cada una en `reportes/procedencia.json`:

    for f in additives vitamins minerals; do
      curl -s "https://api.github.com/repos/openfoodfacts/openfoodfacts-server/commits?path=taxonomies/$f.txt&per_page=1" \
        | python -c "import sys,json;d=json.load(sys.stdin)[0];print('$f', d['sha'], d['commit']['committer']['date'])"
    done

Referencia verificada el 25 de agosto de 2026: `additives.txt` en
`76f4f43b6052835eeff822efddb0b0f37dd9a13f`, 659 entradas, 629 con traducción al
español según la corrida del 27, 45 con `mandatory_additive_class`.

**No actualices las taxonomías a mitad del análisis.** Cambian, y el resultado
depende de la versión. Si alguien reejecuta después con otra y obtiene otra
cifra, eso no es un error: es el objeto de estudio moviéndose, pero hay que
poder decir contra qué versión se midió.

Licencia: los datos de Open Food Facts son ODbL. Aplica la cláusula de
atribución compartida, igual que al volcado de productos.
