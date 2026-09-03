# Filtro de eventos macro (D5): veto por proximidad a fecha programada

**Estado: PRE-REGISTRADO, sin calibrar.** Las secciones 0 a 4 se escriben
**antes** de mirar un solo resultado; la sección 5 se rellenará después, gane
o pierda. Este orden es el punto entero del documento: en `docs/07` la
calibración precedió a la comprobación de si el dato era operable, y salió
caro.

---

## 0. Por qué esto, y qué lo distingue de los dos filtros anteriores

Los filtros de `docs/07` (aglomeración por activo) y `docs/08` (aglomeración
agregada) se descartaron, pero dejaron un resultado sólido: **el riesgo de
cola de este catálogo es correlacionado** — los peores días son sacudidas que
golpean a varios activos a la vez, no fallos de un activo aislado
(`docs/08`, sección 4.3, verificado: los días con ≥2 stops simultáneos bajan
de 110 a 87-102 cuando se veta por amplitud de mercado).

Lo que hundió a `docs/08` no fue el diagnóstico, fue el instrumento: la
amplitud de funding **mide la volatilidad de mercado ya en marcha**, que es
exactamente de donde `squeeze_breakdown` saca su ventaja. El veto no
distinguía riesgo de oportunidad porque ambos eran la misma señal leída al
revés.

Este filtro ataca el mismo riesgo con un instrumento que **no mira el
mercado en absoluto**. Una fecha de FOMC se conoce con meses de antelación y
no contiene información sobre si el mercado está comprimido, extendido o
rompiendo. Es la diferencia entre "hoy hay tormenta" (que es también cuando
se pesca) y "hoy es martes". Si la ventaja de `squeeze_breakdown` sobrevive
a este veto y su cola mejora, el mecanismo habrá separado lo que la amplitud
no pudo separar. Si no sobrevive, será evidencia de que su ventaja está
ligada a los días de evento en sí, que es un hallazgo distinto y también
útil.

### 0.1 Relación con el objetivo de rendimiento — y por qué no relaja nada

Este trabajo nace de la pregunta de si se puede llegar al 100% anual. Hay
que ser explícito sobre cómo un filtro podría contribuir a eso, porque no es
por la vía que parece: **un filtro de riesgo nunca añade retorno**. Solo
puede recortar la cola, y una cola más corta es lo que justifica subir de
tramo en `escalado_paper_a_real` — el retorno adicional vendría del tamaño,
no del filtro. La cadena es indirecta y hay que decirlo en voz alta para no
engañarse con ella.

**La meta de rendimiento no relaja ni un criterio de la sección 4.** Un
filtro adoptado porque "hacía falta para llegar a la cifra" sería peor que
no tener filtro: añadiría tamaño sobre una protección que no existe.

## 1. Mecanismo, fijado antes de calibrar nada

> Para cada día del calendario, marcar si está dentro de una **ventana de
> evento**: a `k` días antes o `m` días después de una fecha de **decisión
> del FOMC** o de **publicación del IPC de EEUU**. Si el día en que una
> posición **se abriría** cae dentro de esa ventana, vetar esa entrada — en
> **todos** los activos y **todas** las estrategias.

Cuatro precisiones que forman parte del mecanismo, no de la implementación:

1. **El veto se define sobre la barra de ENTRADA, no sobre la de señal.** El
   riesgo que se ataca es tener la posición abierta durante el evento, así
   que lo que importa es cuándo se abre. Con `entry_delay_bars` la entrada
   ocurre 1 o 2 barras después de la señal (`--retraso 1` en el paper
   diario), y el veto tiene que desplazarse con ella. Se deja escrito aquí
   porque aplicarlo sobre la fila de señal sería un error silencioso: vetaría
   días distintos de los que dice vetar.
2. **Es universal, como en `docs/08`.** Un evento macro es de mercado entero
   por definición; vetar solo "algunos activos" no tendría mecanismo detrás.
3. **Nunca cierra posiciones abiertas**, igual que los dos filtros
   anteriores. Ver la limitación que esto impone en la sección 3.
4. **Fecha en UTC**, la misma convención que las barras diarias de Binance.
   FOMC (≈18:00-19:00 UTC) e IPC (≈12:30-13:30 UTC) caen ambos dentro de su
   propio día UTC, así que no hay ambigüedad de frontera.

## 2. Qué se calibra y qué NO

**Se calibra** — la ventana, y nada más:

| Ventana | Días vetados alrededor del evento `T` |
|---|---|
| V0 | `{T}` |
| V1 | `{T-1, T}` |
| V2 | `{T, T+1}` |
| V3 | `{T-1, T, T+1}` |
| V4 | `{T-2, T-1, T, T+1}` |

