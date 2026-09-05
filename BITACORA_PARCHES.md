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
- **Flujo completo (01→12):** re-ejecutado el 02/09/2026 contra el
  diccionario v1.1. Ver la sección «Corrida completa 01→12» más abajo para
  las cifras nuevas y los dos bugs que se encontraron y corrigieron.
- **Cuatro bugs de conteo encontrados el 05/09/2026 — APLICADOS y todo el
  flujo 01→12 recorrido de nuevo ese mismo día.** Ver la sección «Diagnóstico
  de la coincidencia 1597» más abajo para el reporte completo y «Cifras
  finales tras aplicar los cuatro arreglos» para el antes/después de cada
  script. **La cifra citable de la brecha depurada es ahora 69.7 %, no
  67.5 % ni 66.1 %.** Al aplicar el arreglo de deduplicación por código
  (bug 2) a todo el pipeline, se encontró el **mismo bug, sin diagnosticar
  todavía, en `09_replica_pais.py` y en `11_estructura_declaracion.py`** —
  ambos comparten el patrón de iterar términos y no agrupar por código antes
  de contar. Quedaron corregidos igual que `07`/`08`. `10_acuerdo_vs_off.py`
  y `12_termino_disparador.py` se revisaron y **no tienen este bug**: su
  unidad de conteo es intencionalmente la forma/término, no el código, así
  que una fila por término es el diseño correcto ahí, no un defecto.
- **Pendiente, sin empezar (además de lo de arriba):** decidir el tratamiento
  del dióxido de titanio (E171) antes del modelo de Firth, escribir el manual
  de anotación, sortear los 600 y anotar contra el hash de v1.1.
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

## Corrida completa 01→12 contra el diccionario v1.1 (02/09/2026)

No es un parche numerado — el usuario pidió correr todo el flujo con el
diccionario ya congelado. Se documenta aquí por la misma razón que todo lo
demás: dos bugs reales aparecieron al correrlo, y quien lea el repo después
tiene que saber que ya se corrigieron.

**Bug 1 — `01_subconjunto_mx.py` sobrescribía `reportes/procedencia.json`
entero.** El script escribía un `dict` nuevo con solo
`origen/fecha/licencia/sha256_salida`, borrando las secciones
`taxonomias_off` y `acuerdo_mexicano_aditivos` que se habían agregado a mano
en parches anteriores (documentación de commits y URLs de las taxonomías de
OFF y de los Anexos del DOF). Se recuperó el contenido perdido desde
`git show HEAD:reportes/procedencia.json` y se corrigió el script para que
**fusione** (lee el archivo existente, actualiza solo esas cuatro claves) en
vez de sobrescribir. Verificado con una segunda corrida: las claves manuales
sobreviven.

**Bug 2 — `07_forma_y_clase.py` tenía `MINERALES = {"E170", "E171"}`, sin
E172**, mientras que `08`, `09`, `10`, `11` y `12` sí traen las tres. Con el
bloque nombrado `naturales` en el YAML, un E172 sin marcar caía a
`natural_botanico` por el nombre del bloque en vez de por su código real —
exactamente el aviso genérico que `14_congelar_diccionario.py` imprime en
cada corrida sobre este mismo riesgo. Corregido agregando E172 al set. **No
cambió ningún número en esta corrida** porque E172 tuvo cero detecciones en
este corte de datos; el arreglo previene el problema para cuando sí las
tenga.

**Además:** el diccionario `MEXICO` hardcodeado dentro de
`09_replica_pais.py` (usado para comparar contra España) traía los números de
la corrida del 27 de agosto, previa al congelamiento. Se actualizó con los
valores de la v1.1 (correr `--pais en:mexico` primero para obtenerlos).

### Cifras que cambiaron respecto a la última corrida citada en el repo

