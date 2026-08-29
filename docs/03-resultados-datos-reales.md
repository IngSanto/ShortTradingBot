# Primeros resultados sobre datos reales

**Fecha:** agosto 2026 · **Estado:** ninguna estrategia ha pasado las puertas de validación.

Este documento se actualiza con cada tanda de datos nuevos. Lo que contiene hoy
no es una lista de estrategias que funcionan: es una lista de **cosas que ya
podemos descartar** y de otras que siguen sin demostrarse.

---

## 1. Qué datos tenemos, y qué no

El entorno de desarrollo tiene la red restringida: Yahoo Finance, Binance,
Bybit, Kraken, Stooq, CoinGecko, Alpha Vantage, Polygon y Nasdaq Data Link
devuelven todos 403. Solo `raw.githubusercontent.com` es accesible, así que los
datos vienen de repositorios públicos que **committean** los CSV
(`scripts/fetch_github_data.py`).

| Serie | Barras | Periodo | Calidad |
|---|---|---|---|
| **BTC/USD diario** | 4.753 | 2012-01 → 2025-01 | Real, de 1 min agregado. Bitstamp **spot**, no perpetuo |
| **BTC/USD 4h** | 28.216 | 2012-01 → 2025-01 | Igual, mayor resolución |
| **VIX diario** | 9.261 | 1990-01 → 2026-08 | Real, OHLC sin volumen. Índice **no operable** directamente |

**Lo que falta, y condiciona todas las conclusiones:**

- **Un universo.** Una sola serie de precios no permite distinguir un edge de una casualidad de ese activo. Es la limitación más grave de esta tanda.
- **Funding y open interest reales.** `funding_fade_short` y `oi_flush_short` — las dos con mejor tesis del catálogo — siguen sin poder evaluarse.
- **Acciones y futuros.** No hay ningún dataset accesible con OHLCV por ticker.

---

## 2. Resultado principal: la criba está descartando, que es su trabajo

### 2.1 Evidencia para descartar (resultados negativos y significativos)

| Estrategia | BTC diario | BTC 4h | Veredicto |
|---|---|---|---|
| `bollinger_upper_fade` | −0,388 (t=−3,06) | −0,197 (t=−3,25) | **Descartada.** Negativa y significativa en las dos temporalidades. Ya entró como línea base; ahora hay evidencia real en su contra. |
| `failed_breakout_short` | −0,187 (t=−1,62) | −0,159 (t=−2,94) | **Degradada.** Era mi candidata nº2. En BTC la tesis de "compradores atrapados" no aparece: pierde de forma consistente en ambas temporalidades. |
| `parabolic_extension_fade` | −0,467 (t=−5,42) | — | **Confirmada su exclusión** de producción, ahora con datos. |

Que `failed_breakout_short` falle es el resultado más útil de la tanda, porque
**contradice la recomendación del documento 01**. Lo que ahí era una tesis
razonable —hay un grupo identificable de compradores atrapados cuya salida
alimenta la caída— no se observa en el precio de BTC. Dos lecturas posibles, y
no las puedo separar con estos datos: la tesis es falsa en cripto, o mi
implementación (barrido del máximo de 20 barras + cierre por debajo) es
demasiado tosca para capturarla.

### 2.2 El caso que parecía bueno y no lo era

`squeeze_breakdown` sobre BTC diario:

- Expectativa **+0,393 R**, t = 2,33, 55 operaciones.
- Meseta de parámetros **perfecta**: 27 de 27 combinaciones positivas, mediana +0,306, peor caso +0,189.
- Signo positivo en **todos** los sub-periodos (2012-16, 2017-20, 2021-25).

Todo apuntaba bien. Y aun así **no pasa**:

| Prueba | Resultado |
|---|---|
| t-estadístico en el periodo líquido (2017+) | **1,11** — por debajo del umbral de 2 |
| Misma estrategia en 4h (239 operaciones) | **−0,012** (t = −0,15) — el edge desaparece |

El resultado diario tenía 35 operaciones en el tramo líquido. Con esa muestra, un
t de 1,11 y una meseta bonita son perfectamente compatibles con el azar: la
meseta mide que el resultado no depende de un parámetro afortunado, no que el
resultado sea real. Cuando se multiplica la muestra por siete cambiando de
temporalidad, no queda nada.

**Lección para el proceso:** la meseta de parámetros y la consistencia por
sub-periodo son necesarias pero no suficientes. El test que lo mató fue el de
temporalidad cruzada, que no estaba en la metodología original. **Queda añadido
como puerta 2.5.**

---

## 3. Control: el motor discrimina correctamente

Sobre el VIX —una serie fuertemente reversiva a la media, con comportamiento
opuesto al de una acción o BTC— el catálogo se ordena exactamente al revés:

| Familia | En VIX (reversivo) | En BTC (tendencial) |
|---|---|---|
| Reversión (`bollinger_upper_fade`) | **+0,221** (t=+3,46) | −0,388 (t=−3,06) |
| Tendencia (`donchian_breakdown`) | **−0,616** (t=−10,2), acierto 11% | +0,262 (t=+0,94) |

No es un hallazgo operable —el índice VIX no se puede vender en corto
directamente— pero sí una **verificación del instrumento**: el motor no produce
el mismo resultado con independencia de los datos. Detecta la naturaleza de la
serie, y con el signo correcto en ambos casos.

---

## 4. Dos advertencias sobre las cifras de arriba

1. **Los datos son de spot, los costes son de perpetuo.** Se aplicó el perfil cripto (carry −10%, es decir, ingreso) a precios de Bitstamp spot, donde no se cobra funding. El sesgo es de **+0,04 R por operación** a favor de los resultados: medido, no estimado. Ninguna conclusión de este documento cambia al corregirlo, pero conviene tenerlo presente.
2. **Un activo no es una muestra.** Todo lo anterior es BTC. `assets_positive`, la métrica de consistencia entre activos, no significa nada con n=1.

---

## 5. Estado del catálogo tras esta tanda

| Estrategia | Estado | Siguiente paso |
|---|---|---|
| `funding_fade_short` | **Sin evaluar** | Conseguir histórico de funding: sigue siendo la mejor tesis |
| `oi_flush_short` | **Sin evaluar** | Conseguir open interest |
| `pullback_to_ema_short` | **Neutra** (+0,018 diario / +0,006 en 4h) | Necesita universo |
| `donchian_breakdown` | **Neutra** (+0,262 pero t=0,94) | Necesita universo |
| `squeeze_breakdown` | **No pasa** | El edge diario no sobrevive al cambio de temporalidad |
| `failed_breakout_short` | **Evidencia en contra** | Revisar la implementación antes de descartar la tesis |
| `bollinger_upper_fade` | **Descartada** | — |
| `parabolic_extension_fade` | **Descartada** | — |
| `relative_weakness_short` | **Sin evaluar** | Necesita universo + índice |
| `gap_up_fade` | **Sin evaluar** | Necesita datos intradía y filtro de noticias |

**Balance: 0 promovidas, 3 descartadas, 1 caída en la puerta de temporalidad.**
Es exactamente lo que se espera de una primera tanda, y es barato comparado con
descubrirlo con dinero real.

---

## 6. El cuello de botella, con nombre y apellidos

Lo que bloquea el progreso no es el código: es **el acceso a datos**. Con un
universo de 20-30 activos por mercado y el histórico de funding, las puertas 1 a
3 de la metodología se pueden completar en horas. Sin eso, cada conclusión se
apoya en un solo activo y nunca superará el umbral estadístico, por muchas
estrategias que implementemos.
