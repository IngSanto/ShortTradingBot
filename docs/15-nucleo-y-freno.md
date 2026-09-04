# El bot no es el motor: es el freno que permite acelerar

**Resultado: medido contra cero, el sistema corto rinde 12-18% y pierde
contra comprar y mantener. Medido como cobertura de una posición larga,
convierte un activo que no se puede apalancar en uno que sí.** Esa es la
diferencia entre un techo del 34% y uno del 59%.

Este documento nace de una objeción del usuario —"he conseguido 30% operando
en largo, 18% me parece poco"— que era correcta y que destapó un error de
encuadre en toda la sesión anterior: se estaba midiendo el bot **contra cero**
cuando había que medirlo **como pieza de una cartera**.

---

## 1. El error de encuadre

`docs/11` a `docs/14` comparan el bot contra comprar y mantener y concluyen
que pierde: 18% contra 40%. Esa comparación da por hecho que los dos compiten
por el mismo dinero, y por tanto que hay que elegir uno.

Pero un sistema **solo corto** gana, por construcción, cuando el mercado cae
—que es exactamente cuando una posición larga sufre. Si esa anticorrelación es
real, las dos patas no compiten: una sujeta a la otra. Y lo que sujeta un
drawdown determina cuánto se puede apalancar, que es de donde sale el
crecimiento compuesto.

## 2. La ecuación

Para una cartera con retorno medio `μ` y varianza `σ²`, apalancada `L` veces,
el crecimiento compuesto a largo plazo es aproximadamente:

```
g(w, L) = L·μ(w) − L²·σ(w)²/2
```

que se maximiza en **L\* = μ/σ²**, dando **g\* = μ²/(2σ²) = Sharpe²/2**.

Repartiendo capital entre núcleo largo y bot con peso `w`:

```
μ(w) = w·μₙ + (1−w)·μᵦ
σ(w)² = w²σₙ² + (1−w)²σᵦ² + 2·w·(1−w)·ρ·σₙ·σᵦ
```

**Todo el mecanismo está en el término `2w(1−w)ρσₙσᵦ`.** Con `ρ` negativa, ese
término resta: la varianza cae más deprisa de lo que cae el retorno. Y como
`L*` es `μ/σ²`, con σ² en el denominador, **bajar la varianza sube el
apalancamiento sostenible más de lo que baja el retorno**.

No es una idea nueva —es Markowitz y Kelly juntos—, pero sí es la lectura que
faltaba: el valor del bot no es su μ, es su ρ.

## 3. Lo medido (universo cripto completo, 2020-2026)

**Correlación entre el bot y comprar-y-mantener: −0,257.**

| Cartera | CAGR | Max DD | Sharpe | Techo (S²/2) |
|---|---|---|---|---|
| 100% núcleo (comprar y mantener) | +40,1% | −83,4% | 0,83 | 34% |
| 100% bot (solo corto) | +12,0% | −84,1% | 0,46 | 11% |
| **60% núcleo / 40% bot** | **+53,8%** | **−43,7%** | **1,09** | **59%** |

La mezcla **bate a las dos patas por separado y a la vez reduce el drawdown a
la mitad**. No es magia: es el término de covarianza negativa.

### 3.1 Lo que de verdad compra la cobertura: apalancamiento

| Apalancamiento | 60/40 con cobertura | Núcleo solo |
|---|---|---|
| L = 1,0 | +53,8% (DD −44%) | +40,1% (DD −83%) |
| L = 1,5 | +72,2% (DD −60%) | **+23,0%** (DD −98%) |
| L = 2,0 | **+79,7%** (DD −73%) | **−17,4%** (DD −99,9%) |

**Sin cobertura, apalancar destruye la posición.** Con un drawdown del 83%, un
L=1,5 ya deja el CAGR por debajo del de no apalancar, y L=2 lo pone en
negativo: la cuenta se vacía antes de poder recuperarse. Con cobertura, el
óptimo de crecimiento está en L\* = 2,09.

Esa es la aportación real del bot, y no aparece en ninguna métrica que lo mire
en solitario.

## 4. La prueba que lo separa de un espejismo

Esta sesión ya produjo un Sharpe 1,12 que resultó ser sesgo de selección
(`docs/14`). Así que la pregunta obligatoria es: ¿la cobertura funciona cuando
hace falta, o solo de media?

| Periodo | Núcleo solo | 60/40 con cobertura | ρ del tramo |
|---|---|---|---|
| 2020-21 alcista | +507% (DD −64%) | +210% (DD −44%) | −0,14 |
| **2022 bajista** | **−76,9%** (DD −78%) | **−10,6%** (DD −34%) | **−0,36** |
| 2023-24 recuperación | +96,7% (DD −57%) | +51,4% (DD −28%) | −0,28 |
| **2025-26 reciente** | **−52,7%** (DD −80%) | **−6,3%** (DD −28%) | **−0,39** |

Dos cosas, y las dos importan:

