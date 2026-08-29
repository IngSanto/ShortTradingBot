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

#### D1. Pairs trading / neutral al mercado ⭐
- **Idea:** dos activos cointegrados (mismo sector, misma cadena de valor). Cuando el spread se abre más de 2 desviaciones, corto el caro y largo el barato.
- **Por qué destaca:** es la **única** familia que elimina de raíz la deriva alcista (condición 1). Tu resultado no depende de que el mercado baje. Además, el largo financia parcialmente el coste del préstamo del corto.
- **Requiere:** precios de un universo sectorial + test de cointegración (Engle-Granger o Johansen) con reestimación periódica.
- **Riesgo principal:** la relación se rompe (fusión, cambio regulatorio, un negocio que se hunde de verdad). Obligatorio un stop temporal además del de precio.
- **Prioridad: MÁXIMA.**

#### D2. Fade del funding extremo en perpetuos (cripto) ⭐
- **Idea:** en los futuros perpetuos, cuando el funding se dispara en positivo, los largos apalancados están pagando a los cortos. Es una medida **directa y observable** de posicionamiento alcista saturado.
- **Por qué destaca:** cumple tres condiciones a la vez — no hay deriva estructural que combatir, el desequilibrio de flujo es medible en tiempo real (condición 3) y **cobras carry mientras esperas** en lugar de pagarlo. Es el único caso del catálogo donde el tiempo juega a tu favor estando corto.
- **Requiere:** histórico de funding + open interest (API de Binance/Bybit vía `ccxt`).
- **Riesgo principal:** riesgo de contraparte/exchange y liquidaciones en cascada. El tamaño lo es todo.
- **Prioridad: MÁXIMA** si aceptamos operar cripto.

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

---

## 3. Mi recomendación: por dónde empezar

Ordenadas por probabilidad de sobrevivir a una validación seria:

| # | Estrategia | Familia | Por qué está aquí | Qué necesita |
|---|---|---|---|---|
| 1 | **Pairs / neutral al mercado** (D1) | Spread | Elimina la deriva, el problema nº1 del corto | Universo sectorial + cointegración |
| 2 | **Fade de funding** (D2) | Cripto | Cobras carry mientras esperas; flujo observable | API de exchange (`ccxt`) |
| 3 | **`failed_breakout_short`** (C1) | Estructura | Tesis causal, stop ajustado, exposición corta | Nada: **operable hoy** |
| 4 | **`pullback_to_ema_short`** (B2) | Tendencia | Mejor R:R de la familia mejor documentada | Nada: **operable hoy** |
| 5 | **`relative_weakness_short`** (B3) | Factor | Factor académico sólido; ideal como pata corta | Índice de referencia |
| 6 | **`donchian_breakdown`** (B1) | Tendencia | Línea base obligatoria del seguimiento de tendencia | Nada: **operable hoy** |

**Descartadas de entrada para dinero real** (se mantienen en el laboratorio):
`volatility_spike_exhaustion` y `parabolic_extension_fade` por riesgo de ruina;
`bollinger_upper_fade` como mera línea base.

**Y una capa que no es negociable:** el filtro de aglomeración (D4) por encima de
todo lo demás. Ninguna estrategia de este catálogo debería enviar una orden real
sobre un valor difícil de tomar prestado o con interés corto extremo.

---

## 4. La decisión que condiciona todo lo demás

Antes de invertir horas de validación hay que fijar el **mercado**, porque cambia
qué estrategias tienen sentido:

| | Acciones (EEUU/EU) | Cripto (perpetuos) | Futuros (índices, materias primas) |
|---|---|---|---|
| Deriva en contra | Alta (~8%/año) | No persistente | Baja |
| Coste de estar corto | Préstamo 0,3-50% | **Funding: a menudo cobras** | Casi nulo |
| Riesgo de squeeze | Alto en small caps | Alto (liquidaciones) | Bajo |
| Restricciones | Uptick rule, prohibiciones, recall | Ninguna | Ninguna |
| Horario | Sesión + huecos nocturnos | 24/7, **sin huecos** | Casi 24h |
| Datos históricos | Buenos y baratos | Excelentes y gratuitos | Buenos |
| Capital mínimo | Cuenta de margen (25k USD para day trading en EEUU) | Bajo | Medio-alto |

**Lectura honesta:** para un bot *short-only*, cripto y futuros son terreno
estructuralmente más favorable que las acciones. En acciones, el planteamiento
que más probabilidades tiene de funcionar no es *short-only* sino **largo/corto
neutral**. Si el requisito es que el bot solo opere en corto y en acciones,
estamos eligiendo el escenario más difícil de los tres: se puede, pero conviene
saberlo antes de invertir meses.

---

## 5. Estado actual del código

Las diez estrategias de las familias A, B y C están implementadas y pasan la
criba automática:

```bash
pip install -r requirements.txt
python scripts/screen_strategies.py --regimes --robustness
python -m pytest tests/ -q
```

Sobre datos sintéticos **todas dan expectativa negativa**, y eso es la respuesta
correcta: un paseo aleatorio con deriva positiva no contiene ninguna estructura
explotable, así que tras costes cualquier sistema debe perder. Sirve para
validar que **el motor no fabrica alfa de la nada** (`tests/test_backtest.py`),
no para elegir estrategia. Esa elección exige datos reales — el siguiente paso.
