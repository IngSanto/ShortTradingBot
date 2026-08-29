# Resultados sobre datos reales

**Última actualización:** agosto 2026 · **0 de 12 estrategias superan las puertas de validación.**

Este documento no es una lista de estrategias que funcionan. Es la lista de lo
que ya podemos descartar, y por qué. Cada resultado negativo aquí es dinero no
perdido.

---

## 1. Los datos

Con la red del entorno abierta, los tres mercados quedaron accesibles:

| Mercado | Universo | Barras | Periodo | Fuente |
|---|---|---|---|---|
| **Acciones** | 15 (5 ETF + 10 valores) | 56.572 | 2010-2026 | Yahoo v8 |
| **Futuros** | 11 (índices, energía, metales, tipos) | 43.000+ | 2010-2026 | Yahoo v8 |
| **Cripto** | 10 perpetuos **con funding real** | 23.212 | 2020-2026 | data.binance.vision |

Reproducible con `scripts/fetch_data.py` y `scripts/fetch_binance_public.py`.

---

## 2. El hallazgo principal: la mejor tesis del catálogo era falsa

`funding_fade_short` era la **prioridad nº1**. La tesis: un funding extremo
señala largos apalancados saturados, así que ponerse corto captura la corrección
mientras cobras carry. Cumplía tres de las cuatro condiciones de la §1 del
catálogo. Era la única estrategia en la que el tiempo jugaba a favor del corto.

**Es falsa, y con margen amplio:**

| Prueba | Resultado |
|---|---|
| Expectativa | **−0,185 R**, t = **−3,97** sobre 329 operaciones |
| Consistencia entre activos | **1 de 10** activos en positivo |
| Barrido de parámetros | **0 de 27** combinaciones positivas |

No es sensibilidad a un parámetro ni mala suerte en un activo. Y la prueba que
lo cierra: medir qué hace el precio *después* de la señal.

| Barras después de funding extremo | Rendimiento medio | Media general |
|---|---|---|
| 1 | **+1,04%** | +0,22% |
| 3 | **+3,05%** | +0,64% |
| 5 | **+5,11%** | +1,10% |
| 10 | **+10,28%** | +2,32% |

**El funding extremo es una señal de continuación alcista, no de agotamiento.**
Multiplica por 4,4 el rendimiento esperado, en la dirección contraria a la que
apostábamos. La lógica de "los largos saturados tienen que deshacerse" no
aparece: lo que un funding alto marca es una tendencia fuerte, y el carry que
cobras (~0,03% diario) es calderilla frente a un +1% diario en tu contra.

*Matiz honesto:* el periodo 2020-2026 en cripto contiene dos mercados alcistas
enormes, lo que favorece a cualquier señal de momentum. Pero eso no salva a la
estrategia: contra ese fondo, ponerse corto es justamente lo que no hay que
hacer, y es el fondo real sobre el que habríamos operado.

---

## 3. Acciones: mercado inviable para un bot solo-corto

**Las diez estrategias de precio pierden, y pierden con los costes puestos a cero.**

| Estrategia | E[R] | t | Activos en positivo |
|---|---|---|---|
| `rsi2_fade` | −0,032 | −1,17 | 53% |
| `gap_up_fade` | −0,173 | −2,00 | 40% |
| `donchian_breakdown` | −0,164 | −2,27 | 27% |
| `parabolic_extension_fade` | −0,153 | −2,91 | 20% |
| `pullback_to_ema_short` | −0,192 | −2,93 | 20% |
| `relative_weakness_short` | −0,298 | −3,24 | 13% |
| `bollinger_upper_fade` | −0,146 | −4,50 | 13% |
| `squeeze_breakdown` | −0,292 | −5,79 | 0% |
| `failed_breakout_short` | −0,279 | −5,90 | 13% |

Que pierdan **sin costes** es la clave: no es un problema de comisiones ni de
afinar parámetros. Es la deriva alcista de la §1 del catálogo, confirmada sobre
16 años y 56.572 barras. Y la columna de consistencia descarta que sea un valor
desafortunado arrastrando la media.

**Conclusión operativa:** con la restricción de operar solo en corto y sin pata
larga, **las acciones no son un mercado viable**. La respuesta correcta en renta
variable sigue siendo largo/corto neutral, que quedó fuera por decisión de
diseño.

