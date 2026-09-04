# Pre-registro: peso dinámico entre núcleo y freno según régimen

**Estado: PRE-REGISTRADO. Las secciones 0 a 4 se escriben antes de ejecutar
ninguna de las pruebas de validación.**

Y una advertencia que este documento necesita más que ningún otro del
proyecto: **la regla que aquí se valida no se pre-registró antes de
encontrarse.** Salió de mirar los datos. Eso obliga a un protocolo distinto y
más exigente, explicado en la sección 1.

---

## 0. Qué se propone

`docs/15` estableció que el bot no es el motor sino el freno: su valor es
`ρ = −0,257` contra una posición larga, no su rendimiento. Pero al quitar el
ciclo alcista de 2020-21 —a petición del usuario, y con razón— los papeles se
invierten:

| 2022-2026 (4,7 años) | CAGR | Sharpe |
|---|---|---|
| Núcleo (comprar y mantener) | **−25,2%** | −0,02 |
| Bot solo | **+31,8%** | 0,68 |

En un régimen el motor es el núcleo; en el otro, el bot. Un peso fijo elige
mal en uno de los dos por definición. De ahí la regla:

> **Mecanismo:** si el precio del núcleo está por encima de su media móvil de
> `M` días, pesar el núcleo con `w_alcista`; si está por debajo, pesar el
> núcleo con `w_bajista` (menor). El régimen se evalúa con el dato del día
> anterior y se aplica al siguiente, nunca con el dato del propio día.

## 1. Por qué esto NO es un pre-registro normal, y qué se hace al respecto

La regla se encontró explorando: se probaron tres pares de pesos y una sola
longitud de media (200 días), después de haber visto la tabla por subperiodos.
Los números que la hicieron atractiva —+87,5% en el periodo completo, +47,0%
sin el ciclo alcista— son, por construcción, **dentro de muestra**.

Esta sesión ya produjo tres espejismos con esa misma firma: un Sharpe 1,12 que
era sesgo de selección (`docs/14`), una señal de interés abierto cuya t
deambulaba (`docs/12`), y un momento transversal que falló en 36 celdas
(`docs/16`). No hay motivo para tratar este hallazgo con menos sospecha.

**Como la reserva de 16 activos ya se usó al construir la cartera del bot, no
queda una muestra virgen sobre la que confirmar.** En vez de fingir que sí,
la validación se hace por las cuatro vías que sí quedan disponibles, todas
fijadas ahora:

1. **Sensibilidad al parámetro** — si el efecto solo existe en `M=200` y
   desaparece en 150 o 250, es un punto ajustado.
2. **Costes reales** — cada cambio de régimen mueve capital entre dos botes.
3. **Estabilidad temporal** — tiene que ganar al peso fijo en los dos
   subperiodos, no solo en el agregado.
4. **Prueba nula** — comparar contra regímenes falsos (aleatorios con la misma
   frecuencia de cambio). Si un régimen inventado rinde parecido, lo que
   funciona es cambiar de peso, no *cuándo* se cambia.

La cuarta es la que más importa y la que no se ha hecho hasta ahora en este
proyecto.

## 2. Qué se calibra y qué no

**Se recorre, para medir meseta (no para elegir el mejor):**
- Longitud de la media: **{100, 150, 200, 250, 300}** días.
- Pares de peso: **{80/20, 70/30, 60/40}** en alcista, con el complementario
  en bajista (20/80, 30/70, 40/60).

**Fijo:**
- El indicador de régimen es la media móvil del propio núcleo. No se prueban
  otros (volatilidad, funding, amplitud): cada uno sería otra hipótesis.
- El desfase de un día entre observar y aplicar.
- Rebalanceo mensual, coherente con `docs/16`.
- El universo: cripto, los mismos 40 activos.

**No se prueba el par extremo 100/0 – 0/100** aunque fue el mejor en la
exploración. Saltar de estar totalmente dentro a totalmente fuera es una
apuesta binaria al indicador, y su buen resultado depende de acertar cada
giro; los pares intermedios degradan suavemente cuando el indicador falla, que
es lo que hay que exigirle a algo que va a llevar dinero real.

## 3. Costes que se aplican

Cada cambio de régimen implica vender de un bote y comprar en el otro. Se
cobra **0,20% sobre el capital movido** en cada cambio — comisión más
deslizamiento en cripto, del lado pesimista del perfil de costes del proyecto.

Se reporta además el **número de cambios por año**: si son muchos, el
*whipsaw* se come el resultado aunque el mecanismo sea correcto.

## 4. Criterio de éxito, fijado ahora

Sobre el universo cripto completo, con costes aplicados:

1. **Bate al mejor peso fijo** (50/50, que es el más robusto de los fijos
   entre los dos subperiodos) en **el periodo completo y en 2022-2026**, los
   dos.
2. **Meseta en el parámetro**: cumple la condición 1 en **al menos 3 de las 5
   longitudes de media**. Si solo funciona en una, se descarta.
3. **Supera la prueba nula**: el Sharpe con el régimen real debe ser mayor que
   el **percentil 95** de 200 regímenes aleatorios con la misma frecuencia de
   cambio. Esta es la condición dura: si no la pasa, el resto no importa.
4. **Rotación tolerable**: menos de 12 cambios de régimen al año. Más que eso
   es operar el ruido de la media móvil.

**Si falla cualquiera de las cuatro, se descarta y se dice así.** Y en
particular: si falla la 3, el hallazgo se registra como lo que sería —un
artefacto de haber mirado los datos antes de fijar la regla.

## 5. Resultados

*(Vacío hasta ejecutar.)*
