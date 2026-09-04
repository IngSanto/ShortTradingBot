#!/usr/bin/env python3
"""¿Y si el bot no es el motor de retorno, sino el freno que permite acelerar?

Toda la sesion ha medido el sistema corto contra cero: 18% anual, Sharpe 0,56,
y comparado con comprar y mantener cripto (40%, Sharpe 0,83) sale perdiendo.
Esa comparacion asume que los dos compiten por el mismo dinero.

Pero un sistema SOLO CORTO gana, por construccion, cuando el mercado cae -que
es exactamente cuando una posicion larga sufre. Si esa anticorrelacion es real
y grande, el bot no compite con la posicion larga: **reduce su drawdown**. Y
el drawdown es lo que limita cuanto se puede apalancar y componer.

La cuenta que importa entonces no es "cual de los dos rinde mas" sino:

    crecimiento(w, L) = L·μ(w) − L²·σ(w)²/2

donde `w` reparte capital entre el nucleo largo y el bot, y `L` es el
apalancamiento. Bajar σ mediante la cobertura permite subir L mas de lo que se
pierde en μ. Ese es el mecanismo, y aqui se mide si existe.

    python scripts/nucleo_cobertura.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.markets import get_market  # noqa: E402

from portfolio_backtest import cargar, metricas, simular  # noqa: E402

ESTRATEGIAS = ["pullback_to_ema_short", "squeeze_breakdown"]
DIAS_ANIO = 365


def retornos_bot() -> pd.Series:
    """Retornos diarios del sistema corto sobre todo el universo cripto."""
    universo = cargar("todo")
    cfg = get_market("cripto").config(risk_per_trade=0.01)
    estado = simular(universo, ESTRATEGIAS, cfg, filtro_eventos=False)
    eq = metricas(estado)["equity"]
    return eq.pct_change().dropna()


def retornos_nucleo() -> pd.Series:
    """Comprar y mantener el universo cripto, equiponderado y rebalanceado."""
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    cierres = {}
    for s in split["diseno"] + split["reserva"]:
        d = pd.read_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"),
                        index_col=0, parse_dates=True)
        cierres[s] = d["close"].pct_change()
    return pd.DataFrame(cierres).mean(axis=1).dropna()


def evaluar(r: pd.Series, etiqueta: str, apalancamiento: float = 1.0) -> dict:
    """Metricas de una serie de retornos diarios, con apalancamiento constante.

    El apalancamiento se aplica a los retornos y se acota en -95%: una cartera
    apalancada puede matematicamente cruzar cero, y dejar que lo haga produce
    equities negativos que no existen en la realidad -ahi te han liquidado.
    """
    rl = (r * apalancamiento).clip(lower=-0.95)
    eq = (1 + rl).cumprod()
    años = (r.index[-1] - r.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / años) - 1 if eq.iloc[-1] > 0 else -1.0
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    sharpe = rl.mean() / rl.std() * np.sqrt(DIAS_ANIO) if rl.std() > 0 else np.nan
    return {"etiqueta": etiqueta, "L": apalancamiento, "CAGR": cagr,
            "max_dd": dd, "sharpe": sharpe}


def linea(m: dict) -> str:
    return (f"  {m['etiqueta']:34s} L={m['L']:.2f}  CAGR {m['CAGR']:+7.1%}  "
            f"DD {m['max_dd']:+7.1%}  Sharpe {m['sharpe']:5.2f}")


def main() -> int:
    bot = retornos_bot()
    nucleo = retornos_nucleo()
    comun = bot.index.intersection(nucleo.index)
    bot, nucleo = bot.loc[comun], nucleo.loc[comun]
    print(f"Periodo comun: {comun[0].date()} -> {comun[-1].date()} ({len(comun)} dias)\n")

    rho = bot.corr(nucleo)
    print(f"CORRELACION entre el bot y comprar-y-mantener: {rho:+.3f}")
    print("  (si es negativa, el bot cubre; si es ~0, solo diversifica; "
          "si es positiva, no sirve para esto)\n")

    print("Cada pata por separado:")
    print(linea(evaluar(nucleo, "nucleo (comprar y mantener)")))
    print(linea(evaluar(bot, "bot (solo corto)")))

    print("\nMezclas sin apalancar (w = fraccion en el nucleo largo):")
    mejor = None
    for w in [0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        m = evaluar(w * nucleo + (1 - w) * bot, f"w={w:.0%} nucleo / {1-w:.0%} bot")
        print(linea(m))
        if mejor is None or m["sharpe"] > mejor[1]["sharpe"]:
            mejor = (w, m)

    w = mejor[0]
    mezcla = w * nucleo + (1 - w) * bot
    print(f"\nMejor Sharpe sin apalancar: w={w:.0%} -> {mejor[1]['sharpe']:.2f}")

    # Optimo de crecimiento: L* = mu / sigma^2 sobre retornos diarios.
    mu, var = mezcla.mean(), mezcla.var()
    l_opt = mu / var if var > 0 else 0
    print(f"Apalancamiento de maximo crecimiento (mu/sigma²): L* = {l_opt:.2f}\n")

    print("La misma mezcla, apalancada:")
    for L in sorted({1.0, 1.5, 2.0, 2.5, 3.0, round(l_opt, 2), round(l_opt / 2, 2)}):
        if L <= 0:
            continue
        print(linea(evaluar(mezcla, f"w={w:.0%}, apalancado", L)))

    print("\nY el nucleo solo, apalancado, para ver si la cobertura aporta algo:")
    mu_n, var_n = nucleo.mean(), nucleo.var()
    for L in sorted({1.0, 1.5, 2.0, round(mu_n / var_n, 2)}):
        if L <= 0:
            continue
        print(linea(evaluar(nucleo, "nucleo sin cobertura", L)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def rebalanceo_periodico(nucleo: pd.Series, bot: pd.Series, w: float,
                         cada: str = "ME", apalancamiento: float = 1.0) -> pd.Series:
    """Mezcla con rebalanceo REAL cada periodo, no continuo.

    Mezclar retornos diarios equivale a rebalancear todos los dias, que nadie
    hace y que ademas regala un 'bono de rebalanceo' inflado. Aqui los dos
    botes crecen solos dentro del periodo y solo se igualan al final de cada
    mes, que es como se operaria de verdad.
    """
    idx = nucleo.index
    capital, pesos = 1.0, np.array([w, 1 - w])
    serie = []
    for _, tramo in pd.DataFrame({"n": nucleo, "b": bot}).groupby(pd.Grouper(freq=cada)):
        if tramo.empty:
            continue
        botes = capital * pesos
        for _, fila in tramo.iterrows():
            r = np.array([fila["n"], fila["b"]]) * apalancamiento
            botes = botes * (1 + np.clip(r, -0.95, None))
            nuevo = botes.sum()
            serie.append((_, nuevo / capital - 1) if False else (fila.name, nuevo))
            capital_intra = nuevo
        capital = max(capital_intra, 1e-9)
    eq = pd.Series([v for _, v in serie], index=[i for i, _ in serie])
    return eq.pct_change().dropna()