*Matiz:* el universo elegido son mega-caps y ETF de un periodo excepcionalmente
alcista. Un universo de small caps de bajo flotante daría otro resultado — pero
también otro riesgo de squeeze, y no tenemos datos de préstamo para modelarlo.

---

## 4. Futuros y cripto: nada pasa, pero algo asoma

Ninguna estrategia supera la puerta 2 (t > 2) en ningún mercado. Las dos que más
se acercan, ambas en cripto:

| Estrategia | E[R] | t | Activos+ | Meseta | Veredicto |
|---|---|---|---|---|---|
| `pullback_to_ema_short` | +0,091 | 1,29 | **70%** | **100%** | P2 fallida |
| `squeeze_breakdown` | +0,036 | 0,48 | 50% | 89% | P2 fallida |

`pullback_to_ema_short` es la única candidata que queda viva del catálogo
original: positiva en 7 de 10 activos, **meseta de parámetros perfecta** (27 de
27 combinaciones), y positiva también en futuros. Pero t = 1,29 no es
distinguible del ruido, y ya aprendimos en la tanda anterior —con
`squeeze_breakdown` sobre BTC— que una meseta bonita con muestra corta no
significa nada.

En futuros, `donchian_breakdown` es la única que supera la puerta 1 (+0,038,
meseta 67%), pero se queda en t = 0,52.

---

## 5. Estado del catálogo

| Estrategia | Veredicto | Evidencia |
|---|---|---|
| `funding_fade_short` | **DESCARTADA** | La señal apunta al revés; 0/27 combinaciones |
| `failed_breakout_short` | **DESCARTADA** | Negativa y significativa en los tres mercados |
| `bollinger_upper_fade` | **DESCARTADA** | Negativa y significativa en los tres mercados |
| `parabolic_extension_fade` | **DESCARTADA** | Negativa y significativa; t=−3,4 en cripto |
| `rsi2_fade` | **DESCARTADA** | Negativa en los tres mercados |
| `squeeze_breakdown` | **Muerta en acciones y futuros** | Sobrevive débil en cripto (t=0,48) |
| `relative_weakness_short` | **DESCARTADA en acciones** | t=−3,24; sin pata larga no tiene argumento |
| `volatility_spike_exhaustion` | **DESCARTADA** | Negativa; y con el peor riesgo de ruina |
| `donchian_breakdown` | **En observación** | Único positivo en futuros, pero t=0,52 |
| **`pullback_to_ema_short`** | **La única viva** | +0,091 R en cripto, 70% activos, meseta 100% |
| `gap_up_fade` | **Sin evaluar en cripto** | Correcto: 24/7 no tiene huecos. Negativa en acciones |
| `oi_flush_short` | **Sin evaluar** | Falta open interest (carpeta `metrics` de Binance) |

**Balance: 7 descartadas con evidencia, 1 viva, 2 en observación, 2 sin evaluar.**

---

## 6. Tres bugs que solo aparecieron con datos reales

Los datos sintéticos no los habrían encontrado nunca:

1. **Precios negativos.** El WTI cerró a −37,63 el 20-04-2020. El dimensionamiento dividía por el precio: con precio negativo habría abierto una cantidad negativa, es decir, **un largo encubierto dentro de un motor short-only**.
2. **Huecos de funding convertidos en ceros.** `resample().sum()` devuelve 0 para días sin registros. Un hueco de datos se volvía un "funding cero" creíble.
3. **`load_csv` descartaba `funding_rate`.** Recortaba el DataFrame a las cinco columnas OHLCV, así que `funding_fade_short` devolvía **cero señales sin dar ningún error**. Es el peor modo de fallo posible: parecía "no hay oportunidades" cuando era "no ve su dato".

Los tres tienen ahora prueba de regresión.

---

## 7. Qué haría a continuación

1. **Abandonar acciones** para el mandato solo-corto. La evidencia es contundente y seguir ahí es gastar tiempo.
2. **Concentrarse en `pullback_to_ema_short` en cripto**: bajar a 4h y 1h para multiplicar la muestra y aplicar la puerta 2.5. Es la única forma barata de saber si ese +0,091 R es real.
3. **Descargar el open interest** (`metrics` de Binance) para evaluar `oi_flush_short`, la última tesis del catálogo sin probar.
4. **Replantear la familia de flujo.** El resultado del funding sugiere que en cripto los indicadores de posicionamiento funcionan como señales de *continuación*. Si eso se confirma, el catálogo corto debería construirse sobre agotamiento de tendencia, no sobre aglomeración.
