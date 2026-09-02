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

*(Vacío hasta ejecutar la calibración. Se rellena con la rejilla completa,
cumpla o no.)*
