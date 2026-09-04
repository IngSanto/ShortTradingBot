#!/usr/bin/env python3
"""Corrige la curva de capital: valorar a mercado, no solo lo realizado.

`paper.py` actualiza `estado.equity` unicamente al CERRAR una posicion, y el
historial diario guarda ese valor. La curva resultante es una escalera: no se
mueve mientras hay posiciones abiertas perdiendo, y salta el dia que cierran.

Para el registro de paper trading eso da igual -el saldo realizado es el
saldo-. Pero todas las metricas de RIESGO se calcularon sobre esa escalera:
volatilidad diaria, Sharpe, peor dia, drawdown y, sobre todo, la correlacion
con el nucleo, que es el numero del que depende la propuesta entera.

El backtest de un solo activo si valora a mercado
(`equity + direccion*(cierre-entrada)*cantidad`). Esta inconsistencia entre
los dos motores es el error: se uso el que no valora para medir riesgo.

Aqui se reconstruye la curva correcta -realizado mas no realizado de las
posiciones vivas cada dia- y se compara.

    python scripts/auditoria_mtm.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.markets import get_market  # noqa: E402
from shortbot.paper import EstadoPapel, PaperBroker  # noqa: E402
from shortbot.strategies import build  # noqa: E402

from portfolio_backtest import cargar  # noqa: E402

ESTRATEGIAS = ["pullback_to_ema_short", "squeeze_breakdown"]


def simular_mtm(universo, estrategias, cfg):
    """Como portfolio_backtest.simular, pero registrando valor a mercado.

    Devuelve (equity realizada, equity a mercado, exposicion nocional).
    """
    fechas = pd.DatetimeIndex([])
    for df in universo.values():
        fechas = fechas.union(df.index)
    trabajo = []
    for nombre in estrategias:
        for simbolo, df in universo.items():
            trabajo.append((f"{nombre}|{simbolo}", df,
                            build(nombre).generate_signals(df, None)))

    estado = EstadoPapel(creado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         equity_inicial=cfg.initial_equity, equity=cfg.initial_equity)
    broker, log = PaperBroker(cfg), []
    realizada, mercado, nocional = [], [], []

    for ts in fechas:
        cierres = {}
        for clave, df, sig in trabajo:
            if ts not in df.index:
                continue
            i = df.index.get_loc(ts)
            broker._entradas_pendientes(estado, clave, df, i, log)
            broker._salidas(estado, clave, df, i, log)
            broker._nuevas_senales(estado, clave, sig, df, i, log)
            cierres[clave.split("|")[1]] = float(df["close"].iloc[i])

        # No realizado de lo que sigue abierto. En corto se gana cuando el
        # precio baja, de ahi el signo.
        no_realizado = expuesto = 0.0
        for d in estado.abiertas:
            px = cierres.get(d["simbolo"])
            if px is None:
                continue
            no_realizado += (d["precio_entrada"] - px) * d["cantidad"]
            expuesto += px * d["cantidad"]
        realizada.append((ts, estado.equity))
        mercado.append((ts, estado.equity + no_realizado))
        nocional.append((ts, expuesto / max(estado.equity + no_realizado, 1e-9)))

    idx = [t for t, _ in realizada]
    return (pd.Series([v for _, v in realizada], index=idx),
            pd.Series([v for _, v in mercado], index=idx),
            pd.Series([v for _, v in nocional], index=idx))


def metricas(eq: pd.Series) -> dict:
    r = eq.pct_change().dropna()
    años = (eq.index[-1] - eq.index[0]).days / 365.25
    return {"CAGR": eq.iloc[-1] / eq.iloc[0] ** 1 and (eq.iloc[-1] / eq.iloc[0]) ** (1 / años) - 1,
            "DD": ((eq - eq.cummax()) / eq.cummax()).min(),
            "peor_dia": r.min(),
            "sharpe": r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan}


def main() -> int:
    universo = cargar("todo")
    cfg = get_market("cripto").config(risk_per_trade=0.01)
    real, mtm, noc = simular_mtm(universo, ESTRATEGIAS, cfg)

    print("CURVA DE CAPITAL: solo realizado (lo usado) frente a valor a mercado\n")
    for etq, eq in [("realizado (lo usado hasta ahora)", real), ("valor a mercado (correcto)", mtm)]:
        m = metricas(eq)
        print(f"  {etq:34s} CAGR {m['CAGR']:+7.1%}  peor dia {m['peor_dia']:+7.2%}  "
              f"DD {m['DD']:+7.1%}  Sharpe {m['sharpe']:5.2f}")

    print(f"\n  Dias sin ningun movimiento en la curva realizada: "
          f"{(real.pct_change().abs() < 1e-12).mean():.1%}")
    print(f"  Dias sin movimiento en la curva a mercado:        "
          f"{(mtm.pct_change().abs() < 1e-12).mean():.1%}")

    print(f"\nEXPOSICION NOCIONAL (suma de posiciones abiertas / capital)")
    print(f"  mediana {noc.median():.2f}x   media {noc.mean():.2f}x   "
          f"maxima {noc.max():.2f}x")
    print(f"  dias por encima de 3x: {(noc > 3).sum()} ({(noc > 3).mean():.1%})")

    # Correlacion con el nucleo, que es el numero del que depende todo
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    px = {s: pd.read_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"),
                         index_col=0, parse_dates=True)["close"]
          for s in split["diseno"] + split["reserva"]}
    P = pd.DataFrame(px)
    val = P / P.ffill().bfill().iloc[0]
    nucleo = val.mean(axis=1).pct_change().dropna()
    for etq, eq in [("realizado", real), ("a mercado", mtm)]:
        r = eq.pct_change().dropna()
        c = r.index.intersection(nucleo.index)
        print(f"\n  rho(bot {etq}, nucleo) = {r.loc[c].corr(nucleo.loc[c]):+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
