# Bitácora de aplicación de parches

Este archivo existe por un problema concreto: quien genera el siguiente parche
(otra sesión de Claude Code, sin acceso a esta conversación) trabaja sobre su
propia copia del repositorio y no ve automáticamente qué se corrigió *al
aplicar* un parche aquí. Dos veces ya se ha repetido el mismo síntoma —el
parche 13 diagnosticó de nuevo, sin saberlo, un bug que ya se había corregido
al aplicar el parche 12, y preguntó explícitamente qué se había tocado en
local—. Este documento cierra ese hueco: por cada parche, qué se aplicó tal
cual y qué se tuvo que corregir aquí, con archivo y motivo, para que la
siguiente sesión pueda leer esto antes de escribir el siguiente parche y no
reabrir lo ya resuelto.

**Se actualiza después de cada parche aplicado.** Si estás generando el
próximo, léelo completo antes de tocar nada — es más rápido que reconstruirlo
del `git log`.

---

## Estado actual (después del parche 13)

- **Diccionario:** congelado, **v1.1**, `sha256: 8c7c8790221bf161dc1353282d1da34595a7176f9a4cf16046c22486e88e9640`
  (ver `config/colorantes.lock.json` y `config/DICCIONARIO_CONGELADO.md`).
  35 códigos, 202 términos.
- **Veredicto aplicado:** `config/decisiones_dra.yaml`, Dra. Sulem Yali
  Granados-Balbuena, 01/09/2026.
- **Fusión del Acuerdo (DOF):** aplicada (`config/colorantes_adiciones.yaml`
  vía `src/fusionar_diccionario.py --aplicar`).
- **Pendiente, sin empezar:** rehacer el flujo completo (01→12) contra el
  diccionario v1.1, decidir el tratamiento del dióxido de titanio (E171) antes
  del modelo de Firth, escribir el manual de anotación, sortear los 600 y
  anotar contra el hash de v1.1.
- **`config/acuerdo_colorantes.yaml`** (vocabulario legal de referencia): sin
  tocar desde el parche 6. No se congela ni se fusiona con el diccionario de
  detección; son cosas distintas a propósito.

---

## Respuesta directa a la pregunta del parche 13

> «Como sí corrió y sí escribió, alguien tuvo que parchear el script en local.
> Si Claude Code lo tocó, dime qué cambió.»

Sí. Al aplicar el parche 12, `14_congelar_diccionario.py` tronaba con
`TypeError: forma de codigo no reconocida: <class 'str'>` en el bloque
`sustituibilidad` (`regla`, `candidatos`, `notas`, no términos), exactamente
como diagnosticó el parche 13. Se corrigió con una lista explícita de bloques
a excluir (`BLOQUES_NO_CODIGO = ("meta", "genericos", "sustituibilidad")`) en
`recorre()` y en el bucle de `aplica()` que borra códigos vacíos — más
frágil que el `es_mapa_de_codigos()` estructural del parche 13, pero
suficiente para que el 1.0 congelara. El parche 13 lo reemplazó por completo;
esa corrección local ya no existe en el árbol.

Además, antes de congelar la v1.0 se detectó y se dejó **sin corregir a
propósito** que `lactoflavina`, `vitamina b-2` y `carbon medicinal`
sobrevivían con el mismo motivo que sus pares ya retirados — se le preguntó al
usuario y se decidió congelar tal cual, dejándolo anotado como pregunta de
seguimiento. El parche 13 encontró exactamente lo mismo de forma
independiente y lo resolvió con `codigo_completo: true`. Las invariantes ni el
resultado numérico del 1.0 se vieron afectados por la corrección del
`TypeError`; si algo, la garantía del manifiesto de la v1.0 sí era la que se
ejecutó, con esa única función reescrita.

---

## Parche 12 → 13: qué se corrigió aquí, además de lo que traía el parche 13

Al aplicar el parche 13 (que ya venía con su propio arreglo del bug de
`sustituibilidad`, más robusto que el de arriba) aparecieron **dos problemas
nuevos**, no señalados en `INSTRUCCIONES.md` del parche 13, corregidos aquí:

1. **Falso positivo de «fusión pendiente».** El chequeo que compara
   `colorantes_adiciones.yaml` contra el diccionario no distinguía «nunca se
   fusionó» de «se fusionó y una corrida anterior ya lo podó por cero
   detecciones» (`podar_si_cero_detecciones`). Como la v1.0 ya había podado 5
   variantes de «beta caroteno sintético», el script las veía «pendientes» y
   `--aplicar` se habría negado a congelar con
   `No se congela con la fusion pendiente`, aunque el estado real ya estaba al
   día. Se corrigió excluyendo del chequeo los términos que
   `decisiones_dra.yaml` marca para poda (`src/14_congelar_diccionario.py`,
   bloque que arma `pendientes` dentro de `main()`).

2. **Prueba desactualizada en `tests/test_diccionario.py`.**
   `test_ambiguos_marcados` asumía que E101 seguía en el diccionario como
   «origen indeterminado». Al salir E101 por completo (fortificación, no
   colorante), la prueba fallaba con `KeyError`. Se actualizó para reflejar
   que E101 ya no es un caso ambiguo: dejó de estar en el eje de color, punto.
   E160a y E140 siguen con `origen_indeterminado: true` sin cambios.

Cifra de contraste con lo que anticipaba el parche 13: predijo 34 códigos;
salieron **35**. La aritmética del propio parche tiene un desliz (37 − 2 = 35,
no 34); los 202 términos sí coincidieron exactamente. No hay nada mal en el
repo por esa diferencia.