1. **La cobertura se fortalece justo cuando se necesita.** En los dos tramos
   bajistas recorta la pérdida un 85-90%, y la correlación se vuelve **más
   negativa** ahí (−0,36 y −0,39) que en el tramo alcista (−0,14). Eso no es
   un artefacto de selección: es la propiedad estructural de un sistema que
   solo puede ganar cuando el precio baja.
2. **Se paga con techo.** En el tramo alcista, 507% se queda en 210%. La
   cobertura no es gratis: es una prima que se paga en los años buenos y se
   cobra en los malos.

## 5. La parte incómoda: el retorno no es nuestro

El 40% de comprar-y-mantener está **dominado por el +507% de 2020-21**. En los
últimos dos años cripto lleva **−52,7%**. Es decir:

- El motor de retorno de esta estructura es **beta de cripto**, no una ventaja
  que hayamos construido.
- Si cripto se queda plano, la mezcla rinde aproximadamente `0,4 × 12% ≈ 5%`.
- El 53,8% del backtest **no es una expectativa**, es lo que habría pasado en
  un periodo que incluyó la mayor subida de la historia de esa clase de
  activo.

Lo único que este proyecto aporta de propio es el freno. El acelerador lo pone
el mercado, y puede no estar.

## 6. Metodología propuesta

Encaja con el plan del usuario —aportar capital periódicamente y dejar que
componga— y usa cada pieza para lo que sirve:

1. **Núcleo largo (≈60%)**: el motor. Comprar y mantener diversificado. Aquí
   está el retorno, y es beta.
2. **Bot corto (≈40%)**: el freno. No se le pide rendir, se le pide bajar el
   drawdown. Su métrica de éxito es `ρ`, no `μ`.
3. **Las aportaciones hacen de rebalanceo, gratis.** Cada aportación nueva va
   íntegra a la pata que esté por debajo de su peso objetivo. Rebalancear
   vendiendo paga impuestos y comisiones; rebalancear con dinero nuevo no
   paga ninguno de los dos. Con aportaciones periódicas, el rebalanceo deja
   de ser un coste y pasa a ser automático.
4. **Apalancamiento: empezar en 1,0.** El óptimo teórico es 2,09, pero se
   calcula sobre un pasado que incluye el mayor mercado alcista de cripto. La
   regla prudente es la mitad del óptimo (*half-Kelly*), y solo después de que
   el paper trading confirme la `ρ` en vivo.

**Sobre el peso concreto:** el 60/40 sale de maximizar el Sharpe sobre este
histórico, así que está ajustado a él. La región 50-70% da Sharpe 1,04-1,09
—es una meseta, no un pico—, lo que da cierta confianza en que no es un punto
sobreajustado, pero el número exacto no debe tomarse como precisión.

## 7. ¿Y el 100%?

Con la ecuación de la sección 2, el objetivo se traduce en algo concreto:
**hace falta Sharpe 1,41**, porque `g* = S²/2`.

| Configuración | Sharpe | Techo |
|---|---|---|
| Solo el bot (donde estábamos) | 0,56 | 16% |
| Solo comprar y mantener | 0,83 | 34% |
| **Núcleo + freno (esto)** | **1,09** | **59%** |
| Objetivo | 1,41 | 99% |

La estructura núcleo+freno **triplica el techo** frente al punto de partida y
cubre unos dos tercios de la distancia al objetivo. Lo que falta —de 1,09 a
1,41— exige una de dos cosas:

- **Una segunda cobertura descorrelacionada de la primera.** El freno actual
  es cripto-corto. Un segundo freno que actúe sobre otra cosa (bonos largos
  en pánico de riesgo, por ejemplo) reduciría más la varianza sin tocar el
  núcleo. Es la única vía que no depende de que el mercado suba.
- **Que cripto repita un ciclo como 2020-21.** Eso no es una estrategia, es
  una apuesta, y conviene llamarla por su nombre.

**Conclusión honesta:** 50-60% anual es defendible como expectativa de
backtest para esta estructura, con drawdowns del 40-45% y sabiendo que
depende de que el núcleo tenga retorno positivo. El 100% requiere o una
segunda fuente de cobertura por descubrir, o apalancamiento por encima de lo
prudente, o suerte de ciclo. Nada de eso está medido todavía.

## 8. Estado

Esto es **exploración, no validación**: no ha pasado las puertas de `docs/02`,
no tiene reserva ni pre-registro, y el peso 60/40 se eligió mirando el
resultado. Lo que sí tiene, y lo que lo distingue del Sharpe 1,12 de
`docs/13`, es un **mecanismo estructural que explica por qué debería
funcionar** —un sistema solo-corto no puede sino anticorrelacionar con el
mercado— y la comprobación por subperiodos de que la cobertura se refuerza
justo en los tramos donde se necesita.

El siguiente paso serio es pre-registrar esta estructura como hipótesis de
cartera y medir `ρ` en el paper trading en vivo, que es la única cifra de la
que depende todo lo demás.
