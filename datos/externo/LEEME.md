# Datos externos

Aquí va material que **no** es nuestro y que hay que versionar por referencia,
no por copia ciega.

## `additives.txt` — taxonomía de aditivos de Open Food Facts

Necesaria para `src/08_vocabulario_off.py`. Descarga:

    curl -sL https://raw.githubusercontent.com/openfoodfacts/openfoodfacts-server/main/taxonomies/additives.txt \
         -o datos/externo/additives.txt

Anota en `reportes/procedencia.json` el **commit exacto**, no la rama:

    curl -s https://api.github.com/repos/openfoodfacts/openfoodfacts-server/commits?path=taxonomies/additives.txt\&per_page=1 \
      | python -c "import sys,json; d=json.load(sys.stdin)[0]; print(d['sha'], d['commit']['committer']['date'])"

Referencia verificada el 25 de agosto de 2026:
`76f4f43b6052835eeff822efddb0b0f37dd9a13f`, 659 entradas, 631 con traducción al
español, 45 con `mandatory_additive_class`.

**La taxonomía cambia.** Los resultados del script 08 dependen de la versión.
No la actualices a mitad del análisis: si alguien reejecuta después con otra
versión y obtiene otra cifra, eso no es un error, es el objeto de estudio
moviéndose — pero hay que poder decir contra qué versión se midió.

Licencia de la taxonomía: los datos de Open Food Facts son ODbL. Aplica la
cláusula de atribución compartida, igual que al volcado de productos.