| Número | Antes (pre-v1.1) | Ahora (v1.1) |
|---|---|---|
| Brecha depurada (`05`, la que se cita) | 66.1 % | **67.5 %** |
| Brecha bruta (`02`) | 77.6 % | 74.1 % |
| P1 azul (sintético vs. espirulina) | 328 vs. 4 | 332 vs. **0** (espirulina ahora exige contexto) |
| P4 réplica España (natural, diferencia vs. México) | -8.4 pp (falla) | **-10.0 pp (sigue fallando)** — no era artefacto del diccionario sin depurar |
| P7 términos estables entre países | 80.0 % | **85.7 %** |
| M3 (vitaminas/minerales recuperadas en `08`) | 17 (E101) | **0** — E101 ya no existe en el eje, no hay nada que M3 pueda recuperar |
| `10`, formas oficiales ya en nuestro diccionario | 44 (29.7 %) | **96 (64.9 %)** — por la fusión del DOF |

**Aviso para leer `10_acuerdo_vs_off.json` de esta corrida:** de los 453
productos que aparecen como «forma legal no reconocida», **421 son
riboflavina**. Eso no es una brecha nueva: es la consecuencia esperada de que
la Dra. la sacara del eje de color. No reportar esa cifra sin esa aclaración.

---

## Diagnóstico de la coincidencia 1597 = 1597 (05/09/2026) — APLICADO

Investigación pedida por `DIAGNOSTICO_1597.md` (recibido de fuera, no un
parche numerado). **Regla explícita del propio documento: no tocar ningún
script hasta reportar evidencia.** Se reportó primero (lo que sigue), y solo
tras la confirmación explícita del usuario («aplica los cuatro y recorre
todo») se tocó el código. Los cuatro arreglos quedaron aplicados el mismo
día, con el flujo 01→12 completo recorrido de nuevo contra ellos.

**Lo que se descartó.** `05_auditoria_brecha.py` cuenta bien: `n_con_colorante`
y `n_con_brecha` ya son conteos de productos distintos (`len()` sobre un
DataFrame de una fila por producto, filtrado por conjunto no vacío), no filas
de una tabla de detección. Verificado recalculando desde el parquet intermedio
sin tocar el script: (1) productos con detección y (4) productos con falta
coinciden exactamente con lo reportado (1597 y 1078).

**Lo que sí está mal — bug 1, confirmado, con impacto real en la cifra que se
cita.** `05_auditoria_brecha.py` (línea 56) y `06_sustitucion_por_categoria.py`
(línea 77) construyen `por_codigo = {c: p for c, _, p in matchers}` para el
chequeo de contexto. Como `matchers` trae **un patrón por término** y el dict
se queda con el último procesado, para cualquier código con más de un término
(11 de los 13 que exigen contexto — todos excepto E101 y E170, que ya no
tienen términos) el chequeo de «¿aparece "colorante" cerca?» se hace contra
un término **arbitrario del código, no contra el que de verdad coincidió en
ese producto**. Para E171 el diccionario se queda con el patrón de "pigmento
blanco 6" en vez de "dioxido de titanio", que es el que aparece en el 99 % de
los casos reales.

Recalculada la brecha depurada usando el término que de verdad coincidió por
detección (mismo criterio que ya usa correctamente `07_forma_y_clase.py`):

| | Reportado ahora | Corregido |
|---|---|---|
| n_con_colorante depurado | 1597 | **1734** |
| n_con_brecha | 1078 | **1208** |
| brecha depurada (la cifra citable) | 67.5 % | **69.7 %** |

Los scripts 07 a 12 **no** tienen este bug: rastrean el término específico que
coincidió en cada detección (`detectar_con_forma`/`detectar_con_termino`) y
llaman `con_contexto(texto, termino)` con ese término real, no con un patrón
por código.

**Bug 2, confirmado, con impacto real y activo.** `07_forma_y_clase.py` y
`08_vocabulario_off.py` comparten la misma función de detección por término
(`detectar_con_forma`/`detectar_con_termino`), que **no deduplica por
código**: si un producto declara el mismo colorante con dos sinónimos (p. ej.
"achiote" y "annatto", ambos E160b), lo cuenta dos veces. Por eso 07 y 08
"coinciden" en 3417 detecciones / 1597 sin etiqueta — no es corroboración
independiente entre dos scripts, es el mismo bug compartido. El recuento
correcto (deduplicado por código y producto, como ya hace `util.py::detectar()`
para 05) da **2949 detecciones, 1356 sin etiqueta**. La distribución resultante
(moda 1, mediana 2, media 1.85, cola larga) es la que el propio diagnóstico
dijo que cerraría el caso si aparecía así.

