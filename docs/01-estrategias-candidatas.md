# Catálogo de estrategias candidatas para operar en corto

> Documento de trabajo. Cada estrategia es una **hipótesis falsable**, no una
> recomendación. El objetivo de la fase de laboratorio es descartar la mayoría.

---

## 1. Antes de elegir: por qué el lado corto no es "el largo al revés"

Esto no es pesimismo, es el punto de partida para no perder tiempo. Cinco
asimetrías estructurales juegan en contra del vendedor en corto:

| Asimetría | Qué significa en la práctica |
|---|---|
| **Deriva positiva** | La renta variable sube ~7-10% anual de media. Un corto empieza cada día con ese viento en contra. En cripto no existe esa deriva persistente: es una diferencia de fondo, no un detalle. |
| **Pérdida no acotada** | Un largo pierde como máximo el 100%. Un corto puede perder 300% en una sesión. Y llega en **hueco de apertura**, donde el stop no protege. |
| **Coste de acarreo** | El préstamo de acciones cuesta entre 0,3% y >50% anual. Cuanto más atractivo es el corto (todo el mundo lo quiere), más caro es. |
| **Convexidad al revés** | Ganas poco a menudo y pierdes mucho de golpe. Es un perfil de "vender seguros": la curva de capital sube suave y cae a plomo. |
| **Riesgo regulatorio y de recall** | Prohibiciones de cortos en pánicos, regla del *uptick*, y el prestamista puede reclamar los títulos y forzarte a cerrar en el peor momento. |

**Consecuencia de diseño:** el motor de backtesting de este repo cobra huecos
al precio de apertura, cobra el préstamo por día y prioriza el stop sobre el
objetivo cuando ambos caen en la misma barra. Un backtest de cortos que no haga
esto es publicidad, no investigación.

### Dónde sí persiste una ventaja en corto

Un edge corto sobrevive cuando cumple **al menos una** de estas condiciones:

1. **Neutraliza la deriva** — el corto es una pata de un spread (pairs, largo/corto sectorial), no una apuesta direccional.
2. **Exposición muy corta en el tiempo** — horas o pocos días: no da tiempo a que la deriva ni el préstamo se coman el resultado.
3. **Opera un desequilibrio de flujo identificable** — compradores atrapados, liquidación forzada, sobrecalentamiento del funding.
4. **Se activa solo en un régimen concreto** — y el resto del tiempo está en liquidez, en vez de forzar operaciones.

Las estrategias del catálogo están puntuadas contra estos cuatro criterios.

---

## 2. El catálogo

Diez estrategias implementadas y ejecutables hoy (`src/shortbot/strategies/`),
más cinco que requieren datos que aún no tenemos conectados.

### Familia A — Reversión: vender el exceso al alza

Tesis común: un movimiento vertical sin flujo real detrás se corrige. El edge es
estadístico y de corto plazo; la exposición debe medirse en días, no en meses.

#### A1. `rsi2_fade` — Sobrecompra extrema en tendencia bajista
- **Reglas:** RSI(2) > 90 **y** precio por debajo de la SMA(200) → corto en la apertura siguiente. Stop 2 ATR, objetivo 2 ATR, máximo 5 sesiones.
- **Por qué podría funcionar:** es la versión corta del clásico de Connors. El filtro de tendencia es lo esencial: sin él, estás vendiendo fuerza en un mercado alcista.
- **Cómo falla:** en un mercado alcista amplio el filtro de SMA(200) apenas deja operar, y cuando deja, suele ser en el suelo de una corrección. Documentalmente el lado largo de este sistema es mucho más fuerte que el corto.
- **Datos:** OHLC diario. Disponible ya.
- **Prioridad: MEDIA.** Barata de probar, expectativa modesta.

