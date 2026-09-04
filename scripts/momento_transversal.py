#!/usr/bin/env python3
"""Seleccion TRANSVERSAL: rankear los activos entre si, no contra su historia.

Las catorce estrategias del catalogo son temporales: cada activo se juzga
contra su propio pasado (su EMA, su percentil de volatilidad, su interes
abierto). Ninguna ha preguntado nunca lo otro: **de los 40, cuales son los
mejores AHORA MISMO comparados entre ellos**.

Es la dimension que usa la cartera DeepSeek que trajo el usuario -un LLM
puntua cada empresa y se queda con las 10 mejores- y es tambien la familia
con mas evidencia publicada en finanzas. Aqui se prueba su version mecanica,
sin LLM: rankear por retorno pasado y quedarse con los N mejores.

Tres cosas se copian de esa cartera y se dicen:

  RANKING       comparar activos entre si en vez de contra su propia historia.
  MENSUAL       un mes de tenencia, rebalanceo al final. Menos decisiones que
                el motor diario, menos ruido y menos costes.
  CONCENTRAR    quedarse con unos pocos, no repartir entre los 40. docs/11
                midio que 40 criptos correlacionadas son 1,7 apuestas: si
                repartir no diversifica, concentrar en los mejores no
                concentra tanto riesgo como parece.

Lo que NO se copia es el LLM puntuando. No porque no pueda funcionar, sino
porque no se puede validar hacia atras: es imposible reconstruir que habria
dicho un modelo en marzo de 2024 con las noticias de esa semana, y cualquier
intento esta contaminado porque el modelo ya sabe como acabo la historia.

**El control esta dentro desde el principio**: toda variante se compara
contra comprar y mantener el MISMO universo. Sin eso, en un mercado que sube,
cualquier cosa parece que funciona (docs/14).

    python scripts/momento_transversal.py --universo cripto
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

CARPETA = {"cripto": "data/cripto/*_1d.csv",
           "diversificado": "data/diversificado/*.csv",
           "acciones": "data/acciones/*.csv"}

# Convencion estandar: se salta el ultimo mes al medir el impulso. El tramo
# mas reciente esta dominado por reversion a corto plazo, que es ruido para
# esta hipotesis y ademas es lo que mide el catalogo temporal que ya tenemos.
SALTO = 21


def cargar(universo: str, desde: str | None) -> pd.DataFrame:
    cierres = {}
    for f in sorted(glob.glob(os.path.join(RAIZ, CARPETA[universo]))):
        s = os.path.basename(f).replace("_1d.csv", "").replace(".csv", "")
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        cierres[s] = d["close"]
    px = pd.DataFrame(cierres).sort_index()
    return px.loc[desde:] if desde else px


def simular(px: pd.DataFrame, lookback: int, n: int, corto: bool,
            dias_anio: int) -> dict:
    """Cartera transversal rebalanceada mensualmente.

    En cada rebalanceo se rankea por el retorno de `lookback` dias (saltando
    el ultimo mes) y se compra el top N -y se vende el peor N si `corto`.
    """
    ret = px.pct_change()
    señal = px.shift(SALTO) / px.shift(SALTO + lookback) - 1

    fechas_rebal = px.resample("ME").last().index
    pesos = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for fecha in fechas_rebal:
        if fecha not in señal.index:
            continue
        fila = señal.loc[fecha].dropna()
        # Solo activos con precio vivo ese dia: rankear contra un activo que
        # ya no cotiza seria comprar un fantasma.
        fila = fila[px.loc[fecha, fila.index].notna()]
        if len(fila) < 2 * n:
            continue
        orden = fila.sort_values(ascending=False)
        largos = orden.index[:n]
        posterior = pesos.index > fecha
        pesos.loc[posterior, :] = 0.0
        pesos.loc[posterior, largos] = 1.0 / n
        if corto:
            pesos.loc[posterior, orden.index[-n:]] = -1.0 / n

    r = (pesos.shift(1) * ret).sum(axis=1).dropna()
    return metricas(r, dias_anio)


def metricas(r: pd.Series, dias_anio: int) -> dict:
    r = r.clip(lower=-0.95)
    eq = (1 + r).cumprod()
    años = (r.index[-1] - r.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / años) - 1 if eq.iloc[-1] > 0 else -1.0
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    sh = r.mean() / r.std() * np.sqrt(dias_anio) if r.std() > 0 else np.nan
    return {"CAGR": cagr, "DD": dd, "sharpe": sh, "retornos": r}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--universo", choices=list(CARPETA), default="cripto")
    p.add_argument("--desde", default=None)
    p.add_argument("--lookbacks", type=int, nargs="+", default=[63, 126, 252])
    p.add_argument("--n", type=int, nargs="+", default=[3, 5, 8])
    args = p.parse_args()

    px = cargar(args.universo, args.desde)
    dias_anio = 365 if args.universo == "cripto" else 252
    print(f"Universo '{args.universo}': {px.shape[1]} activos, "
          f"{px.index[0].date()} -> {px.index[-1].date()}\n")

    control = metricas(px.pct_change().mean(axis=1).dropna(), dias_anio)
    print(f"CONTROL comprar y mantener   CAGR {control['CAGR']:+7.1%}  "
          f"DD {control['DD']:+7.1%}  Sharpe {control['sharpe']:5.2f}\n")

    filas = []
    for lb in args.lookbacks:
        for n in args.n:
            for corto in (False, True):
                m = simular(px, lb, n, corto, dias_anio)
                filas.append({"lookback": f"{lb}d", "top_N": n,
                              "tipo": "largo+corto" if corto else "solo largo",
                              "CAGR": f"{m['CAGR']:+.1%}", "DD": f"{m['DD']:+.1%}",
                              "sharpe": round(m["sharpe"], 2),
                              "vs control": round(m["sharpe"] - control["sharpe"], 2)})
    t = pd.DataFrame(filas)
    print(t.to_string(index=False))
    mejor = t.loc[t["sharpe"].idxmax()]
    print(f"\nMejor Sharpe: {mejor['tipo']}, lookback {mejor['lookback']}, "
          f"top {mejor['top_N']} -> {mejor['sharpe']} "
          f"({mejor['vs control']:+} frente al control)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
