# `oi_deleverage_short`: desapalancamiento forzado como señal de continuación

> **Corrección hecha antes de calibrar.** Este documento se escribió titulado
> `oi_flush_short`, hasta descubrir que ese nombre ya existe en el registro
> (`OpenInterestFlushShort`, en `strategies/crypto.py`) y corresponde a una
> hipótesis **distinta**: interés abierto que *creció* con el precio y luego
> rompe un mínimo. Eso es un estado acumulado más un disparador; esto es un
> proceso en curso. Ver la sección 0.1 para qué se hace con las dos.

**Estado: PRE-REGISTRADO, sin calibrar.** Las secciones 0 a 5 se escriben
antes de mirar un solo resultado. La sección 6 se rellena después, gane o
pierda.

Es la primera estrategia del catálogo que usa datos que no son precio ni
volumen: interés abierto y posicionamiento (`data/metricas/`, ver
`scripts/fetch_binance_metrics.py`).

---

## 0. Por qué esta hipótesis y no otra

Dos resultados previos la eligen casi solos.

**El primero, del catálogo:** de las doce estrategias probadas, las seis que
murieron con t negativo hacían todas lo mismo — vender fuerza, apostar a que
un movimiento se agota (`bollinger_upper_fade`, `parabolic_extension_fade`,
`rsi2_fade`, `failed_breakout_short`, `volatility_spike_exhaustion`,
`funding_fade_short`). Las dos que sobrevivieron hacen lo contrario: apostar
a que un movimiento continúa. En este mercado, **fadear pierde y continuar
gana**, y es la regularidad más fuerte que ha producido el proyecto.

`funding_fade_short` importa especialmente aquí: fracasó con t = −6,82
apostando a que los largos masificados se agotan. Su veredicto fue "la señal
predice continuación alcista, no agotamiento". Cualquier hipótesis que use
posicionamiento tiene que explicar por qué no es esa otra vez.

**El segundo, de `docs/11`:** el techo del sistema no está en la expectativa
por operación sino en el Sharpe de cartera (0,56) y en que 40 activos
correlacionados al 0,561 son 1,7 apuestas independientes. Una estrategia
nueva solo acerca al objetivo si mueve **esa** cifra. Eso cambia el criterio
de éxito, y por eso la sección 5 es distinta a la de cualquier estrategia
anterior del catálogo.

### 0.1 Las dos hipótesis de interés abierto, y por qué se prueban las dos

`oi_flush_short` lleva escrito en el registro desde antes de que existieran
los datos, con sus parámetros ya fijados en código. Nunca se ha ejecutado
porque requería una columna `open_interest` que el proyecto no tenía. Eso lo
convierte, sin pretenderlo, en el pre-registro más limpio del catálogo: su
especificación es anterior al dato.

Se evalúa **tal cual está escrito**, sin tocar un parámetro. Es una sola
comparación y cero calibración.

`oi_deleverage_short` es la hipótesis nueva de este documento. Son mecanismos
distintos y opuestos en el tiempo: uno dispara cuando el apalancamiento
**se ha acumulado** y algo lo rompe; el otro cuando **se está destruyendo**.

**Consecuencia contable, asumida ahora:** el catálogo pasa de K=12 a K=14
estrategias probadas, así que el umbral de Bonferroni sube de **2,865 a
2,914**. Se aplica el nuevo a las dos, y también se deja anotado que las
estrategias ya admitidas se juzgaron con el umbral de su momento — sus t
(5,85 y 5,12) superan el nuevo con holgura, así que la corrección no cambia
ninguna decisión pasada.

## 1. La distinción que hace la hipótesis: estado contra proceso

`funding_fade_short` medía un **estado**: "hay muchos largos". Eso es una
foto, y una foto de mucha gente comprada es perfectamente compatible con que
sigan comprando. Por eso predecía continuación alcista.

Esta hipótesis mide un **proceso**: "los largos están siendo cerrados a la
fuerza, ahora mismo". No es que haya apalancamiento, es que se está
deshaciendo. El mecanismo por el que eso continúa es mecánico, no
psicológico:

1. Una liquidación forzada es una venta a mercado que el operador no elige.
2. Esa venta empuja el precio abajo, lo que cruza el margen del siguiente.
3. El libro se adelgaza según se consume, así que cada venta mueve más.