#### A2. `gap_up_fade` — Hueco alcista climático que cierra débil
- **Reglas:** apertura ≥ 1 ATR sobre el cierre previo, volumen ≥ 1,5× su media y cierre en la mitad baja del rango → corto.
- **Por qué podría funcionar:** el hueco de apertura sin noticia que lo sostenga atrae compradores minoristas al peor precio; el relleno del hueco es uno de los patrones intradía más estudiados.
- **Cómo falla:** si el hueco viene de una noticia real (resultados, aprobación regulatoria, opa), el gap no se rellena: **continúa**. Sin un filtro de noticias esta estrategia se pone corta justo delante del catalizador.
- **Datos:** idealmente **intradía** (1-5 min) para gestionar la primera hora. En diario es una aproximación pobre.
- **Prioridad: ALTA, condicionada** a conseguir datos intradía + un filtro de noticias/eventos.

#### A3. `parabolic_extension_fade` — Agotamiento tras extensión vertical
- **Reglas:** cierre ≥ 2 ATR sobre la EMA(20), tramo acumulado ≥ 8% en 5 sesiones, y **primera barra con máximo más bajo** → corto. Stop 1,5 ATR.
- **Por qué podría funcionar:** es la operativa clásica contra el *pump* de small caps de bajo flotante. La espera al máximo más bajo es lo que la convierte en operable en lugar de suicida.
- **Cómo falla:** es la estrategia con **mayor riesgo de ruina** del catálogo junto a A/C3. Vendes exactamente lo que el mercado está comprando con más euforia. Un solo GME arruina años de aciertos.
- **Datos:** necesita un **universo** de valores volátiles y de bajo flotante; sobre un índice casi nunca dispara.
- **Prioridad: BAJA para producción, ALTA como objeto de estudio.** Si entra, con el tamaño más pequeño y stop duro.

#### A4. `bollinger_upper_fade` — Fuera de banda en mercado lateral
- **Reglas:** cierre por encima de la banda superior **y** ADX < 20 (sin tendencia) → corto. Sale al volver a la media.
- **Por qué podría funcionar:** en rango, el precio revierte; el filtro de ADX es lo único que separa esto de perder dinero sistemáticamente.
- **Cómo falla:** el ADX es un indicador retrasado. Detecta que ya no hay tendencia justo cuando está empezando la siguiente.
- **Prioridad: BAJA.** La incluyo como línea base contra la que comparar: si una estrategia no bate a ésta, no vale el riesgo.

---

### Familia B — Seguimiento de tendencia bajista

Tesis común: la volatilidad se agrupa y las caídas son más rápidas que las
subidas. Se gana poco a menudo y mucho de vez en cuando.

**Coste emocional:** tasa de acierto del 30-40% y rachas largas de pérdidas. Si
no toleras eso, esta familia no es para ti aunque sea rentable.

#### B1. `donchian_breakdown` — Ruptura de mínimos con filtro de tendencia
- **Reglas:** cierre bajo el mínimo de 20 sesiones **y** EMA(50) < EMA(200) → corto. Stop 2,5 ATR, objetivo 6 ATR, salida si recupera la EMA(50).
- **Por qué podría funcionar:** es la pata corta del sistema Turtle. El seguimiento de tendencia es la anomalía con más evidencia fuera de muestra que existe, en múltiples mercados y décadas.
- **Cómo falla:** rupturas falsas en serie. En mercados con mucha intervención (recompras, liquidez de bancos centrales) los soportes se recuperan sin dar continuidad.
- **Prioridad: ALTA.** Es la referencia obligada del lado corto.

#### B2. `pullback_to_ema_short` — Rebote técnico contra la media
- **Reglas:** EMA(50) < EMA(200), el precio rebota hasta tocar la EMA(20) y la rechaza cerrando por debajo → corto. Stop 2 ATR sobre el máximo del rebote.
- **Por qué podría funcionar:** misma tesis que B1 pero con **mejor precio de entrada**: el stop cabe justo encima del rebote, así que el mismo movimiento produce un R-múltiplo mayor. Perseguir la ruptura paga el peor precio del día.
- **Cómo falla:** el rebote no se detiene en la EMA(20) y sigue hasta la EMA(50)/(200). Necesita la disciplina de no re-entrar.
- **Prioridad: MUY ALTA.** Mejor relación riesgo/beneficio que B1 con la misma tesis de fondo.