**Bug 3, confirmado pero sin efecto actual (dormido).** La estratificación de
los 600 en `07_forma_y_clase.py` (línea 356, bloque E) deriva "es natural" de
`any(c in dic["naturales"] for c in s)` — membresía cruda en el bloque del
YAML — en vez de llamar a `clase_de()`. Como E171/E172 viven físicamente en
el bloque `naturales`, esto podría meter pigmentos inorgánicos al estrato
natural. **Verificado contra los 7775 productos completos: hoy da 0 casos**
— los dos productos que citaba el diagnóstico externo (`722776005606`,
`7506174507633`) ya no están ni en el corpus problemático ni en la muestra
actual, porque son de antes del congelamiento v1.1. El bug sigue en el código
y podría activarse si el diccionario vuelve a cambiar; no corrompe nada hoy.

**Bug 4, confirmado, con impacto real y activo, pequeño.**
`06_sustitucion_por_categoria.py` solo excluye carmín (E120) de "naturales";
a diferencia de 07-12, no excluye E170/E171/E172. Con E171 teniendo detecciones
reales, 2 productos concretos (`7501006505689`, `7501791650922`) se cuentan
hoy como "natural" en la Tabla 4/6 cuando deberían reportarse aparte como
mineral_inorganico.

### Arreglo aplicado (05/09/2026)

1. En `05_auditoria_brecha.py` y `06_sustitucion_por_categoria.py`: se
   sustituyó `util.py::detectar()` (o el chequeo de contexto por código) por
   una función local `detectar_con_termino()` que devuelve `(codigo, bloque,
   termino)` con el término real que coincidió, y el contexto se busca con
   `contexto_de_color(texto, termino)`/`con_contexto(texto, termino)` sobre
   ese término, no sobre un patrón arbitrario del código.
2. En `07_forma_y_clase.py` y `08_vocabulario_off.py`: se agrupan las
   detecciones por `codigo` antes de emitir fila — un producto aporta como
   máximo una fila por código, sin importar cuántos sinónimos de ese código
   contenga. El contexto y la cobertura de vocabulario se combinan con OR
   entre los sinónimos que matchearon (basta que uno tenga "colorante" cerca,
   o que uno esté en el vocabulario de OFF).
3. En `07_forma_y_clase.py`, bloque E (estratificación de los 600) **y**
   bloque D (recálculo de Chiu): se reemplazó `any(c in dic["naturales"] for
   c in s)` / `dic["sinteticos"]` por un diccionario `clase_por_codigo` que sí
   pasa por `clase_de()`, para que E171/E172 nunca puedan colarse al estrato
   natural por vivir en el bloque `naturales` del YAML.
4. En `06_sustitucion_por_categoria.py`: se agregó el conjunto `MINERALES =
   {"E170", "E171", "E172"}` y se excluyen de "naturales" igual que ya se
   excluía E120; se reportan aparte como campo `mineral` por fila y
   `n_mineral_inorganico`/`pct_mineral` en la matriz agregada.

**Alcance ampliado al aplicar.** El bug 2 (no deduplicar por código) resultó
estar también en `09_replica_pais.py` y `11_estructura_declaracion.py` —
ninguno de los dos estaba mencionado en el diagnóstico original, que solo
había mirado `07`/`08`. Se corrigieron con el mismo patrón (agrupar por
código, OR entre sinónimos). Se revisaron `10_acuerdo_vs_off.py` y
`12_termino_disparador.py`: su granularidad de conteo es intencionalmente
por forma/término (`10` mide qué formas legales existen en el vocabulario de
OFF; `12` mide si el término, no el código, es la unidad que decide la
recuperación), así que una fila por término ahí **no** es este bug — no se
tocaron.

