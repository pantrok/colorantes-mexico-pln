# Bitácora de búsqueda de antecedentes

**Fecha de ejecución:** 2026-08-29  
**Ventana temporal:** desde 2010  
**Fuentes:** OpenAlex y Crossref, por interfaz de programación, sin llave.  
**Consultas:** 27 cadenas en 5 bloques.  
**Confirmados:** 371; **únicos tras deduplicar por DOI y título:** 348.

## Qué significa cada columna

**Declarados** es lo que la interfaz dice tener. No es un resultado de búsqueda: incluye todo lo que comparta alguna palabra.

**Confirmados** son los que contienen literalmente, en el título o el resumen recuperados, **todas las frases entrecomilladas de la propia consulta** más lo que exija la regla. **Es la única cifra citable.**

**Por revisar** cumplen la regla pero les falta alguna frase: el buscador los emparejó por otro campo. Quedan en `13_por_revisar.csv` para cribado manual y **no cuentan** en ninguna afirmación del artículo.

Tasa global de confirmación: **6.9 %** de lo recuperado.

### Por fuente

| Fuente | Recuperados | Confirmados |
|---|---|---|
| Crossref | 4817 | **19** |
| OpenAlex | 560 | **352** |

Crossref se mantiene como red de seguridad, no como fuente de descubrimiento: no ofrece búsqueda de frase y no devuelve resumen en la mayoría de sus registros, de modo que la verificación solo puede leer el título. Su aporte al corpus se reporta tal como sale.

## Control de recuperación

Se comprobó si la estrategia alcanza trabajos que ya se sabía que eran los vecinos más cercanos. **«No recuperado» señala una cadena insuficiente; «recuperado y descartado» señalaría un filtro mal calibrado**, que es el problema grave.

Resultado: **5 de 5** en el corpus.

| Trabajo | DOI | Estado |
|---|---|---|
| Zancheta et al. 2025 — aditivos en 5 paises de LatAm, incluye Mexico | `10.1186/s12992-025-01130-7` | en el corpus |
| Dunford et al. 2025 — colorantes sinteticos en el anaquel de EE.UU. | `10.1016/j.jand.2025.05.007` | en el corpus |
| Chiu et al. 2025 — colorantes en preenvasados de Hong Kong | `10.1108/BFJ-12-2023-1130` | en el corpus |
| Tseng et al. 2022 — aditivos sensoriales desde listas de ingredientes, EE.UU. | `10.3389/fnut.2021.762814` | en el corpus |
| Chazelas et al. 2020 — precedente metodologico directo, usa Open Food Facts | `10.1038/s41598-020-60948-w` | en el corpus |

> Una búsqueda no demuestra inexistencia. Con este control declarado, lo que la bitácora sostiene es «no se identificaron trabajos que…», nunca «no existen».

## Resultados por consulta

