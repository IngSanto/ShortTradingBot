# Resultados sobre datos reales

**Última actualización:** agosto 2026 · **2 de 12 estrategias superan las puertas 1 a 3.**
Ninguna ha pasado por paper trading todavía: no hay nada listo para dinero real.

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

> **Decisión confirmada (2026-08-30):** se cierra el mandato a cripto. Acciones
> queda descartado con evidencia; futuros descartado pero no vetado de raíz
> (ver `config/catalogo.json` → `decisiones_confirmadas`). Lo que sigue es la
> evidencia que llevó a esa decisión.



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

## 4. Cripto: dos estrategias superan las puertas 1 a 3

Al ampliar el universo de 10 a **40 perpetuos** (82.209 barras), el
t-estadístico subió como debía si el efecto era real:

| Estrategia | n | E[R] | t | Activos+ | Meseta | Fuera de muestra | Veredicto |
|---|---|---|---|---|---|---|---|
| `pullback_to_ema_short` | 1.025 | +0,114 | **3,36** | 72,5% | 100% | **+0,271** (228 ops) | **PASA** |
| `squeeze_breakdown` | 844 | +0,198 | **5,03** | 72,5% | 100% | **+0,166** (156 ops) | **PASA** |
| `donchian_breakdown` | 591 | +0,015 | 0,36 | 47,5% | — | — | P1 fallida |

Con 10 activos, `pullback_to_ema_short` daba t=1,29. Con 40, t=3,36. Esa es la
firma de un efecto real: al cuadruplicar las observaciones independientes el
estadístico crece, no se queda plano.

### No es solo cobertura: hay alfa en mercado alcista

La prueba que más importa en un sistema corto. Régimen definido por BTC frente
a su SMA(200) el día de entrada:

| Estrategia | BTC alcista | BTC bajista | Dependencia |
|---|---|---|---|
| `squeeze_breakdown` | **+0,224** (t=4,51) | +0,121 (t=2,67) | **−0,103** |
| `pullback_to_ema_short` | **+0,140** (t=3,06) | +0,186 (t=5,15) | +0,046 |

Ambas son positivas **con el mercado subiendo**, y `squeeze_breakdown` es
incluso mejor ahí que en mercado bajista. No son seguros disfrazados de alfa.

### Puerta 2.5 superada

| Estrategia | Diario | 4h, ventanas ×6 | 4h, mismos parámetros |
|---|---|---|---|
| `squeeze_breakdown` | +0,041 | +0,075 | **+0,066 (t=2,37)** |
| `pullback_to_ema_short` | +0,110 | +0,082 | −0,005 |

`squeeze_breakdown` es además **invariante de escala**: funciona con los
parámetros sin tocar sobre barras de 4h, y con significancia. Es mejor señal
todavía. `pullback_to_ema_short` conserva el signo y la magnitud en la variante
B, que es lo exigible, pero su patrón solo existe en la ventana larga.

*(Comparación sobre los mismos 10 activos en ambas temporalidades; el resto del
universo solo tiene barras diarias.)*

---

## 5. Dos errores de análisis propios, y cómo se detectaron

Ambos me llevaron a conclusiones equivocadas antes de corregirlos. Quedan aquí
porque el proceso importa tanto como el resultado.

### 5.1 Trocear la serie destruye el calentamiento de los indicadores

Analicé la expectativa año por año cortando cada serie en trozos anuales. Está
mal: cada trozo empieza sin historia, así que una EMA(200) no genera ninguna
señal hasta 200 barras después.

| Año | Operaciones reales | Con la serie troceada |
|---|---|---|
| 2023 | 292 | 99 |
| 2025 | 323 | 138 |
| 2026 | 241 | **1** |

Con esos datos concluí que `pullback_to_ema_short` "solo gana en años
bajistas". Era falso. **Lo correcto es ejecutar sobre la serie completa y
etiquetar después cada operación** por el régimen del día de entrada. Hecho así,
la estrategia no pierde en ningún año y tiene alfa en régimen alcista.