Se restauró además `reportes/07_muestra_anotacion.csv` desde git: apareció
como cambio sin commitear al iniciar esta sesión, con la columna `code`
convertida a notación científica por un redondeo de Excel al abrirlo/guardarlo
— no lo causó ninguna corrida de este repo. No tenía anotaciones (`anotador_1`
/`anotador_2`/`notas` vacíos), así que no se perdió trabajo al descartarlo.

### Cifras finales tras aplicar los cuatro arreglos (05/09/2026)

| Script | Métrica | Antes del arreglo | Después |
|---|---|---|---|
| `05` | brecha depurada (la que se cita) | 67.5 % (1078/1597) | **69.7 % (1208/1734)** |
| `05` | brecha bruta | 74.1 % | 74.1 % (sin cambio) |
| `06` | categorías con n≥30 | 11 | **12** (aparece `mineral_inorganico`) |
| `07` | sintético (agregado depurado) | n=2693, no medido así antes | **n=2509 (37.1 %)** |
| `07` | natural_botánico | — | **n=438 (90.4 %)** |
| `07` | carmín | — | **n=233 (95.7 %)** |
| `07` | mineral_inorgánico | — | **n=48 (25.0 %)** |
| `08` | cobertura de vocabulario | — | 59/197; M3 recuperadas 0; brecha global 48.4 % |
| `09` México | sintético | n=2693, brecha 35.7 % | **n=2509, brecha 37.1 %** |
| `09` México | natural_botánico | n=441, brecha 90.5 % | **n=438, brecha 90.4 %** |
| `09` México | carmín | n=235, brecha 95.7 % | **n=233, brecha 95.7 %** |
| `09` España | sintético | n=839, brecha 33.4 % | **n=795, brecha 33.2 %** |
| `09` España | natural_botánico | n=2607, brecha 80.5 % | **n=2585, brecha 80.5 %** |
| `09` España | carmín | n=500, brecha 32.2 % | **n=488, brecha 32.0 %** |
| `09` | P4 (natural baja ≥15 pp en España) | falla (-10.0 pp aprox.) | **sigue fallando (-9.9 pp)** |
| `09` | P5 (sintético cambia <10 pp) | cumple | **sigue cumpliendo (-3.9 pp)** |
| `10` | (sin bug; no cambió) | 96/148 formas oficiales en nuestro diccionario | igual |
| `11` México | n_detecciones | 3271 | **3085** |
| `11` España | n_detecciones | 3742 | **3669** |
| `11` | VEREDICTO (ambos países) | H2 — el código en el texto | sin cambio |
| `12` | (sin bug; granularidad por término, no cambió) | 14 términos comparables, 85.7 % estables, P7 cumple | igual |

**El diccionario `MEXICO` hardcodeado en `09_replica_pais.py`** (usado como
referencia fija dentro del propio script para la comparación con España) se
actualizó a los valores corregidos: `sintetico n=2509/37.1 %/82.8 %`,
`natural_botanico n=438/90.4 %/30.8 %`, `carmin n=233/95.7 %/92.7 %`.

**No volver a citar 67.5 %, 66.1 %, ni las cifras de `07`/`08`/`09`/`11`
previas a esta corrida — están reemplazadas por las de esta tabla.**

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
| — (sin número, `DIAGNOSTICO_1597.md`) | *(pendiente de commit)* | No trajo código: un diagnóstico externo pidió investigar la coincidencia 1597=1597 entre `05` y `07`/`08` | Encontrados y corregidos los 4 bugs de conteo de la sección de arriba en `05`, `06`, `07`, `08`; el alcance se amplió en local a `09` y `11`, que compartían el mismo bug de no-deduplicación sin que el diagnóstico externo los hubiera señalado. Brecha depurada pasa a citarse en 69.7 % |

---

## Cómo evitar que esto se repita

Antes de generar el siguiente parche: pedirle al usuario `git log --oneline`
y el contenido de este archivo, o el archivo mismo si está en GitHub
(`https://github.com/pantrok/colorantes-mexico-pln`). El repo remoto siempre
refleja el estado real después de cada «sí, hazlo» — está más al día que
cualquier copia local de la sesión que redacta el parche.