#### B3. `relative_weakness_short` — La pata corta del momentum transversal
- **Reglas:** el activo rinde ≥ 5 puntos por debajo de su índice en 63 sesiones **y** el índice está bajo su SMA(200) → corto.
- **Por qué podría funcionar:** el momentum transversal es un factor documentado en literatura académica durante décadas y en casi todos los mercados. Y sobre todo: **combinada con un largo, neutraliza la deriva** (condición 1).
- **Cómo falla:** los *momentum crashes* — los rebotes violentos de lo más castigado tras un suelo de mercado son el escenario que destruye este factor, y ocurren rápido.
- **Prioridad: MUY ALTA**, pero como parte de una cartera larga/corta, no en solitario.

---

### Familia C — Estructura de mercado y volatilidad

Tesis común: el mercado deja rastro de dónde hay órdenes. Cuando el precio va a
buscarlas y falla, deja compradores atrapados: ése es el combustible de la caída.

#### C1. `failed_breakout_short` — Barrido de liquidez / ruptura falsa
- **Reglas:** el máximo de la barra supera el máximo de 20 sesiones (se activan stops y órdenes de ruptura) pero el **cierre vuelve por debajo** de ese nivel, con volumen ≥ 1,2× la media → corto. Stop 1,5 ATR, objetivo 3 ATR.
- **Por qué podría funcionar:** es de las pocas ideas cortas con **lógica de flujo de órdenes** detrás, no solo estadística: hay un grupo identificable de compradores atrapados cuya salida alimenta la caída (condición 3). Además, stop muy ajustado → R-múltiplos altos.
- **Cómo falla:** distinguir una ruptura falsa de una consolidación antes de continuar es difícil en tiempo real. Muchas rupturas "falsas" se confirman dos días después.
- **Prioridad: MUY ALTA.** Es mi primera candidata: horizonte corto, stop ajustado y tesis causal.

#### C2. `squeeze_breakdown` — Compresión de volatilidad resuelta a la baja
- **Reglas:** el ancho de las Bandas de Bollinger en el percentil ≤25 de las últimas 120 sesiones (compresión) y pérdida del mínimo de 10 sesiones → corto.
- **Por qué podría funcionar:** el agrupamiento de volatilidad es uno de los hechos estilizados más sólidos de las series financieras. Tras la compresión viene la expansión; aquí solo se opera la bajista.
- **Cómo falla:** la compresión predice **que** habrá expansión, no su **dirección**. La mitad de las veces resuelve al alza y nos deja cortos justo antes.
- **Prioridad: MEDIA-ALTA.** Necesita un filtro direccional adicional (contexto de índice o de sector).

#### C3. `volatility_spike_exhaustion` — Clímax de volatilidad
- **Reglas:** volatilidad realizada en el percentil ≥90, subida ≥15% en 5 sesiones y primera barra bajista → corto. Máximo 5 sesiones.
- **Por qué podría funcionar:** los clímax terminan agotándose; el que aguanta cobra la reversión.
- **Cómo falla:** **es literalmente ponerse corto contra un short squeeze en curso.** El escenario de ruina no es hipotético, es el caso base.
- **Prioridad: BAJA / solo estudio.** La mantengo en el catálogo para *medir* el riesgo de squeeze, no para operarla.

---

### Familia D — Requieren datos que aún no tenemos conectados

No están implementadas porque necesitan fuentes adicionales. Dos de ellas son,
en mi opinión, las **más prometedoras de todo el documento**.