Mientras la cola de liquidaciones no se vacía, el proceso se alimenta. La
apuesta es que ese vaciado no termina dentro de la barra en la que empieza.

## 2. Mecanismo, fijado antes de calibrar nada

> Entrar corto al cierre del día `t` cuando se cumplan **las dos** cosas:
>
> 1. **El interés abierto se desploma**: la variación diaria de
>    `sum_open_interest` está en su percentil inferior `p` de los últimos
>    180 días.
> 2. **El precio cae ese mismo día**: `close < open`.

La segunda condición no es un adorno, es lo que da sentido a la primera. El
interés abierto cayendo **con el precio subiendo** son cortos cubriendo —el
proceso contrario, y una señal para la que este sistema no tiene lado. Solo
la combinación "OI se desploma **y** el precio cae" identifica largos siendo
expulsados. Confundir las dos convertiría la señal en ruido con dos causas
opuestas mezcladas.

**Salidas**: las de siempre (stop 2 ATR, objetivo 3 ATR, máximo 10 barras).
Se fijan, no se calibran — así los resultados son comparables con las doce
estrategias anteriores y no se abre una dimensión de búsqueda nueva.

## 3. Qué se calibra y qué no

**Se calibra**, y es todo:

- Percentil `p` del desplome de interés abierto: **{5%, 10%, 20%}**.

Tres celdas. La rejilla es deliberadamente diminuta: con catorce estrategias
probadas, el umbral corregido es t ≥ 2,914, y cada parámetro extra que se
explora lo encarece.

**Fijo, no se calibra:**

- La ventana del percentil (180 días). En `docs/07` percentil y ventana se
  movieron juntos y la ventana no cambió ninguna conclusión; repetirlo sería
  gastar comparaciones sin motivo nuevo.
- La confirmación de precio (`close < open`). Es parte del mecanismo
  (sección 2), no un parámetro.
- Las reglas de salida.
- La dirección: solo corto, como todo el catálogo.

**No se calibra en absoluto, porque sería otra hipótesis:** usar el ratio
long/short de las cuentas grandes contra el de la multitud. Es una idea
distinta —divergencia de posicionamiento, no desapalancamiento— y necesita
su propio pre-registro. Los datos ya están descargados, lo que no autoriza a
probarla de propina aquí.

## 4. Validación de los datos, con reglas fijadas ahora

Los datos son nuevos y nunca se han usado en este proyecto, así que se
comprueban **antes** de calibrar, con criterios que no dependen del
resultado:

- **Cobertura**: un activo entra solo si tiene dato en ≥80% de los días en
  que tiene precio. Los que no llegan se excluyen y se listan por nombre.
- **Huecos**: se reportan los tramos sin dato de más de 5 días seguidos. Un
  hueco no se rellena por interpolación —inventar interés abierto sería
  inventar la señal—; esos días simplemente no generan señal.
- **Saltos estructurales**: el interés abierto puede saltar por cambios de
  contrato o de método de Binance, no por mercado. Se reportan las
  variaciones diarias superiores al ±50%. Si aparecen agrupadas en una fecha
  común a muchos activos, es artefacto y esa fecha se excluye del universo
  entero.

## 5. Criterio de éxito

Dos niveles, y hay que pasar los dos. El primero es el de siempre; el
segundo existe porque `docs/11` demostró que el primero no basta para el
objetivo.

**Nivel 1 — admisión al catálogo** (puertas de `docs/02`, sin cambios):

1. t ≥ **2,914** sobre el conjunto de diseño (Bonferroni para K=14,
   ver 0.1).
2. Expectativa positiva en ≥ **50%** de los activos.
3. **Meseta**: al menos 2 de las 3 celdas del percentil cumplen, no una
   suelta.
4. Alfa en régimen alcista **y** bajista. Si solo gana cuando el mercado
   cae, es un seguro y se dimensiona distinto.

**Nivel 2 — relevancia para el objetivo** (nuevo, de `docs/11`):

5. Añadirla a la cartera **sube el Sharpe de cartera**. La referencia es la
   cartera actual de dos estrategias: Sharpe **0,46**, CAGR **12,0%**. Una
   tercera estrategia que pase el nivel 1 pero baje el Sharpe se documenta
   como *válida pero inútil para este objetivo*, y no se activa.

