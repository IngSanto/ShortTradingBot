# Reinicio del paper trading: por qué se cierra un registro y se abre otro

**5 de septiembre de 2026.** El registro de la puerta 4 arrancado el 30 de
agosto se cierra con 6 sesiones y 2 operaciones, y se abre uno nuevo.

## 1. El motivo: medía un sistema distinto del que queremos validar

El registro viejo corría sobre el código de `main`, que se quedó atrás
mientras el trabajo de auditoría avanzaba en una rama. Concretamente medía:

| | Registro cerrado | Registro nuevo |
|---|---|---|
| Estrategias | solo `pullback_to_ema_short` | `pullback_to_ema_short` + `squeeze_breakdown` |
| Filtro de eventos macro (`docs/10`) | **no aplicado** | T-1 a T+0 |
| Curva de equity | solo lo realizado | realizado + no realizado |

Las dos operaciones de ese registro salieron de un sistema que no es el que
queremos llevar a dinero real. Sumarlas con las que vengan daría una
expectativa que no corresponde a ninguno de los dos.

La alternativa era continuar y anotar la fecha del cambio. Se descartó porque
2 operaciones no aportan nada estadísticamente —el mínimo de la puerta 4 son
50— y a cambio dejarían la muestra partida para siempre.

## 2. Se archiva, no se borra

`state/archivo/paper_2026-08-30_a_2026-09-05.json` guarda el registro completo
con `motivo_cierre` escrito dentro, y el dashboard lo enseña en "Registros
anteriores". Es la única evidencia hacia delante que tiene el proyecto:
borrarla para que el historial quede limpio sería exactamente el gesto que la
puerta 4 existe para impedir.

`scripts/reiniciar_paper.py` hace las dos cosas en un solo paso y aborta si el
fichero de destino ya existe, para que un reinicio no pueda pisar a otro.

## 3. El registro nuevo declara qué mide

`EstadoPapel` tiene ahora un campo `configuracion`:

```json
{"estrategias": ["pullback_to_ema_short", "squeeze_breakdown"],
 "filtro_eventos_macro": true, "ventana_eventos": [1, 0],
 "retraso_entrada_barras": 1}
```

Sin esto, un registro es una lista de números sin procedencia: basta activar
una estrategia para que las cifras de antes y las de después dejen de ser
sumables sin que nada avise. Que sea un **campo del dataclass** y no un
atributo suelto es deliberado —`guardar()` usa `asdict()`, que solo serializa
campos, así que un atributo se habría perdido al escribir sin dar error— y hay
una prueba que lo fija.

## 4. Un fallo encontrado al probarlo

En el arranque, el recuento de vetos corría sobre todo el histórico y
anunciaba señales de años atrás como *"8 señales vetadas hoy"*. El número era
correcto y la etiqueta falsa.

Es la misma firma que los seis espejismos de `docs/18`: **un número correcto
que responde a una pregunta distinta de la que importa**. Aquí lo cazó
ejecutar el arranque y leer la salida en vez de darla por buena. El
corto-circuito de arranque va ahora antes del filtro, con prueba de regresión.

## 5. Estado de partida, verificado

- 39 activos × 2 estrategias marcados; **0 operaciones**. El motor no
  reprocesa el histórico: eso sería un backtest disfrazado de paper.
- EOSUSDT excluido por datos rancios (última barra 2025-05-21).
- Calendario macro con 147 fechas, **15 futuras** —sin fechas futuras el
  filtro no vetaría nada y el sistema parecería protegido sin estarlo.
- Riesgo 0,1% por operación. No es el 0,5% que salió óptimo en `docs/18`
  sección 7.2: la expectativa se mide en R, que es invariante al tamaño, así
  que la puerta 4 no se ve afectada. Lo que cambiaría es la amplitud de la
  curva, no si el sistema funciona.

## 6. Qué esperar

El mínimo son 50 operaciones o 60 sesiones, lo que sea más largo. Con dos
estrategias en vez de una la primera cifra llegará antes que en el registro
anterior, pero la segunda no: **no hay forma de acelerar 60 sesiones**, y ese
es el punto de esta puerta.

Lo que se mide cuando llegue: la expectativa en R contra la del backtest, y
—lo que de verdad importa para la estructura núcleo + freno de `docs/15`— la
correlación con el mercado medida en vivo, no sobre un backtest contaminado.