#### D1. Pairs trading / neutral al mercado — ❌ DESCARTADA (requiere pata larga)
- **Idea:** dos activos cointegrados (mismo sector, misma cadena de valor). Cuando el spread se abre más de 2 desviaciones, corto el caro y largo el barato.
- **Por qué destaca:** es la **única** familia que elimina de raíz la deriva alcista (condición 1). Tu resultado no depende de que el mercado baje. Además, el largo financia parcialmente el coste del préstamo del corto.
- **Requiere:** precios de un universo sectorial + test de cointegración (Engle-Granger o Johansen) con reestimación periódica.
- **Riesgo principal:** la relación se rompe (fusión, cambio regulatorio, un negocio que se hunde de verdad). Obligatorio un stop temporal además del de precio.
- **Prioridad: descartada** por la decisión de operar **solo en corto** (ver §4). Se documenta porque es la respuesta correcta si algún día se levanta esa restricción: es la única familia que elimina de raíz el problema nº1 del lado corto.

#### D2. Fade del funding extremo en perpetuos (cripto) → implementada como E1
- **Idea:** en los futuros perpetuos, cuando el funding se dispara en positivo, los largos apalancados están pagando a los cortos. Es una medida **directa y observable** de posicionamiento alcista saturado.
- **Por qué destaca:** cumple tres condiciones a la vez — no hay deriva estructural que combatir, el desequilibrio de flujo es medible en tiempo real (condición 3) y **cobras carry mientras esperas** en lugar de pagarlo. Es el único caso del catálogo donde el tiempo juega a tu favor estando corto.
- **Estado: ya no es pendiente.** Implementada en `src/shortbot/strategies/crypto.py` junto con la descarga de funding. Ver E1.

#### D3. Deriva post-resultados negativa (PEAD corto)
- **Idea:** tras una sorpresa negativa en resultados, el precio sigue derivando a la baja durante semanas. Anomalía documentada desde los años 60.
- **Requiere:** calendario de resultados + estimaciones de consenso (de pago o scrapeado).
- **Riesgo:** el efecto se ha ido erosionando conforme se ha popularizado.
- **Prioridad: MEDIA.** Buena tesis, dato caro.

#### D4. Filtro de aglomeración / interés corto
- **Idea:** no es una estrategia sino un **filtro de supervivencia**: vetar cortos en valores con interés corto alto sobre el flotante, días para cubrir elevados o coste de préstamo disparado.
- **Por qué importa:** es la defensa más directa contra el escenario que arruina una cuenta. Debería aplicarse a **todas** las estrategias del catálogo, no ser opcional.
- **Requiere:** datos de short interest (quincenales) y tarifa de préstamo del bróker.
- **Prioridad: ALTA como capa transversal.**

#### D5. Estacionalidad intradía (corto de sesión)
- **Idea:** en renta variable el retorno se concentra históricamente en el tramo nocturno; la sesión regular aporta mucho menos. Estar corto solo intradía elude parte de la deriva.
- **Riesgo:** el efecto es pequeño frente a los costes y se lo comen las comisiones si se opera a diario.
- **Prioridad: BAJA.** Interesante como *modulador* de las otras (cerrar antes del cierre), no como estrategia propia.

### Familia E — Específicas de perpetuos de cripto ⭐

Tesis común: en un futuro perpetuo el **funding** es una medida directa y
observable del posicionamiento. No hay que inferir el desequilibrio a partir del
precio: se lee.

#### E1. `funding_fade_short` — Fade del funding extremo
- **Reglas:** funding en el percentil ≥90 de las últimas 90 barras **y** por encima de un suelo absoluto (0,05% diario ≈ 18% anualizado) **y** barra de giro (cierre < apertura) → corto. Sale cuando el funding vuelve a su mediana.
- **Por qué destaca:** cumple tres de las cuatro condiciones a la vez. No hay deriva estructural que combatir, el desequilibrio de flujo es medible en tiempo real, y sobre todo **cobras carry mientras esperas**. Es la única estrategia del catálogo en la que el paso del tiempo juega a favor del corto.
- **Cómo falla:** el funding puede seguir extremo durante semanas en un mercado alcista fuerte. El suelo absoluto y la barra de giro existen para no vender en plena euforia, pero no eliminan el riesgo.
- **Datos:** OHLCV + histórico de funding vía `ccxt`. **Gratuito y ya implementado** (`scripts/fetch_data.py --market cripto`).
- **Prioridad: MÁXIMA.**