**Diagnóstico que se reporta y NO selecciona**: la correlación de sus
retornos diarios con los de las dos estrategias aprobadas. Es lo que
explicará el resultado del punto 5 —una estrategia poco correlacionada vale
más que una con más expectativa— pero la decisión la toma el Sharpe de
cartera, que ya incorpora la correlación, no un umbral inventado sobre ρ.

**Protocolo**: se calibra sobre los 24 activos de diseño. La reserva de 16 se
toca **una vez**, al final, para confirmar. Si el nivel 1 falla, no se llega
a mirar la reserva.

## 6. Resultados

**Estado: NINGUNA DE LAS DOS SE ADOPTA.** No pasan el nivel 1, así que el
nivel 2 ni se evalúa. Conjunto de diseño completo: 24 activos, todos con
cobertura del 100% tras la validación de la sección 4.

| Estrategia | n | E[R] | t | Activos positivos |
|---|---|---|---|---|
| `oi_deleverage_short` pct=5% | 803 | −0,001 | −0,03 | 42% |
| `oi_deleverage_short` pct=10% | 1.313 | −0,007 | −0,31 | 54% |
| `oi_deleverage_short` pct=20% | 1.998 | +0,024 | **+1,24** | 58% |
| `oi_flush_short` (sin tocar) | 45 | −0,232 | −1,89 | 43% |

El umbral era 2,914. La mejor celda llega a 1,24.

### 6.1 La prueba no es la t, es cómo se movió al crecer la muestra

La calibración se corrió tres veces según iba entrando la descarga. Eso da
algo más informativo que un contraste aislado:

| Activos | n (celda 20%) | t |
|---|---|---|
| 13 | 1.108 | +1,16 |
| 18 | 1.507 | +0,65 |
| **24** | **1.998** | **+1,24** |

Un efecto real crece con la muestra: la t escala con la raíz de n, así que
pasar de 1.108 a 1.998 operaciones debería haber subido un t=1,16 hasta
≈1,56 por pura aritmética. En vez de eso la t **deambula** —baja a 0,65,
vuelve a 1,24— sin tendencia. Eso no es una señal débil que necesite más
datos: es ruido, y más datos no lo van a arreglar.

El signo de E[R] hace lo mismo entre percentiles (−0,001, −0,007, +0,024).
Un mecanismo real mantiene la dirección al mover el umbral.

### 6.2 Lo que el dato nuevo sí aportó

La validación pre-registrada (sección 4) encontró que el **7 de marzo de 2022
el interés abierto vale exactamente cero en 11 de los 13 primeros activos**, y
al día siguiente vuelve. Es una caída del servicio de Binance.

Era el peor artefacto posible para esta hipótesis en concreto: un cero produce
una variación diaria del −100%, que es exactamente la señal más extrema que
`oi_deleverage_short` busca. Sin esa comprobación la estrategia habría
disparado en todos los activos el mismo día, con la señal más fuerte de toda
la muestra, por un fichero mal escrito — y habría parecido un hallazgo.

Se corrigió en la raíz, no por fechas: un interés abierto de cero no es un
valor, es la ausencia del dato (`cargar_open_interest` en `data.py`).

### 6.3 Balance

La hipótesis era razonable y el mecanismo, plausible: una liquidación forzada
es una venta que nadie elige, y la cola de liquidaciones no se vacía dentro de
la barra. Los datos dicen que no, o al menos que no en barras diarias — es
posible que el proceso se agote en horas y que a cierre de día ya no quede
nada que capturar, pero eso es otra hipótesis y necesitaría datos intradía y
su propio pre-registro.

`oi_flush_short`, con 45 operaciones y t=−1,89, tampoco funciona; su muestra
es demasiado pequeña para concluir mucho más que eso.

**Consecuencia para el catálogo**: dos estrategias más descartadas, K pasa de
14 a... 14 (ya se contaban aquí). El umbral de Bonferroni se queda en 2,914.

**Consecuencia para el objetivo del 100%**: esta era la última fuente de
información sin explorar —lo único que no está en la serie de precios. Con
ella cerrada, las cinco vías de `docs/11` y `docs/14` están agotadas y el
sistema real sigue siendo el mismo: 18% anual, Sharpe 0,56.