**Fijo, no se calibra:**

- **El conjunto de eventos: FOMC + IPC de EEUU, los dos juntos.** Son los dos
  con impacto transversal documentado, ambos programados y ambos con historia
  pública completa. No se prueban variantes "solo FOMC" ni "solo IPC" ni
  versiones ampliadas (actas, NFP): serían hipótesis distintas y gastarían
  comparaciones múltiples sin mecanismo nuevo que lo justifique. El desglose
  por tipo de evento se **reporta como diagnóstico descriptivo**, no como
  dimensión de selección.
- **El carácter universal del veto** (sección 1.2).
- **El umbral de "importancia"** del evento: no existe. Todas las fechas de
  FOMC e IPC cuentan igual. Ponderar por sorpresa o por reacción esperada
  requeriría datos que no se conocen de antemano — y un filtro que necesita
  predecir deja de ser un filtro.

Se reporta la rejilla completa (5 ventanas), no el mejor punto.

### 2.1 Por qué ventanas estrechas y no `max_bars` completo

`default_max_bars = 10`: una posición abierta diez días antes de un FOMC
sigue viva durante el evento, y este filtro no la va a cerrar. Vetar los diez
días previos a cada evento se comería el calendario entero (≈20 eventos al
año), así que la cobertura es **parcial por construcción**.

Pero la parcialidad no es arbitraria: una posición abierta en `T-1` o `T`
afronta el evento con **toda su vida por delante y sin ninguna ganancia
acumulada que absorba el golpe**, mientras que una abierta en `T-8` llega con
el precio ya movido a favor o en contra y el resultado en buena parte
decidido. La configuración de máximo riesgo es precisamente la posición
recién abierta, y es la que estas ventanas cubren. Esto es razonamiento de
mecanismo, no una excusa retroactiva: queda escrito antes de ver ningún
número, y si los resultados no lo respaldan, el filtro se descarta.

## 3. Limitaciones conocidas de antemano

- **Cobertura parcial** (sección 2.1): atenúa la exposición de posiciones
  nuevas, no la exposición total.
- **Muestra de eventos pequeña**: ≈20 eventos al año, ≈80-90 en el periodo de
  diseño. Pocos eventos significa poca potencia estadística, y por eso el
  criterio de la sección 4 exige **consistencia a lo largo de la rejilla**
  en vez de significancia en una celda — un solo punto que cumpla no es
  evidencia, es la lección de `docs/07` y `docs/08`.
- **Sesgo geográfico**: son eventos de EEUU sobre un mercado que opera 24/7 y
  es global. Si el resultado sale plano, esa es una de las explicaciones
  candidatas, y no se podrá distinguir de "los eventos no importan" con estos
  datos.
- **Ventaja frente a los filtros anteriores**: el calendario macro tiene
  historia pública completa para todo el periodo, así que **no hay recorte de
  muestra** como el `2026-07-31` que impuso el funding en `docs/07` y
  `docs/08`. Se calibra sobre el periodo entero del conjunto de diseño.

## 4. Criterio de éxito, fijado ahora

Sobre el conjunto de **diseño** (24 activos; la reserva de 16 no se toca),
con las dos estrategias aprobadas:

1. **Reduce el riesgo de cola**: bajan los días con ≥2 stops simultáneos, o
   mejora el peor trade agregado.
2. **No destruye la muestra**: conserva ≥ **85%** de las operaciones. El
   listón es más alto que el 70% de `docs/08` a propósito: este filtro veta
   entre un 5% y un 15% de los días del calendario, así que si se lleva por
   delante más del 15% de las operaciones es que está mordiendo donde no
   dice morder.
3. **No hunde la expectativa**: el E[R] no cae más de un **15%** (mismo
   listón que `docs/08`, para que los tres filtros sean comparables).
4. **El mecanismo apunta en la dirección correcta** — pre-registrado aquí,
   no comprobado a posteriori: el E[R] de los trades **vetados** debe ser
   **≤** el de los conservados. Si los vetados rinden mejor, el filtro está
   quitando ventaja en vez de riesgo y **se rechaza aunque cumpla 1-3**.
   Esta condición existe porque fue exactamente lo que mató a `docs/08`, y
   allí se descubrió después; aquí se compromete antes.
5. **Ambas estrategias** cumplen a la vez (`squeeze_breakdown` y
   `pullback_to_ema_short`), como en `docs/08`.
6. **Meseta, no punto**: las condiciones 1-5 se cumplen en **al menos 3 de
   las 5 ventanas**. Una sola celda ganadora se reporta como ruido, no como
   hallazgo.

Si no hay meseta, **se descarta y se dice así**, con el mecanismo explicado
si se identifica. Mismas reglas que `docs/07` y `docs/08`.

