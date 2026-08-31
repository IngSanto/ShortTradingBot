# Filtro de aglomeración (D4): veto por funding extremo negativo

**Estado: NO ADOPTADO.** No cumple el criterio de éxito pre-registrado, y por
el camino se encontró y corrigió un fallo real de infraestructura. Las
secciones 1 a 3 se escribieron antes de calibrar nada. La sección 4, después.

---

## 1. El problema que ataca

Es un **filtro de riesgo, no una estrategia**: nunca genera una entrada, solo
puede **vetar** una que la estrategia ya quería abrir. Ataca la asimetría más
peligrosa del corto — el *short squeeze* — con el equivalente en perpetuos del
interés corto / días para cubrir que se usa en acciones (`docs/01`, D4).

**Mecanismo, fijado antes de calibrar nada:**

> Vetar una entrada nueva en corto si el funding del activo está en su
> **percentil extremo negativo** de los últimos N días. Funding muy negativo
> significa que los cortos ya están pagando a los largos: el lado corto de ese
> activo ya está masificado, que es justo el ingrediente de un apretón que
> jugaría en contra de abrir uno más ahí.

Es la traducción directa del D4 original (que pedía datos de acciones que no
existen en perpetuos) al dato equivalente que sí tenemos.

## 2. Qué se calibra y qué NO se calibra

**Se calibra** (parámetros de implementación de un mecanismo ya fijado):
- Percentil de corte: {5%, 10%, 15%, 20%}
- Ventana de cálculo del percentil: {60, 90, 120} días

**No se calibra**, porque cambiarlo sería otra hipótesis, no un ajuste de
parámetros: la dirección del veto (negativo, no positivo — eso ya lo probamos
y falló al revés con `funding_fade_short`), ni qué dato se usa (funding, no
otra cosa).

Se reporta **la rejilla completa**, no el mejor punto: si un solo punto de 12
se ve bien y el resto no, es ruido, no una calibración válida.

## 3. Criterio de éxito, fijado ahora

El filtro se adopta si, sobre el conjunto de diseño (24 activos), para **ambas**
estrategias aprobadas, existe una región amplia de la rejilla (no un solo punto)
donde se cumplen las tres condiciones a la vez:

1. **Reduce el riesgo de cola**: el peor trade mejora, o la frecuencia de
   `gap_stop` baja, de forma consistente (no en un único parámetro suelto).
2. **No destruye la muestra**: conserva al menos el 70% de las operaciones
   originales. Un filtro que veta la mitad de las oportunidades no es un
   ajuste fino, es cambiar de estrategia.
3. **No hunde la expectativa**: el E[R] tras el filtro no cae más de un 15%
   respecto al original. Reducir cola a costa de la expectativa entera no es
   una mejora neta, hay que verlo explícitamente.

**Si ninguna región de la rejilla cumple las tres a la vez, el filtro se
descarta y se dice así.** No se persigue una combinación que solo funcione en
un punto aislado.

## 4. Resultados

### 4.1 Primer hallazgo: un hueco de datos que casi falsea la prueba

La primera pasada de la rejilla (sobre los 40 activos con toda su historia)
dio un resultado sospechoso: el peor trade era **idéntico, a tres decimales,
en las 12 combinaciones de cada estrategia**. Investigando: 23 de los 24
activos de diseño tenían solo **3% de cobertura de funding en los últimos 30
días**, y ahí caían los peores trades de la muestra.

Causa: el archivo estático de Binance solo publica `fundingRate` en ficheros
**mensuales**, nunca diarios (confirmado, un fichero diario da 404). El
actualizador incremental que alimenta el paper trading en vivo solo refrescaba
velas, nunca funding — el dato quedaba congelado en la última descarga mensual
completa (31 de julio) mientras los precios seguían actualizándose a diario.

Se intentó cerrar el hueco con la API en tiempo real de Binance
(`fapi.binance.com`) como alternativa para el mes en curso. **Confirmado en
los logs de una ejecución real de GitHub Actions: bloqueada también ahí**
(0/40 símbolos, `HTTPError`), igual que en este entorno de desarrollo. Es un
bloqueo geográfico de Binance que alcanza a ambas infraestructuras — no hay
ninguna vía disponible para mantener el funding fresco en este sistema. El
intento quedó apagado por defecto (costaba ~7 minutos por ejecución diaria
para un resultado que siempre falla).

**Consecuencia para el propio filtro, más allá de esta calibración:** aunque
el mecanismo hubiera funcionado, no sería adoptable en producción tal como
está montado el pipeline de datos — el funding solo se puede refrescar cuando
Binance cierra el archivo mensual, con hasta ~30 días de desfase. Un filtro de
aglomeración necesita el dato fresco por definición; uno con un mes de retraso
no protege de nada que esté pasando ahora.

### 4.2 La calibración limpia, con cobertura real de funding

Repetida sobre el tramo con cobertura completa (hasta 2026-07-31, el último
día del último mes archivado):

| Estrategia | Combinaciones que cumplen | Mejor caso |
|---|---|---|
| `squeeze_breakdown` | **1 de 12** | percentil 20%, ventana 60d — mejora el peor trade en +0,001 R |
| `pullback_to_ema_short` | **0 de 12** | ninguna |

El peor trade **no mejora de forma significativa en ninguna de las 24
combinaciones evaluadas**. El único punto que técnicamente cumple el criterio
lo hace por un margen de +0,001 R — es exactamente el caso que la sección 3
dijo que no cuenta ("no se persigue una combinación que solo funcione en un
punto aislado").

**Según el criterio pre-registrado, el filtro NO se adopta.**

### 4.3 Por qué, probablemente

Los peores trades de este catálogo no vienen de que el activo concreto ya
tuviera el lado corto masificado: vienen de movimientos que sacuden a **varios
activos a la vez el mismo día** (el ejemplo que disparó la investigación del
hueco de datos —RUNE, SUI y XLM tocando stop el mismo 19 de agosto— es
exactamente eso). Un veto calculado sobre el funding de *ese* activo no tiene
por qué anticipar un evento que afecta al mercado entero.

**No se persigue aquí.** Sería una hipótesis distinta —funding agregado del
mercado, no por activo— y necesitaría su propia pre-registración si se quiere
probar más adelante.

### 4.4 Balance

El filtro de aglomeración por funding individual, tal como se diseñó, **no
reduce el riesgo de cola de ninguna de las dos estrategias aprobadas**, y
además no sería operable en vivo aunque lo hiciera. Se descarta.

Lo que sí queda, y tiene valor más allá de esta prueba concreta:
- Corregido un fallo real en la actualización diaria (`fusionar()` no rellenaba
  huecos en fechas ya guardadas).
- Confirmado y documentado, con evidencia de un runner real, que la API en vivo
  de Binance no es una vía disponible para este proyecto.
- Identificada una pista concreta para un filtro de aglomeración *agregado* de
  mercado, no probada aquí.

