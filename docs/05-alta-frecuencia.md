# ¿Compensa operar con mucha frecuencia? La medida

**Pregunta que lo origina:** ¿se puede ganar con muchas operaciones al día,
cada una con una ganancia mínima, en vez de pocas operaciones con un edge
mayor? Medido con datos propios en tres temporalidades (1d, 4h, 1h) sobre los
mismos 10 perpetuos. Reproducible con `scripts/frequency_cost_analysis.py`.

**Respuesta corta: no, en este sistema no compensa.** El coste fijo por
operación no se encoge con el horizonte; el movimiento de precio que se puede
capturar, sí. Cuanto más corto el plazo, peor la proporción entre ambos — y se
mide, no es una intuición.

---

## 1. El coste no cambia; el movimiento sí

Comisión + slippage: **0,190% de ida y vuelta**, igual si operas una vez al día
o una vez por hora. Lo que cambia es el ATR (el movimiento típico de precio),
que se encoge según la raíz del tiempo:

| Temporalidad | ATR mediano | Coste / ATR | Riesgo (2×ATR) | Coste / riesgo |
|---|---|---|---|---|
| 1 día | 6,37% | 3,0% | 12,75% | **1,5%** |
| 4 horas | 2,41% | 7,9% | 4,83% | **3,9%** |
| 1 hora | 1,15% | 16,6% | 2,30% | **8,3%** |

Cada vez que se acorta el horizonte, el coste se come una fracción **mayor**
del riesgo de la operación, no menor. Al pasar de 1 día a 1 hora (24×), el
coste como fracción del riesgo se multiplica por 5,5 — muy cerca de lo que
predice la teoría (√24 ≈ 4,9).

## 2. Y el propio edge se degrada al acortar el horizonte

No es solo el coste: la fricción medida (aislando comisión+slippage del carry
del funding, que en cripto es un ingreso) crece casi exactamente como √tiempo:

| Estrategia | Fricción a 1d | Fricción a 4h | Fricción a 1h |
|---|---|---|---|
| `pullback_to_ema_short` | 0,017 R | 0,046 R | 0,100 R |
| `squeeze_breakdown` | 0,016 R | 0,047 R | 0,103 R |

Y el resultado neto, con parámetros sin reescalar (más operaciones, horizonte
real más corto):

| Estrategia | 1d | 4h | 1h |
|---|---|---|---|
| `pullback_to_ema_short` | **+0,091** R (0,15 ops/día) | −0,005 R (1,0 ops/día) | **−0,071 R** (4,1 ops/día) |
| `squeeze_breakdown` | +0,031 R (0,13 ops/día) | **+0,066 R** (0,80 ops/día) | **−0,038 R** (3,0 ops/día) |

`squeeze_breakdown` mejora en 4h (coherente con lo que ya sabíamos: es
invariante de escala) pero en 1h **también** se hunde. La frecuencia sí sube
—de 0,8 a 4 operaciones diarias contando los 10 activos, en la dirección que
se preguntaba— pero el edge por operación se vuelve negativo antes de llegar
ahí.

## 3. Lo que exigiría, en sentido inverso, un objetivo de 10 operaciones/día

`retorno_diario ≈ (operaciones/día) × (riesgo por operación) × E[R]`

| Objetivo diario | E[R] necesario con 10 ops/día al 1% de riesgo |
|---|---|
| 0,1% | +0,010 |
| 0,5% | +0,050 |
| 1,0% | +0,100 |

Con datos reales, la única casilla que se acerca es `squeeze_breakdown` a 4h
(+0,066, pero con 0,8 ops/día, no 10). En 1h, donde la frecuencia sí ronda lo
que se buscaba, **ambas estrategias dan negativo**.

## 4. Por qué el HFT real sí funciona, y qué le falta a esto

El market making y el arbitraje estadístico de alta frecuencia son un campo de
estudio real y con literatura extensa (microestructura de mercado; libros como
los de Aldridge o Chan lo tratan en detalle). Pero se sostienen en algo que
este sistema no tiene:

- **Cobrar el spread, no pagarlo** — rebates de *maker* en vez de comisión de *taker*.
- **Colocation** — prioridad de cola en microsegundos, inalcanzable sin infraestructura junto al motor de emparejamiento.
- Un tipo de edge distinto: no predicción de precio, sino proveer liquidez y capturar el diferencial comprador-vendedor muchas veces.

Sin esas tres cosas, "muchas operaciones pequeñas" con una estrategia
direccional no es market making: es pagar el coste de fricción muchas veces
con una ventaja que, medida aquí, no lo compensa.

## 5. Conclusión

`pullback_to_ema_short` en paper trading (puerta 4, en curso) sigue siendo la
vía correcta. Subir la frecuencia con las estrategias actuales no genera más
ganancia: la destruye, por dos motivos que se refuerzan — el coste pesa más
por operación y el propio patrón se debilita a esa escala. Una estrategia de
alta frecuencia genuina necesitaría una fuente de ventaja distinta (captura de
spread, no dirección de precio) y infraestructura que este proyecto no tiene
planeada.