### 4.1 Diagnósticos que se reportan pero NO seleccionan

Para entender el resultado sin contaminar el criterio, se reportará también:
el desglose FOMC vs IPC, y qué fracción de los peores trades (percentil 5%
por `r_multiple`) tiene su entrada dentro de cada ventana. Son descriptivos:
**no** se usan para elegir ventana ni para revisar los umbrales de la
sección 4 después de verlos.

## 5. Resultados

**ADOPTADO, con la ventana V1 `{T-1, T}`.** Es el primer filtro de riesgo del
catálogo que pasa: `docs/07` y `docs/08` se descartaron. Cumple el criterio de
la sección 4 en el conjunto de diseño (4 de las 5 ventanas), y la
comprobación en la reserva —16 activos que no se habían tocado— lo confirma
sin rebajarlo. Pero el efecto **no es uniforme entre estrategias**, y esa es
la parte que más importa entender (sección 5.4).

Calendario: 132 eventos (53 FOMC, 79 IPC), 2020-01-14 a 2026-08-12.

### 5.1 La rejilla en el conjunto de diseño (24 activos)

Sin filtro: `squeeze_breakdown` n=700, E[R]=+0,125 · `pullback_to_ema_short`
n=897, E[R]=+0,121 · días con ≥2 stops simultáneos: **115**.

| Ventana | `squeeze` retención / E[R] | `pullback` retención / E[R] | Días de stop simultáneo | ¿Cumple? |
|---|---|---|---|---|
| V0 `{T}` | 96,6% / 0,150 (+20%) | 97,5% / 0,139 (+15%) | 111 (−4) | sí |
| V1 `{T-1,T}` | 89,7% / 0,159 (+27%) | 91,0% / 0,152 (+26%) | 97 (−18) | sí |
| V2 `{T,T+1}` | 94,4% / 0,149 (+20%) | 93,4% / 0,133 (+10%) | 104 (−11) | sí |
| V3 `{T-1,T,T+1}` | 87,1% / 0,164 (+32%) | 86,4% / 0,146 (+21%) | 95 (−20) | sí |
| V4 `{T-2..T+1}` | **77,6%** / 0,250 | **83,5%** / 0,166 | 81 (−34) | no: retención |

El signo del resultado es el contrario al de los dos filtros anteriores: aquí
la expectativa **sube** al filtrar, en las cinco ventanas y en las dos
estrategias. V4 se cae por la única razón por la que podía caerse — se come
demasiada muestra (condición 2) —, no por perder ventaja.

### 5.2 Robustez: el retraso real del paper

Con `--retraso 1`, que es como opera el paper diario, cumplen V0, V1 y V2
(V3 se queda en 81,6% de retención para `squeeze`, por debajo del 85%). Sigue
habiendo meseta, y el efecto es si acaso mayor: con la entrada retrasada la
expectativa base cae (0,064 y 0,097) y el filtro la recupera hasta 0,074-0,156.

### 5.3 Confirmación fuera de muestra (reserva, 16 activos)

Se corrió **una vez**, con la rejilla ya fijada, sobre activos que no
intervinieron en ninguna decisión. Sin filtro: `squeeze` n=464 E[R]=+0,206 ·
`pullback` n=607 E[R]=+0,208 · días con ≥2 stops: **79**.

| Ventana | `squeeze` retención / E[R] | `pullback` retención / E[R] | Días de stop simultáneo | ¿Cumple? |
|---|---|---|---|---|
| V0 `{T}` | 96,1% / 0,242 | 99,0% / 0,213 | 72 (−7) | sí |
| V1 `{T-1,T}` | 88,4% / 0,269 | 94,4% / 0,208 | 64 (−15) | sí |
| V2 `{T,T+1}` | 95,5% / 0,235 | 95,6% / 0,201 | 74 (−5) | no: condición 4 |
| V3 `{T-1,T,T+1}` | 87,1% / 0,270 | 90,8% / 0,195 | 68 (−11) | sí |
| V4 `{T-2..T+1}` | **79,3%** / 0,342 | 86,2% / 0,233 | 55 (−24) | no: retención |

La reducción de la cola correlacionada replica limpiamente (79 → 64-74). La
mejora de expectativa **no replica igual**, y ahí está el matiz de 5.4.

### 5.4 Qué replica y qué no: el efecto lo lleva `squeeze_breakdown`

Contraste de la ventana V1, comparando los trades que el veto quitaría contra
los que deja (t de Welch y 20.000 permutaciones, `scripts/significancia_filtro_eventos.py`):

