#!/usr/bin/env python3
"""¿Cuanto del retorno se pierde por no limitar la exposicion simultanea?

`portfolio_backtest.py` dejo el numero incomodo: la cartera con las dos
estrategias gana 62% aritmetico (400 operaciones/año x 0,156 R x 1%) pero
solo 12% geometrico, con un drawdown del 84%. La diferencia no es un coste
ni una comision: es el peaje de componer sobre un capital que se hunde. Con
40 activos correlacionados, muchas posiciones se abren el mismo dia y una
sacudida las cobra todas a la vez.

Este barrido mide dos palancas que no son alfa -no cambian ni una señal-:

  tope   maximo de posiciones abiertas a la vez. Rechaza entradas cuando ya
         hay demasiadas, que es lo que un operador haria al ver la cuenta
         llena.
  riesgo fraccion del equity arriesgada por operacion. Importa porque el
         retorno geometrico es concavo en el tamaño: pasado un punto, subir
         el riesgo BAJA el crecimiento a largo plazo aunque suba la media.

Se barre sobre DISENO. La reserva se toca solo para confirmar el punto
elegido, una vez, igual que en docs/10.

    python scripts/sweep_exposicion.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.markets import get_market  # noqa: E402
from shortbot.paper import EstadoPapel, PaperBroker  # noqa: E402
from shortbot.risk_filters import aplicar_veto, veto_evento_macro  # noqa: E402
from shortbot.strategies import build  # noqa: E402

from portfolio_backtest import CALENDARIO, VENTANA_ADOPTADA, cargar, metricas  # noqa: E402

TOPES = [None, 12, 8, 5, 3, 2]
RIESGOS = [0.0025, 0.005, 0.01, 0.02]
ESTRATEGIAS = ["pullback_to_ema_short", "squeeze_breakdown"]


def preparar(universo: dict, estrategias: list[str], filtro_eventos: bool, retraso: int):
    """Señales por (estrategia, activo). Se calculan UNA vez para todo el barrido."""
    fechas = pd.DatetimeIndex([])
    for df in universo.values():
        fechas = fechas.union(df.index)
    veto_fechas = list(pd.read_csv(CALENDARIO)["fecha"]) if filtro_eventos else None

    trabajo = []
    for nombre in estrategias:
        for simbolo, df in universo.items():
            sig = build(nombre).generate_signals(df, None)
            if filtro_eventos:
                veto = veto_evento_macro(df.index, veto_fechas, *VENTANA_ADOPTADA,
                                         retraso_entrada=retraso)
                sig = aplicar_veto(sig, df, veto)
            trabajo.append((f"{nombre}|{simbolo}", df, sig))
    return fechas, trabajo


def simular(fechas, trabajo, cfg, tope: int | None) -> EstadoPapel:
    estado = EstadoPapel(creado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         equity_inicial=cfg.initial_equity, equity=cfg.initial_equity)
    broker = PaperBroker(cfg)
    log: list[str] = []

    for ts in fechas:
        for clave, df, sig in trabajo:
            if ts not in df.index:
                continue
            i = df.index.get_loc(ts)

            # El tope se aplica justo aqui, sobre las entradas que hoy estan
            # listas para abrirse. Se DESCARTAN, no se encolan: guardarlas
            # para mañana seria operar una señal caducada, que es otra cosa.
            if tope is not None:
                abiertas = {f"{d['estrategia']}|{d['simbolo']}" for d in estado.abiertas}
                listas = [p for p in estado.pendientes
                          if f"{p['estrategia']}|{p['simbolo']}" == clave
                          and p.get("espera", 0) == 0]
                if listas and clave not in abiertas and len(estado.abiertas) >= tope:
                    estado.pendientes = [p for p in estado.pendientes if p not in listas]
                    broker._salidas(estado, clave, df, i, log)
                    broker._nuevas_senales(estado, clave, sig, df, i, log)
                    continue

            broker._entradas_pendientes(estado, clave, df, i, log)
            broker._salidas(estado, clave, df, i, log)
            broker._nuevas_senales(estado, clave, sig, df, i, log)
        estado.registrar_snapshot(str(ts))
    return estado


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conjunto", choices=["diseno", "reserva", "todo"], default="diseno")
    p.add_argument("--retraso", type=int, default=0)
    p.add_argument("--filtro-eventos", action="store_true")
    p.add_argument("--topes", type=int, nargs="*", default=None)
    p.add_argument("--riesgos", type=float, nargs="*", default=None)
    args = p.parse_args()

    topes = ([None] + args.topes) if args.topes else TOPES
    riesgos = args.riesgos or RIESGOS

    universo = cargar(args.conjunto)
    print(f"Conjunto '{args.conjunto}': {len(universo)} activos | "
          f"filtro de eventos: {'SI' if args.filtro_eventos else 'no'} | "
          f"retraso {args.retraso}")
    fechas, trabajo = preparar(universo, ESTRATEGIAS, args.filtro_eventos, args.retraso)
    print(f"{len(trabajo)} pares (estrategia x activo), {len(fechas)} fechas\n")

    filas = []
    for riesgo in riesgos:
        cfg = get_market("cripto").config(risk_per_trade=riesgo, entry_delay_bars=args.retraso)
        for tope in topes:
            m = metricas(simular(fechas, trabajo, cfg, tope))
            filas.append({
                "riesgo": f"{riesgo:.2%}", "tope": tope or "sin tope",
                "CAGR": f"{m['cagr']:+.1%}", "max_dd": f"{m['max_drawdown']:+.1%}",
                "sharpe": round(m["sharpe"], 2), "ops": m["operaciones"],
                "ops_año": round(m["ops_por_año"]), "E[R]": round(m["expectancy_r"], 3),
                # Calmar: crecimiento por unidad de dolor. Con drawdowns de dos
                # digitos altos, el CAGR solo no distingue una cartera operable
                # de una que habria que abandonar por el camino.
                "calmar": round(m["cagr"] / abs(m["max_drawdown"]), 2) if m["max_drawdown"] else float("nan"),
            })
            print(f"  riesgo {riesgo:.2%}  tope {str(tope or 'sin'):8s} -> "
                  f"CAGR {m['cagr']:+7.1%}  DD {m['max_drawdown']:+7.1%}  "
                  f"Calmar {filas[-1]['calmar']:5.2f}  ops/año {m['ops_por_año']:.0f}")

    print("\n" + pd.DataFrame(filas).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
