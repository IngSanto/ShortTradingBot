# Diversificación: se consigue, y no sirve de nada

**Resultado: el universo diversificado duplica las apuestas independientes
(3,5 frente a 1,7) y la cartera pierde el 91% del capital.** No es una
contradicción: es la demostración más limpia de que diversificar multiplica
una ventaja, y si la ventaja es cero, multiplica cero.

Este documento también retira un resultado anterior. El Sharpe 1,12 de
`docs/13` fila E —acciones en largo, el número que parecía la vía al 100%—
era sesgo de selección. Aquí se mide contra un universo limpio y se cae.

---

## 1. El universo, y por qué está construido así

`docs/13` dejó dos defectos medidos: 15 acciones escogidas a mano que
resultaron ser los ganadores de la década, y 40 criptos que por correlación
equivalen a 1,7 apuestas.

`data/diversificado/` los ataca con una sola decisión: **índices de clase de
activo en lugar de valores sueltos** (34 ETF, 2010-2026, `scripts/fetch_universo_diversificado.py`).

- **No hay supervivencia que sesgar.** Un índice sectorial no desaparece
  cuando a sus componentes les va mal: los sustituye. XLE existía antes del
  desplome del petróleo de 2014 y sigue existiendo; una petrolera que quebró
  no está en ninguna lista de hoy.
- **La variedad es estructural, no estadística.** Bonos, divisas y materias
  primas no se mueven con la bolsa por cómo están construidos, no porque la
  muestra haya salido así.

## 2. La diversificación SÍ se consigue

| Grupo | Activos | ρ interna | Apuestas |
|---|---|---|---|
| Renta variable sectorial | 9 | +0,641 | 1,5 |
| Renta variable por región | 6 | +0,728 | 1,3 |
| Bonos | 7 | +0,482 | 1,8 |
| Materias primas | 7 | +0,267 | 2,7 |
| Divisas | 3 | **−0,349** | 3,0 |
| **Universo completo** | **34** | **+0,263** | **3,5** |

Correlación de cada grupo **contra renta variable**, que es lo que de verdad
mide si algo diversifica:

| Divisas | Bonos | Materias | Inmobiliario | Otros sectores |
|---|---|---|---|---|
| **−0,04** | **+0,10** | +0,19 | +0,65 | +0,65 |

De 1,7 apuestas independientes se pasa a 3,5. Lo que aporta la variedad son
bonos, divisas y materias primas; los sectores de bolsa entre sí están al 0,65
y casi no cuentan como apuestas distintas (VNQ e IYR están al **0,987**: son
el mismo activo con dos nombres).

## 3. Y no sirve de nada

| Configuración | Ventana | CAGR | Max DD | Sharpe |
|---|---|---|---|---|
| Comprar y mantener el universo | 16,7 a | +4,8% | −24% | 0,50 |
| Estrategias **largas** | 16,7 a | **−13,5%** | −94% | **−0,43** |
| Largas + cortas | 16,7 a | **−44,9%** | **−100%** | −1,71 |
| Todo (diversificado + cripto + futuros) | 6,0 a | −14,2% | −95% | 0,32 |

Las mismas estrategias que sobre las 15 acciones escogidas daban Sharpe 1,12,
sobre un universo sin sesgo dan **−0,43**. Comprar y mantener este universo
—4,8% con Sharpe 0,50— bate a todo lo que hemos construido para él.

## 4. Por qué el Sharpe 1,12 era mentira, y por qué se veía venir

La cesta era AAPL, NVDA, TSLA, META, MSFT, AMZN, PLTR, SMCI, AMD, COIN.
Comprarla y no tocarla daba 26,9% anual. Sobre eso, *cualquier* regla que
esté comprada la mayor parte del tiempo parece brillante. La estrategia
rendía 17,5%: menos que no hacer nada. El Sharpe alto no medía habilidad,
medía que la cesta subió.

Hay además una razón de mecanismo, no solo estadística, y estaba a la vista
en el catálogo: de las doce estrategias probadas, **las seis que murieron con
t negativo hacían todas lo mismo, vender fuerza**. Las largas de `docs/13` son
el espejo de estrategias de continuación bajista; al invertirlas se convierten
en *comprar fuerza*, que es la misma apuesta perdedora vista del otro lado.
Que funcionaran sobre los ganadores de la década y fracasen sobre un universo
neutro es exactamente lo que predice esa lectura.

## 5. Lo que queda en pie

Tras `docs/11`, `docs/13` y este documento, el mapa de las tres palancas está
completo y solo una casilla tiene algo dentro:

| Palanca | Veredicto |
|---|---|
| Tamaño y exposición | **Cerrada.** El sistema ya opera en su óptimo (`docs/11`) |
| Pata larga | **Cerrada.** Sin ventaja sobre universo limpio: Sharpe −0,43 |
| Otros mercados | **Cerrada.** Los futuros tienen la mejor correlación interna y Sharpe 0,22; el universo diversificado, −0,43 |
| Cripto en corto | **La única ventaja real del proyecto**: Sharpe 0,56 |

Queda una carta sin jugar: la señal de **interés abierto y posicionamiento**
(`docs/12`), pre-registrada y con los datos descargándose. Es la única fuente
de información que no está en la serie de precios, y por tanto la única
candidata a producir una ventaja que hoy no existe.

**Sobre el objetivo del 100%:** este documento lo aleja, no lo acerca. La
diversificación —que era la palanca con más recorrido teórico— está medida y
no aporta, porque no hay ventaja que repartir. El sistema real sigue siendo el
de `docs/11`: 18% anual, Sharpe 0,56, con un techo de crecimiento de 16%.

**Lo que sí vale este resultado:** haber gastado tres documentos en demostrar
que tres caminos no llevan a ningún sitio es barato comparado con haber puesto
dinero en el Sharpe 1,12 de una cesta de ganadores. El control contra
comprar-y-mantener es la pieza que lo evitó, y a partir de aquí es obligatorio
en cualquier prueba con pata larga.
