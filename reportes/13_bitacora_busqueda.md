# Bitácora de búsqueda de antecedentes

**Fecha de ejecución:** 2026-08-29  
**Ventana temporal:** desde 2010  
**Fuentes:** OpenAlex y Crossref, por interfaz de programación, sin llave.  
**Consultas:** 21 cadenas en 5 bloques.  
**Confirmados:** 410; **únicos tras deduplicar por DOI y título:** 407.

## Cómo leer esta tabla

**Declarados** es lo que la interfaz dice tener. No es un resultado de búsqueda: ninguna de las dos hace búsqueda de frase por omisión, así que esa cifra incluye todo lo que comparta alguna palabra.

**Confirmados** son los que, al revisar el título y el resumen recuperados, contienen de verdad los términos exigidos. **Es la única cifra citable.**

Tasa global de confirmación: **9.6 %** de lo recuperado.

> Una búsqueda no demuestra inexistencia. Lo que esta bitácora sostiene es «no se identificaron trabajos que…», con la estrategia declarada.

## Resultados por consulta

| Bloque | Consulta | Fuente | Declarados | Recuperados | Confirmados |
|---|---|---|---|---|---|
| A_colorantes_mercado_mx | `"food colorants" "packaged food"` | OpenAlex | 11 | 11 | **9** |
| A_colorantes_mercado_mx | `"food colorants" "packaged food"` | Crossref | 765839 | 200 | **2** |
| A_colorantes_mercado_mx | `"synthetic dyes" "packaged foods"` | OpenAlex | 4 | 4 | **3** |
| A_colorantes_mercado_mx | `"synthetic dyes" "packaged foods"` | Crossref | 224095 | 200 | **29** |
| A_colorantes_mercado_mx | `colorantes "alimentos procesados"` | OpenAlex | 12 | 12 | **12** |
| A_colorantes_mercado_mx | `colorantes "alimentos procesados"` | Crossref | 8171 | 200 | **0** |
| A_colorantes_mercado_mx | `colorantes etiquetado Mexico` | OpenAlex | 0 | 0 | **0** |
| A_colorantes_mercado_mx | `colorantes etiquetado Mexico` | Crossref | 69287 | 200 | **0** |
| A_colorantes_mercado_mx | `"food dyes" prevalence` | OpenAlex | 15 | 15 | **10** |
| A_colorantes_mercado_mx | `"food dyes" prevalence` | Crossref | 1042023 | 200 | **0** |
| B_aditivos_envasados_mx | `"food additives" "packaged food supply"` | OpenAlex | 2 | 2 | **2** |
| B_aditivos_envasados_mx | `"food additives" "packaged food supply"` | Crossref | 946999 | 200 | **2** |
| B_aditivos_envasados_mx | `"aditivos alimentarios" preenvasados` | OpenAlex | 0 | 0 | **0** |
| B_aditivos_envasados_mx | `"aditivos alimentarios" preenvasados` | Crossref | 1791 | 200 | **82** |
| B_aditivos_envasados_mx | `"food additives" "Latin America"` | OpenAlex | 27 | 27 | **20** |
| B_aditivos_envasados_mx | `"food additives" "Latin America"` | Crossref | 1060185 | 200 | **0** |
| B_aditivos_envasados_mx | `"NOM-051" etiquetado` | OpenAlex | 12 | 12 | **11** |
| B_aditivos_envasados_mx | `"NOM-051" etiquetado` | Crossref | 5738 | 200 | **0** |
| C_extraccion_desde_ingredientes | `"ingredient list" "food additives" extraction` | OpenAlex | 2 | 2 | **2** |
| C_extraccion_desde_ingredientes | `"ingredient list" "food additives" extraction` | Crossref | 1022640 | 200 | **0** |
| C_extraccion_desde_ingredientes | `"ingredient statements" parsing` | OpenAlex | 2 | 2 | **2** |
| C_extraccion_desde_ingredientes | `"ingredient statements" parsing` | Crossref | 22685 | 200 | **73** |
| C_extraccion_desde_ingredientes | `"food labels" "text mining"` | OpenAlex | 5 | 5 | **5** |
| C_extraccion_desde_ingredientes | `"food labels" "text mining"` | Crossref | 1000375 | 200 | **0** |
| C_extraccion_desde_ingredientes | `"named entity recognition" food ingredients` | OpenAlex | 20 | 20 | **20** |
| C_extraccion_desde_ingredientes | `"named entity recognition" food ingredients` | Crossref | 1063091 | 200 | **0** |
| D_calidad_open_food_facts | `"Open Food Facts"` | OpenAlex | 81 | 81 | **72** |
| D_calidad_open_food_facts | `"Open Food Facts"` | Crossref | 1427177 | 200 | **0** |
| D_calidad_open_food_facts | `openfoodfacts` | OpenAlex | 27 | 27 | **19** |
| D_calidad_open_food_facts | `openfoodfacts` | Crossref | 0 | 0 | **0** |
| D_calidad_open_food_facts | `"crowdsourced" "food composition database"` | OpenAlex | 1 | 1 | **1** |
| D_calidad_open_food_facts | `"crowdsourced" "food composition database"` | Crossref | 1097045 | 200 | **0** |
| D_calidad_open_food_facts | `"food composition database" "data quality"` | OpenAlex | 26 | 26 | **12** |
| D_calidad_open_food_facts | `"food composition database" "data quality"` | Crossref | 2943180 | 200 | **3** |
| D_calidad_open_food_facts | `"citizen science" food database completeness` | OpenAlex | 15 | 15 | **4** |
| D_calidad_open_food_facts | `"citizen science" food database completeness` | Crossref | 5048026 | 200 | **0** |
| E_sustitucion_natural_sintetico | `"natural colorants" "synthetic dyes" replacement` | OpenAlex | 12 | 12 | **8** |
| E_sustitucion_natural_sintetico | `"natural colorants" "synthetic dyes" replacement` | Crossref | 723684 | 200 | **0** |
| E_sustitucion_natural_sintetico | `"clean label" colorants reformulation` | OpenAlex | 4 | 4 | **4** |
| E_sustitucion_natural_sintetico | `"clean label" colorants reformulation` | Crossref | 104334 | 200 | **0** |
| E_sustitucion_natural_sintetico | `sustitucion colorantes sinteticos naturales` | OpenAlex | 2 | 2 | **2** |
| E_sustitucion_natural_sintetico | `sustitucion colorantes sinteticos naturales` | Crossref | 10762 | 200 | **1** |

## Fuentes no automatizadas

SciELO y Redalyc no exponen interfaz de búsqueda por texto libre. Quedan cubiertas indirectamente porque OpenAlex las indexa, y se revisaron a mano con `13_busquedas_manuales.md`.

Latindex no se consultó: es un catálogo de revistas, no de artículos.