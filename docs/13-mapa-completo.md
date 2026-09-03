# El mapa completo: las tres palancas medidas, y contra qué hay que medirlas

**Resultado corto: la configuración actual del proyecto —solo corto, solo
cripto— es la peor de todas las probadas.** La mejor encontrada (acciones y
futuros en largo) tiene Sharpe 1,13 frente al 0,56 de la actual, y su techo de
crecimiento es 64% anual en vez de 16%.

**Resultado incómodo: casi todo eso es beta, no alfa.** Este documento existe
sobre todo por el control que lo demuestra (sección 3), sin el cual el
resultado anterior sería una ilusión estadística de manual.

---

## 1. Qué se probó

`docs/11` identificó tres palancas. Aquí se mueven todas, sobre los datos que
el proyecto ya tenía (40 cripto desde 2020, 15 acciones y 11 futuros desde
2010) más un motor que ahora opera en las dos direcciones.

| # | Configuración | Ventana | CAGR | Max DD | Sharpe | Techo (S²/2) |
|---|---|---|---|---|---|---|
| A1 | Cripto, solo corto (**la actual**) | 6,7 a | +17,8% | −63% | **0,56** | 16% |
| A2 | Cripto, largo + corto | 6,7 a | +27,5% | −88% | 0,66 | 22% |
| B | 3 mercados, solo corto | 16,7 a | **−25,6%** | −99,7% | −0,34 | — |
| C | 3 mercados, largo + corto | 6,0 a | +24,5% | −85% | 0,65 | 21% |
| D | Solo futuros, largo + corto | 16,6 a | +1,7% | −63% | 0,22 | 2% |
| E | Solo acciones, en largo | 16,6 a | +17,5% | — | 1,12 | 63% |
| F | Solo futuros, en largo | 16,6 a | +8,9% | — | 0,82 | 33% |
| **G** | **Acciones + futuros, en largo** | **16,6 a** | **+23,8%** | **−66%** | **1,13** | **64%** |
| G' | Acciones + futuros, en largo | 6,0 a | +33,1% | −44% | 1,46 | 107% |

## 2. Lo que enseña, antes del control

**La pata larga no aporta alfa en cripto, aporta cobertura.** Las dos
estrategias largas **pierden dinero solas** ahí (`pullback_to_ema_long`
−11,0%, Sharpe −0,34; `squeeze_breakout_long` +0,4%). Y aun así, añadirlas
sube la cartera de 17,8% a 27,5% y el Sharpe de 0,56 a 0,66: ganan justo
cuando los cortos pierden.

**Diversificar a un mercado donde no tienes ventaja no diversifica, diluye.**
Esto corrige una afirmación previa mía. Se dijo que repartir entre los tres
mercados subiría el Sharpe por la raíz de las apuestas independientes. Es
falso: los futuros tienen la mejor correlación interna de los tres (0,21
frente al 0,56 de cripto) y en corto dan Sharpe 0,22. Más apuestas
independientes no sirven de nada si en esas apuestas no hay expectativa
positiva.

**El mandato solo-corto estaba bien fundado, y en los tres mercados es
ruinoso**: −99,3% del capital en 16,7 años (fila B). La decisión original del
catálogo era correcta con la evidencia que tenía.

## 3. El control que casi todo el mundo se salta

En un mercado que sube, la referencia de una estrategia larga **no es cero,
es el mercado**. Sin comparar contra comprar-y-mantener, cualquier estrategia
larga sobre activos que subieron parece brillante.

| Universo | Comprar y mantener | Nuestras estrategias |
|---|---|---|
| Acciones (16,6 a) | **+26,9%, Sharpe 1,07** | +17,5%, Sharpe 1,12 |
| Cripto (6,7 a) | **+40,1%, Sharpe 0,83** | +17,8%, Sharpe 0,56 |
| Futuros (16,6 a) | +6,6%, Sharpe 0,51 | +8,9%, Sharpe 0,82 |
| Acciones+futuros (16,6 a) | +18,3%, Sharpe 1,01 | +23,8%, Sharpe 1,13 |
| Acciones+futuros (6,0 a) | +24,1%, Sharpe 1,15 | +33,1%, Sharpe 1,46 |

Tres cosas se caen o se sostienen aquí:

1. **El Sharpe 1,12 de acciones en largo es beta.** Comprar y mantener esas
   mismas 15 acciones da 26,9% y Sharpe 1,07. La estrategia **rinde menos que
   no hacer nada**. El universo es AAPL, NVDA, TSLA, AMZN, META, MSFT, PLTR,
   SMCI, AMD, COIN: una cesta escogida a mano con los ganadores de la década.
   Cualquier cosa larga sobre eso luce bien.
2. **En cripto, el sistema entero rinde menos de la mitad que no hacer nada**
   (17,8% contra 40,1%). Con la diferencia de que el corto es un flujo de
   retorno que no existe pasivamente — no es lo mismo, pero hay que decirlo.
3. **Lo único que bate a su referencia de forma consistente son los futuros en
   largo** (Sharpe 0,82 contra 0,51) y la combinación acciones+futuros (1,13
   contra 1,01). Ese exceso encoge al alargar la ventana: +0,31 de Sharpe en
   los últimos 6 años, +0,12 en los 16,6 completos. Y viene con el doble de
   drawdown (−66% contra −32%).

## 4. Qué queda en pie para el objetivo del 100%

El techo de la mejor configuración (G) es 64% anual — el primero que se acerca
sin ser una fantasía. Pero hay que ser preciso sobre de qué está hecho ese
número:

- **Beta**: Sharpe 1,01 de comprar y mantener. No es una ventaja, es exponerse
  al mercado, y depende de que el mercado siga subiendo.
- **Alfa**: +0,12 de Sharpe. Real, medido sobre 16,6 años, pero modesto.

Realizar ese 64% exigiría además **apalancar hasta el óptimo de Kelly**, muy
por encima del 1% por operación actual, con los drawdowns que eso implica
(el barrido de `docs/11` mostró que pasarse lleva a la ruina, no a menos
retorno).

**Conclusión honesta sobre el 100%:** con lo medido aquí, entre 50% y 65%
anual es alcanzable en backtest con acciones y futuros en largo, dimensionado
cerca del óptimo. El 100% exigiría o bien apalancar por encima de Kelly —que
es la ruina con otro nombre— o bien una ventaja que estos datos no muestran.

## 5. Lo que este documento NO autoriza

Nada de lo de arriba ha pasado las puertas de `docs/02`. Es exploración, no
validación, y en concreto:

- Las estrategias largas **no tienen t corregido, ni meseta, ni prueba en
  reserva, ni análisis por régimen**. Son espejos sin calibrar de las cortas.
- **El universo de acciones está sesgado por selección**, y el control de la
  sección 3 lo demuestra: 15 nombres elegidos a mano que subieron mucho. Un
  resultado creíble necesita un universo construido sin mirar el pasado
  (constituyentes de un índice en cada fecha, incluidas las que quebraron).
- La ventana de 6 años que da los mejores números (Sharpe 1,46) es un mercado
  alcista excepcional. Que el exceso caiga a +0,12 al mirar 16,6 años es la
  advertencia, no un detalle.

El siguiente paso serio no es subir el tamaño ni añadir mercados: es
**construir un universo de acciones sin sesgo de supervivencia** y repetir la
fila G contra él. Si el exceso sobrevive a eso, se pre-registra y se pasa por
las cuatro puertas como cualquier otra estrategia.