### 5.2 Escalar el periodo del ATR no conserva su magnitud

Al bajar a 4h escalé las ventanas ×6, incluido el periodo del ATR. Pero el ATR
de una barra de 4h vale **0,396 veces** el de una diaria (medido, idéntico en
los 10 activos; la teoría predice 1/√6 = 0,41). Un stop de "2 ATR" quedaba 2,5
veces más ajustado y dejaba de ser la misma operación.

**El síntoma fue la tasa de acierto**, que cayó del 49% al 37%. Corrigiendo los
múltiplos por 1/0,396 volvió al 50,5%.

### 5.3 Y una suposición que resultó falsa

Diseñé la puerta 2.5 creyendo que bajar de temporalidad multiplicaría la
muestra ×6. No lo hace: con una posición a la vez y una ventana económica fija,
el número de operaciones lo marca el horizonte, no las barras. Dio 404
operaciones frente a 341. Lo que multiplicó la muestra de verdad fue **pasar de
10 a 40 activos**.

---

## 6. Estado del catálogo

| Estrategia | Veredicto | Evidencia |
|---|---|---|
| **`squeeze_breakdown`** | **PASA puertas 1-3** | t=5,03; alfa en alcista; invariante de escala |
| **`pullback_to_ema_short`** | **PASA puertas 1-3** | t=3,36; 72,5% de activos; OOS +0,271 |
| `donchian_breakdown` | En observación | Positiva en ambos regímenes pero t<2 |
| `funding_fade_short` | **DESCARTADA** | La señal apunta al revés; 0/27 combinaciones |
| `failed_breakout_short` | **DESCARTADA** | t=−3,95 en cripto; negativa en los tres mercados |
| `bollinger_upper_fade` | **DESCARTADA** | t=−3,77; negativa en los tres mercados |
| `parabolic_extension_fade` | **DESCARTADA** | t=−4,52 |
| `rsi2_fade` | **DESCARTADA** | t=−4,14 |
| `volatility_spike_exhaustion` | **DESCARTADA** | t=−3,34; y el peor riesgo de ruina |
| `relative_weakness_short` | **DESCARTADA en acciones** | t=−3,24; sin pata larga no tiene argumento |
| `gap_up_fade` | Sin evaluar en cripto | Correcto: 24/7 no tiene huecos |
| `oi_flush_short` | Sin evaluar | Falta open interest |

**En acciones y futuros no sobrevive ninguna.** El catálogo entero pierde en
acciones incluso con los costes a cero.

---

## 7. Qué falta antes de tocar dinero real

Las dos que pasan han superado las puertas 1, 2, 2.5 y 3. **Falta la 4, que no
se puede acelerar:** paper trading, mínimo 60 sesiones o 50 operaciones,
comparando contra el backtest del mismo periodo.

Cuatro reservas que hay que tener presentes:

1. **Sesgo de supervivencia del universo.** Son 40 perpetuos que existen hoy en Binance; los que se deslistaron no están. Para cortos esto juega *en contra* de nuestros resultados —los que colapsaron habrían sido excelentes cortos— así que la estimación es conservadora. Pero no está medido.
2. **Un solo mercado.** Ambas funcionan en cripto y fallan en acciones y futuros. No sabemos si es una peculiaridad de cripto en 2020-2026.
3. **Un solo ciclo completo.** El histórico cubre un mercado bajista mayor (2022) y la debilidad de 2025-2026. No es mucha diversidad de regímenes.
4. **Falta el filtro de aglomeración.** En cripto, veto por open interest extremo y profundidad de libro. No está implementado.

**Siguiente paso recomendado:** montar el paper trading de `squeeze_breakdown`,
que es la más fuerte de las dos (mayor t, alfa en alcista, invariante de
escala), con tamaño mínimo y las reglas de escalado gradual de la puerta 4.