#### E2. `oi_flush_short` — Cascada de liquidaciones
- **Reglas:** el open interest crece ≥10% a la vez que el precio sube ≥5% en 10 barras (las posiciones nuevas son mayoritariamente largas apalancadas) y después el precio pierde el mínimo de 5 barras → corto.
- **Por qué podría funcionar:** las posiciones largas apalancadas tienen un precio de liquidación conocido y mecánico. Cuando se cruza, el exchange las cierra a mercado: venta forzada que alimenta más venta forzada. Es el mismo tipo de lógica causal que `failed_breakout_short`, pero con el combustible medido en lugar de supuesto.
- **Cómo falla:** llegar tarde. Cuando la cascada es visible en barras diarias, gran parte del movimiento ya ocurrió. Probablemente necesite temporalidad intradía.
- **Datos:** open interest histórico (`ccxt`, disponibilidad según exchange).
- **Prioridad: ALTA.**

---

## 3. Decisiones tomadas

Dos decisiones acotan el catálogo, y conviene tenerlas explícitas porque
descartan opciones que de otro modo serían las primeras candidatas:

| Decisión | Consecuencia |
|---|---|
| **Solo corto, sin cobertura larga** | Queda descartado el pairs trading (D1), que era la única familia capaz de neutralizar la deriva alcista. `relative_weakness_short` sigue en juego, pero como corto puro: pierde el beneficio de neutralización y conserva solo la señal de factor. |
| **Validar en los tres mercados** | Acciones, cripto y futuros con el mismo catálogo y costes propios de cada uno. Decide el mercado con datos, no a priori. |

**Lo que implica la primera:** al renunciar a la pata larga, el peso recae en las
otras tres condiciones de la §1 — exposición corta en el tiempo, desequilibrio de
flujo identificable, y selectividad por régimen. Las estrategias que solo
cumplían "neutraliza la deriva" ya no tienen argumento.

---

## 4. Cuánto pesa el mercado: la medida

`python scripts/compare_markets.py` ejecuta el **mismo universo de precios** y las
**mismas señales** bajo los tres perfiles. Como los precios no cambian, toda la
diferencia es atribuible a costes y carry:

| Estrategia | Acciones | Cripto | Futuros | Ventaja cripto | Barras en mercado |
|---|---|---|---|---|---|
| `relative_weakness_short` | +0,084 | **+0,238** | +0,137 | **+0,154 R** | 41 |
| `donchian_breakdown` | −0,050 | **+0,047** | −0,013 | +0,097 R | 24 |
| `squeeze_breakdown` | −0,153 | −0,070 | −0,117 | +0,083 R | 13 |
| `pullback_to_ema_short` | −0,124 | −0,045 | −0,089 | +0,079 R | 13 |
| `failed_breakout_short` | −0,271 | −0,213 | −0,238 | +0,057 R | 8 |
| `rsi2_fade` | −0,035 | −0,015 | −0,018 | +0,019 R | 5 |

**El hallazgo, y no depende de que los precios sean sintéticos:** la ventaja de
cripto es **proporcional al tiempo en mercado**. El carry es determinista dado el
número de barras; lo único que hace el precio es añadir ruido alrededor.

- Un corto en acciones **paga** ~1,19 bps/día de préstamo.
- Un corto en perpetuos **cobra** ~2,74 bps/día de funding.
- Diferencia: ~3,9 bps/día. En 40 barras son ~1,6% de nocional, del orden de magnitud de un edge entero.

**Consecuencia operativa directa:**

1. Las estrategias **de tendencia** (20-40 barras) solo tienen sentido en cripto o futuros. En acciones, el préstamo se come el resultado antes de que la tendencia lo genere.
2. Las estrategias **de horizonte corto** (4-8 barras) son casi indiferentes al mercado en cuanto a carry. Ahí la elección la deciden el riesgo de hueco (alto en acciones, inexistente en cripto 24/7) y la calidad de la ejecución.
3. En **acciones**, si insistimos en solo-corto, hay que limitarse a horizontes cortos y a valores baratos de tomar prestados. Es el mercado más difícil de los tres para este mandato, y ahora tenemos el número que lo cuantifica.