---

## Historial completo, parche por parche

Formato: **parche — commit — qué trajo — qué se corrigió o se decidió aquí
que el parche no traía.**

| Parche | Commit | Qué trajo | Corrección / decisión local |
|---|---|---|---|
| 1 (sin número, `parche-colorantes.zip`) | `52737f2` | Arregla el conteo de categorías (`como_lista()` en `util.py`); `05_auditoria_brecha.py`, brecha bruta vs. depurada | Ninguna |
| 2 | `ebe9da6` | `06_sustitucion_por_categoria.py`, `config/categorias.yaml`; evalúa P1/P2 | Ninguna |
| 3 | `4da484c` | Amplía `REQUIEREN_CONTEXTO` (E160b, E162, E163); corrige el umbral de potencia de `06` | Reaplicado el fix de `como_lista()` (bug de array de numpy en `aditivos_tags or []`) en `05_auditoria_brecha.py`, que llegó sin él por segunda vez |
| 4 | `4eeea72` | `HALLAZGO_openfoodfacts.md`; `01` agrega `vitaminas_tags`/`minerales_tags`; `08_vocabulario_off.py` v1; `07_forma_y_clase.py` | Agregado `"contribuidor"` a la lista de nombres de columna candidatos en `07_forma_y_clase.py` (el script buscaba `creador/creator/contribuyente/...`, no el nombre real que usa el resto del repo desde el principio) |
| 5 | `b9a20e7` | `08_vocabulario_off.py` v2: separa `mineral_inorganico`, corrige M3 | `leer_taxonomia()` no escaneaba líneas `xx:` (E101 seguía sin recuperarse); se agregó detección de separación perfecta en el modelo (el propio v2 no la tenía) con nota "no estimable" en vez de un OR de 3.3×10¹¹; `08_revision_dra.csv` agrupaba detecciones por código en vez de por término |
| 6 | `6f76105` | `09_replica_pais.py`; `src/modelo.py` (Firth); `ACUERDO_mexicano.md`, `config/acuerdo_colorantes.yaml`; `10_acuerdo_vs_off.py` | Bug de columnas anidadas (`STRUCT(lang,text)[]`) contra el volcado crudo en `09_replica_pais.py`; URLs de los PDF del Acuerdo (Anexo III/IV) rotas — reemplazadas por las vigentes y guardada copia local en `datos/externo/` |
| 7 | `29db200` | `11_estructura_declaracion.py`; `fusionar_diccionario.py` + `colorantes_adiciones.yaml` (65 términos del DOF); arregla el bloque C de `10` | **Se aplicaron solo las partes 1 y 3.** La fusión del diccionario (parte 2) se dejó sin aplicar a propósito: el propio `REVISION_DRA.md` (parche 5) pedía no tocar el diccionario hasta el veredicto de la Dra., y una de las adiciones (beta caroteno sintético bajo E160a) tocaba justo uno de los seis puntos pendientes |
| 8 | `56bb26b` | `12_termino_disparador.py`; quita el marcador `tiene_dos_puntos` de `11` (opción B del propio parche) | Mismo bug de columnas anidadas, corregido preventivamente en `12_termino_disparador.py` antes de correrlo contra España |
| 9 | `5ead360` | `13_buscar_antecedentes.py` v1 (OpenAlex + Crossref) | Ninguna corrección; se documentó que el diseño de consulta era demasiado laxo (resuelto en el parche 10, no por mí) |
| 10 | `3118212` | `13_buscar_antecedentes.py` v2: búsqueda de frase real, bloque D reescrito sin «Mexico» | `UnicodeEncodeError` por el carácter `→` contra la consola de Windows (cp1252); se agregó `sys.stdout.reconfigure(encoding="utf-8")` |
| 11 | `c38774c` | `13_buscar_antecedentes.py` v3: exigencias derivadas de las frases de la consulta, tres cajones, control de recuperación | Mismo fix de `UnicodeEncodeError`, reaplicado (el archivo llegó fresco sin él) |
| 12 | `b7cd1c4` | `14_congelar_diccionario.py` v1.0; `config/decisiones_dra.yaml`; congela v1.0 | `TypeError` en `recorre()`/`aplica()` por los bloques `genericos`/`sustituibilidad` (ver arriba); agregado E172/SPIRULINA/E164 a `REQUIEREN_CONTEXTO` en `util.py` (el parche solo lo mencionaba como paso manual, no traía el archivo); **se detectó pero no se corrigió** que `lactoflavina`/`vitamina b-2`/`carbon medicinal` sobrevivían con el mismo motivo que sus pares — decisión del usuario: congelar tal cual y preguntarle a la Dra. después |
| 13 | *(este commit)* | `14_congelar_diccionario.py` v1.1: `codigo_completo`, detección estructural de bloques, invariante de códigos ausentes; recongela v1.1 | Falso positivo de «fusión pendiente» contra términos ya podados a propósito (ver arriba); prueba desactualizada en `test_diccionario.py` (E101 ya no existe) |

---

## Cómo evitar que esto se repita

Antes de generar el siguiente parche: pedirle al usuario `git log --oneline`
y el contenido de este archivo, o el archivo mismo si está en GitHub
(`https://github.com/pantrok/colorantes-mexico-pln`). El repo remoto siempre
refleja el estado real después de cada «sí, hazlo» — está más al día que
cualquier copia local de la sesión que redacta el parche.
