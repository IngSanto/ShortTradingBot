# El techo de crecimiento: por qué 18% y no 100%

**Resultado: la cartera actual rinde 18% anual compuesto, y ese numero no es
una casualidad de la configuracion — es su techo.** Ninguna combinacion de
tamaño y tope de exposicion lo mejora. Subir el riesgo por operacion no sube
el retorno: lo destruye.

Este documento existe porque durante toda la conversacion previa el
rendimiento anual se estimo mal, multiplicando E[R] por operaciones al año.
Aqui se mide de verdad, y sale cuatro veces menos.

---

## 1. La estimacion que estaba mal

Se venia estimando así: `E[R] x operaciones/año x riesgo` — 0,166 × 368 × 1%
≈ 61% anual. Esa cuenta ignora tres cosas, y las tres restan:

1. **Las posiciones comparten capital.** Con 40 activos, muchas se abren el
   mismo dia; no son 400 apuestas seguidas, son rachas simultaneas.
2. **El tamaño depende del equity que quede.** Tras una caida se arriesga
   menos en terminos absolutos, asi que recuperar cuesta mas que caer.
3. **El retorno compone.** Lo que importa no es la media aritmetica sino la
   geometrica, y la diferencia entre ambas crece con la volatilidad.

`scripts/portfolio_backtest.py` simula la cartera dia a dia, conduciendo las
reglas del motor de paper trading en orden cronologico y cruzando todos los
activos. No reimplementa nada: si divergiera del motor, el numero no
significaria nada.

## 2. Lo que rinde de verdad (40 activos, 6,7 años, riesgo 1%)

| Cartera | CAGR | Max drawdown | Sharpe |
|---|---|---|---|
| `pullback_to_ema_short` sola | **+17,9%** | −63,3% | 0,56 |
| `squeeze_breakdown` sola | +14,9% | −50,5% | 0,52 |
| Las dos juntas | **+12,0%** | **−84,1%** | 0,46 |

Las dos juntas rinden **menos** que cualquiera por separado. No es un error:
duplicar el numero de posiciones simultaneas sobre activos que se mueven
juntos no diversifica, apalanca.

La brecha que lo explica: 400 operaciones/año × 0,156 R × 1% = **62%
aritmetico**, contra **12% geometrico** observado. Esos 50 puntos son el
peaje de componer sobre un capital que se hunde.

## 3. El barrido: no hay configuracion que lo arregle

Rejilla completa de {riesgo por operacion} × {tope de posiciones simultaneas}
sobre el conjunto de diseño, con el filtro de eventos activo
(`scripts/sweep_exposicion.py`):

| Riesgo | Sin tope | 12 | 8 | 5 | 3 |
|---|---|---|---|---|---|
| **1%** | **+18,0%** (DD −57%) | +10,3% | +7,8% | +8,0% | +5,0% |
| **2%** | +4,0% (DD −90%) | +8,6% | +9,2% | +13,3% | +8,9% |
| **4%** | **ruina** (DD −101%) | −24,4% | −6,4% | +15,0% | +12,7% |
| **8%** | **ruina** | **ruina** | −69,0% | −10,0% | +7,7% |

Tres lecturas, ninguna agradable:

- **El maximo es el punto donde ya estabamos.** 1% de riesgo sin tope, 18%.
- **Subir el riesgo destruye capital.** Al 4% sin tope la cuenta se vacia. No
  es que rinda menos: desaparece.
- **Los topes compran suavidad, no retorno.** Reducen el drawdown a la mitad
  y suben el Calmar, pero recortan el CAGR porque recortan operaciones.

## 4. Por qué: el sistema ya está en su optimo de crecimiento

Para una estrategia con Sharpe anualizado `S`, el crecimiento geometrico
maximo alcanzable —apostando el tamaño optimo, ni mas ni menos— es
aproximadamente **S²/2**:

| Sharpe | Crecimiento maximo |
|---|---|
| 0,56 (el nuestro) | **15,7%** |
| 1,00 | 50% |
| **1,41** | **99%** |
| 2,00 | 200% |

El Sharpe medido de `pullback_to_ema_short` es 0,56 → techo 15,7%. El CAGR
observado es 17,9%. **El sistema ya opera esencialmente en su optimo de
Kelly**, y por eso el barrido no encuentra nada mejor: no hay dinero sobre la
mesa que recoger con el tamaño, porque ya se esta recogiendo.

## 5. La causa raiz: 40 activos son 1,7 apuestas

Correlacion media entre los 40 perpetuos del universo: **0,561**.

Con esa correlacion, el numero de apuestas efectivamente independientes es:

```
1 / (1/40 + (39/40) × 0,561) = 1,7
```

**No hay 40 posiciones. Hay 1,7.** Toda la diversificacion del sistema es
aparente: cuando el mercado se mueve, se mueve entero. Por eso el drawdown
llega al 84% con las dos estrategias, y por eso añadir activos no ayuda —
añade correlacion, no independencia.

Esto no es un defecto de las estrategias. Es la estructura del mercado al que
el mandato limita el sistema.

## 6. Qué haria falta para 100%, en concreto

El objetivo deja de ser "encontrar una estrategia que gane mas" y pasa a ser
una cantidad concreta: **subir el Sharpe de cartera de 0,56 a ~1,41**, dos
veces y media. Solo hay tres formas, y conviene saber cual esta bloqueada:

| Vía | Qué exigiria | Estado |
|---|---|---|
| **Más ventaja por operacion** | E[R] de 0,155 a ~0,40 | **Abierta.** Requiere una señal materialmente mejor, no un ajuste |
| **Menos correlacion** | Bajar ρ de 0,56 | **Bloqueada por mandato:** solo-corto y solo-cripto. Es un unico factor |
| **Selección de regimen** | Operar solo cuando la ventaja es fuerte | **Abierta, parcialmente explotada** (el filtro de eventos hizo algo de esto) |

La vía de la correlacion es la que mas Sharpe daria y es la unica cerrada por
decision propia, no por evidencia: `solo_corto` y `mercado_unico_cripto` son
decisiones del catalogo, no hallazgos. Mientras sigan en pie, el sistema tiene
1,7 apuestas independientes y el techo se calcula sobre eso.

## 7. Lo que este documento NO dice

No dice que 100% sea imposible. Dice que **no se alcanza con el tamaño**, que
es donde se estaba buscando, y que exige multiplicar por 2,5 la calidad
ajustada por riesgo. Tambien dice que el sistema actual, al 18% con
drawdowns del 57%, esta bien construido pero opera en un mercado de un solo
factor con un mandato de un solo lado.

La busqueda que sigue —señales de interes abierto y posicionamiento, datos
que este sistema nunca ha usado— se juzga contra ese numero: si no mueve el
Sharpe, no acerca al objetivo por mucho que suba el E[R] de una estrategia
aislada.