---

## 5. Orden de trabajo recomendado

> **Actualización (agosto 2026):** el orden de esta tabla ya no refleja la
> evidencia. La primera tanda de datos reales degradó `failed_breakout_short`
> (nº2 aquí) y descartó `bollinger_upper_fade` y `parabolic_extension_fade`.
> Ver [`docs/03-resultados-datos-reales.md`](03-resultados-datos-reales.md).
> Las prioridades de abajo siguen siendo válidas como *tesis*, no como resultado.

| # | Estrategia | Mercado prioritario | Por qué | Estado |
|---|---|---|---|---|
| 1 | **`funding_fade_short`** (E1) | Cripto | Única con carry a favor y flujo observable directamente | Implementada; falta descargar funding |
| 2 | **`failed_breakout_short`** (C1) | Los tres | Tesis causal, stop ajustado, horizonte corto → poco sensible al carry | Operable hoy |
| 3 | **`pullback_to_ema_short`** (B2) | Cripto / futuros | Mejor R:R de la familia mejor documentada | Operable hoy |
| 4 | **`donchian_breakdown`** (B1) | Cripto / futuros | Línea base obligatoria del seguimiento de tendencia | Operable hoy |
| 5 | **`oi_flush_short`** (E2) | Cripto | Combustible de la caída medido, no supuesto | Implementada; falta open interest |
| 6 | **`relative_weakness_short`** (B3) | Acciones | Factor sólido, pero sin pata larga pierde su mejor argumento | Operable hoy |

**Fuera de producción** (se quedan en el laboratorio): `volatility_spike_exhaustion`
y `parabolic_extension_fade` por riesgo de ruina; `bollinger_upper_fade` y
`gap_up_fade` como líneas base — esta última solo sería interesante con datos
intradía y filtro de noticias.

**Capa transversal no negociable:** el filtro de aglomeración (D4). En acciones,
veto por interés corto y coste de préstamo; en cripto, veto por open interest
extremo y profundidad de libro. Ninguna estrategia debería enviar una orden real
sin pasar por ahí.

---

## 6. Estado actual del código

Doce estrategias implementadas (familias A, B, C y E) sobre un contrato común:

```bash
pip install -r requirements.txt

python scripts/screen_strategies.py --market cripto --regimes   # criba
python scripts/compare_markets.py                               # peso del mercado
python -m pytest tests/ -q                                      # 13 pruebas
```

Sobre datos sintéticos casi todas dan expectativa negativa, y eso es la respuesta
correcta: un paseo aleatorio no contiene estructura explotable, así que tras
costes cualquier sistema debe perder. Sirve para validar que **el motor no
fabrica alfa de la nada** (`tests/test_backtest.py::test_entradas_aleatorias_sin_deriva_dan_expectativa_nula`),
no para elegir estrategia.

### El bloqueo actual

`scripts/fetch_data.py` está escrito y probado hasta donde llega sin red, pero
**no se puede ejecutar desde el entorno de desarrollo**: la política de red solo
permite registros de paquetes. Yahoo Finance, Binance, Bybit, Kraken y Stooq
devuelven todos 403 en el túnel del proxy.

Hay que ejecutarlo en una máquina con salida a internet:

```bash
python scripts/fetch_data.py --market cripto   --start 2019-01-01
python scripts/fetch_data.py --market acciones --start 2010-01-01
python scripts/fetch_data.py --market futuros  --start 2010-01-01

python scripts/screen_strategies.py --market cripto --data "data/cripto/*.csv" --robustness
```

Hasta que eso ocurra, **ninguna cifra de este documento es evidencia de edge**.
Lo que sí está validado es el instrumento de medida: el motor, los costes de
cada mercado y el efecto cuantificado del carry.