| | Diseño | Reserva |
|---|---|---|
| `squeeze_breakdown` | −0,350 R, p = 0,005 | **−0,346 R, p = 0,022** |
| `pullback_to_ema_short` | −0,310 R, p = 0,004 | −0,107 R, **p = 0,45** |
| Agregado | −0,328 R, p < 0,0001 | −0,225 R, p = 0,029 |

Para `squeeze_breakdown` el efecto **replica casi exactamente en magnitud**
(−0,350 R en diseño, −0,346 R en activos independientes): entrar en la
ventana de un evento le cuesta un tercio de R por operación, y eso no es
casualidad de la muestra de diseño.

Para `pullback_to_ema_short` **no replica**: lo que en diseño parecía un
efecto de −0,310 R se queda en −0,107 R con p=0,45 fuera de muestra, que es
indistinguible del ruido. La lectura honesta es que su resultado en diseño
era en buena parte casualidad.

Esto es el reverso exacto de `docs/08`: allí el filtro le quitaba a
`squeeze_breakdown` justo sus mejores operaciones, porque medía la
volatilidad de la que esa estrategia vive. Aquí, con un instrumento que no
mira el mercado, `squeeze_breakdown` es la estrategia a la que el filtro
protege de verdad — y `pullback_to_ema_short`, que allí pasaba de sobra, es
la que aquí no muestra efecto propio. Las dos veces la diferencia la marca
**qué mide el instrumento**, no cuál es la estrategia "buena".

`pullback_to_ema_short` sigue cumpliendo el criterio (el filtro no le hunde
la expectativa y contribuye a la reducción de días de stop simultáneo), pero
se adopta sabiendo que para ella el beneficio demostrado es el de cola, no el
de expectativa.

### 5.5 Por qué V1 y no otra

V0 y V1 son las únicas que cumplen en los **tres** pases (diseño, retraso 1 y
reserva). Entre las dos, V1 reduce mucho más la cola correlacionada (−18 y
−15 días frente a −4 y −7) con una retención todavía holgada (89-94%). La
elección dentro de la región que cumple se hizo **después** de ver las
comprobaciones de robustez, y se deja dicho: la adopción la decidió el
criterio pre-registrado sobre el diseño; la ventana concreta, la
intersección de los tres pases.

### 5.6 Diagnósticos descriptivos (no seleccionaron nada)

- **Concentración del riesgo**: la ventana V1 cubre el 10,6% de los días pero
  contiene el 21,2% de las peores operaciones (percentil 5% por R) frente al
  13,3% de las operaciones totales. El riesgo está concentrado donde el
  mecanismo dice, aproximadamente al doble de densidad.
- **FOMC vs IPC** (medido con V3): las ventanas de FOMC cubren el 6,6% de los
  días y contienen el 16,2% de las peores operaciones (2,5×); las de IPC
  cubren el 9,6% para el mismo 16,2% (1,7×). El FOMC concentra más riesgo por
  día, pero **no se separan**: el mecanismo se fijó con los dos juntos
  (sección 2) y separarlos ahora sería elegir con los resultados a la vista.

### 5.7 Look-ahead conocido y acotado

Tres de los 132 eventos no se conocían de antemano cuando ocurrieron: la
reunión de emergencia del FOMC del 15-mar-2020 y los dos IPC que el cierre
del gobierno de 2025 desplazó (24-oct y 18-dic). Un sistema en vivo no habría
tenido esas fechas en su calendario. Reejecutando la rejilla sin ellas
(`--excluir-no-programados`) el resultado no se mueve: mismas cuatro ventanas
cumplen, E[R] y días de stop simultáneo varían en la última cifra. El
look-ahead existe, está identificado y es inmaterial.

### 5.8 Balance

El filtro se adopta con la ventana V1 `{T-1, T}`. Lo que compra, en concreto:

- **Menos cola correlacionada**: −18 días con ≥2 stops simultáneos en diseño
  (115→97), −15 en la reserva (79→64). Replica en ambos conjuntos.
- **Más expectativa en `squeeze_breakdown`**: +27% en diseño, +30% en la
  reserva, con el mecanismo verificado y replicado (5.4).
- **Neutral en `pullback_to_ema_short`**: cumple el criterio, sin efecto de
  expectativa demostrable fuera de muestra.
- **Coste**: ~10% de las operaciones, y una dependencia nueva —el calendario
  macro— que hay que mantener al día. Es operable: `federalreserve.gov` y
  `bls.gov` son alcanzables desde el runner (`docs/09`), a diferencia del
  funding que hundió a `docs/07`.

Lo que **no** compra: no convierte por sí solo el catálogo en uno de 100%
anual. Un filtro no añade retorno (sección 0.1); lo que hace es acortar la
cola, que es la condición para poder discutir un tramo mayor de riesgo por
operación — y esa discusión es otra, con su propia evidencia.