| Bloque | Consulta | Fuente | Declarados | Recuperados | Confirmados | Por revisar |
|---|---|---|---|---|---|---|
| A_colorantes_mercado_mx | `"food colorants" "packaged food"` | OpenAlex | 11 | 11 | **7** | 2 |
| A_colorantes_mercado_mx | `"food colorants" "packaged food"` | Crossref | 765845 | 200 | **0** | 2 |
| A_colorantes_mercado_mx | `"synthetic dyes" "packaged foods"` | OpenAlex | 4 | 4 | **1** | 2 |
| A_colorantes_mercado_mx | `"synthetic dyes" "packaged foods"` | Crossref | 224095 | 200 | **0** | 29 |
| A_colorantes_mercado_mx | `colorantes "alimentos procesados"` | OpenAlex | 12 | 12 | **12** | 0 |
| A_colorantes_mercado_mx | `colorantes "alimentos procesados"` | Crossref | 8171 | 200 | **0** | 0 |
| A_colorantes_mercado_mx | `colorantes etiquetado Mexico` | OpenAlex | 0 | 0 | **0** | 0 |
| A_colorantes_mercado_mx | `colorantes etiquetado Mexico` | Crossref | 69287 | 200 | **0** | 0 |
| A_colorantes_mercado_mx | `"food dyes" prevalence` | OpenAlex | 15 | 15 | **8** | 2 |
| A_colorantes_mercado_mx | `"food dyes" prevalence` | Crossref | 1042029 | 200 | **0** | 0 |
| A_colorantes_mercado_mx | `"food colors" "pre-packaged foods"` | OpenAlex | 2 | 2 | **1** | 1 |
| A_colorantes_mercado_mx | `"food colors" "pre-packaged foods"` | Crossref | 1045434 | 200 | **0** | 3 |
| B_aditivos_envasados_mx | `"food additives" "packaged food supply"` | OpenAlex | 2 | 2 | **2** | 0 |
| B_aditivos_envasados_mx | `"food additives" "packaged food supply"` | Crossref | 947006 | 200 | **0** | 2 |
| B_aditivos_envasados_mx | `"aditivos alimentarios" preenvasados` | OpenAlex | 0 | 0 | **0** | 0 |
| B_aditivos_envasados_mx | `"aditivos alimentarios" preenvasados` | Crossref | 1791 | 200 | **1** | 81 |
| B_aditivos_envasados_mx | `"food additives" "Latin America"` | OpenAlex | 27 | 27 | **16** | 4 |
| B_aditivos_envasados_mx | `"food additives" "Latin America"` | Crossref | 1060191 | 200 | **0** | 0 |
| B_aditivos_envasados_mx | `"NOM-051" etiquetado` | OpenAlex | 12 | 12 | **11** | 0 |
| B_aditivos_envasados_mx | `"NOM-051" etiquetado` | Crossref | 5739 | 200 | **0** | 0 |
| B_aditivos_envasados_mx | `"sensory-related industrial additives"` | OpenAlex | 1 | 1 | **1** | 0 |
| B_aditivos_envasados_mx | `"sensory-related industrial additives"` | Crossref | 1119330 | 200 | **0** | 1 |
| B_aditivos_envasados_mx | `"industrial additives" "packaged food supply"` | OpenAlex | 1 | 1 | **1** | 0 |
| B_aditivos_envasados_mx | `"industrial additives" "packaged food supply"` | Crossref | 1321259 | 200 | **0** | 2 |
| C_extraccion_desde_ingredientes | `"ingredient list" "food additives" extraction` | OpenAlex | 2 | 2 | **0** | 2 |
| C_extraccion_desde_ingredientes | `"ingredient list" "food additives" extraction` | Crossref | 1022646 | 200 | **0** | 0 |
| C_extraccion_desde_ingredientes | `"ingredient statements" parsing` | OpenAlex | 2 | 2 | **1** | 1 |
| C_extraccion_desde_ingredientes | `"ingredient statements" parsing` | Crossref | 22686 | 200 | **0** | 73 |
| C_extraccion_desde_ingredientes | `"food labels" "text mining"` | OpenAlex | 5 | 5 | **1** | 4 |
| C_extraccion_desde_ingredientes | `"food labels" "text mining"` | Crossref | 1000383 | 200 | **0** | 0 |
| C_extraccion_desde_ingredientes | `"named entity recognition" food ingredients` | OpenAlex | 20 | 20 | **20** | 0 |
| C_extraccion_desde_ingredientes | `"named entity recognition" food ingredients` | Crossref | 1063099 | 200 | **0** | 0 |
| C_extraccion_desde_ingredientes | `"ingredient" "nomenclature" food labels` | OpenAlex | 25 | 25 | **17** | 1 |
| C_extraccion_desde_ingredientes | `"ingredient" "nomenclature" food labels` | Crossref | 783077 | 200 | **0** | 10 |
| D_calidad_open_food_facts | `"Open Food Facts"` | OpenAlex | 81 | 81 | **72** | 0 |
| D_calidad_open_food_facts | `"Open Food Facts"` | Crossref | 1427186 | 200 | **0** | 0 |
| D_calidad_open_food_facts | `openfoodfacts` | OpenAlex | 27 | 27 | **19** | 0 |
| D_calidad_open_food_facts | `openfoodfacts` | Crossref | 0 | 0 | **0** | 0 |
| D_calidad_open_food_facts | `"crowdsourced" "food composition database"` | OpenAlex | 1 | 1 | **1** | 0 |
| D_calidad_open_food_facts | `"crowdsourced" "food composition database"` | Crossref | 1097053 | 200 | **0** | 0 |
| D_calidad_open_food_facts | `"food composition database" "data quality"` | OpenAlex | 26 | 26 | **10** | 2 |
| D_calidad_open_food_facts | `"food composition database" "data quality"` | Crossref | 2943194 | 200 | **0** | 3 |
| D_calidad_open_food_facts | `"citizen science" food database completeness` | OpenAlex | 15 | 15 | **4** | 0 |
| D_calidad_open_food_facts | `"citizen science" food database completeness` | Crossref | 5048048 | 200 | **0** | 0 |
| D_calidad_open_food_facts | `"LanguaL"` | OpenAlex | 58 | 58 | **46** | 0 |
| D_calidad_open_food_facts | `"LanguaL"` | Crossref | 6 | 6 | **6** | 0 |
| D_calidad_open_food_facts | `"INFOODS"` | OpenAlex | 193 | 193 | **90** | 0 |
| D_calidad_open_food_facts | `"INFOODS"` | Crossref | 11 | 11 | **11** | 0 |
| E_sustitucion_natural_sintetico | `"natural colorants" "synthetic dyes" replacement` | OpenAlex | 12 | 12 | **5** | 3 |
| E_sustitucion_natural_sintetico | `"natural colorants" "synthetic dyes" replacement` | Crossref | 723686 | 200 | **0** | 0 |
| E_sustitucion_natural_sintetico | `"clean label" colorants reformulation` | OpenAlex | 4 | 4 | **4** | 0 |
| E_sustitucion_natural_sintetico | `"clean label" colorants reformulation` | Crossref | 104335 | 200 | **0** | 0 |
| E_sustitucion_natural_sintetico | `sustitucion colorantes sinteticos naturales` | OpenAlex | 2 | 2 | **2** | 0 |
| E_sustitucion_natural_sintetico | `sustitucion colorantes sinteticos naturales` | Crossref | 10762 | 200 | **1** | 0 |

## Fuentes no automatizadas

SciELO y Redalyc no exponen interfaz de búsqueda por texto libre. Quedan cubiertas indirectamente porque OpenAlex las indexa, y se revisaron a mano con `13_busquedas_manuales.md`.

Latindex no se consultó: es un catálogo de revistas, no de artículos.