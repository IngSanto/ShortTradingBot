# `oi_flush_short`: desapalancamiento forzado como señal de continuación

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

Tres celdas. La rejilla es deliberadamente diminuta: con doce estrategias ya
probadas, el umbral de significancia corregido es t ≥ 2,87, y cada parámetro
extra que se explora lo encarece.

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

1. t ≥ **2,87** sobre el conjunto de diseño (Bonferroni para K=12).
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

*(Vacío hasta ejecutar. Se rellena con la rejilla completa, cumpla o no.)*
