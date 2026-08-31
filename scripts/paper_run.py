#!/usr/bin/env python3
"""Una iteracion de paper trading sobre el catalogo aprobado.

    python scripts/paper_run.py                # procesa barras nuevas
    python scripts/paper_run.py --actualizar   # descarga primero los datos
    python scripts/paper_run.py --informe      # solo el informe, sin avanzar

El estado vive en state/paper.json y se versiona en git: es el registro de la
puerta 4 y no se puede rehacer. Una operacion registrada ayer no se reinterpreta
hoy; si se pudiera, esto no seria paper trading sino otro backtest.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from shortbot.backtest import BacktestConfig  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.paper import EstadoPapel, PaperBroker, resumen  # noqa: E402
from shortbot.strategies import build  # noqa: E402

ESTADO = os.path.join(RAIZ, "state", "paper.json")
CATALOGO = os.path.join(RAIZ, "config", "catalogo.json")


def informe(estado: EstadoPapel, catalogo: dict) -> None:
    r = resumen(estado)
    print("\n" + "=" * 78)
    print("PAPER TRADING - ESTADO")
    print("=" * 78)
    print(f"Arrancado      : {estado.creado}")
    print(f"Equity         : {r['equity']:,.2f} ({r['retorno']:+.2%})")
    print(f"Operaciones    : {r['operaciones']} cerradas, "
          f"{r['abiertas']} abiertas, {r['pendientes']} pendientes")

    if r["operaciones"]:
        print(f"Expectativa    : {r['expectancy_r']:+.3f} R")
        print(f"Acierto        : {r['acierto']:.1%}   Profit factor: {r['profit_factor']:.2f}")
        print(f"Peor operacion : {r['peor_r']:+.2f} R   Costes: {r['costes']:,.2f}")

        # La comparacion que importa: paper contra lo que prometia el backtest.
        print("\n  Contraste con el backtest (puerta 4):")
        esperado = {e["id"]: e["evidencia"] for e in catalogo["aprobadas_para_paper"]}
        ops = pd.DataFrame(estado.cerradas)
        for est, g in ops.groupby("estrategia"):
            ev = esperado.get(est, {})
            back = ev.get("retraso_1_barra", {}).get("expectancy_r", ev.get("expectancy_r"))
            real = g["r_multiple"].mean()
            n = len(g)
            marca = "muestra corta" if n < 50 else ("dentro de lo esperado"
                    if back is None or real >= 0.5 * back else "POR DEBAJO")
            print(f"    {est:24s} n={n:3d}  paper {real:+.3f} R  "
                  f"vs backtest {back:+.3f} R  -> {marca}")

    if estado.abiertas:
        print("\n  Posiciones abiertas:")
        for d in estado.abiertas:
            print(f"    {d['estrategia']:24s} {d['simbolo']:10s} "
                  f"entrada {d['precio_entrada']:.4f} stop {d['stop']:.4f} "
                  f"({d['barras']}/{d['max_barras']} barras)")

    if r["operaciones"] < 50:
        faltan = 50 - r["operaciones"]
        print(f"\n  Faltan {faltan} operaciones para el minimo de la puerta 4 "
              f"(50 operaciones o 60 sesiones, lo que sea mas largo).")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--actualizar", action="store_true", help="Descarga datos antes de procesar")
    ap.add_argument("--informe", action="store_true", help="Solo informe, no avanza el estado")
    ap.add_argument("--equity", type=float, default=100_000.0)
    ap.add_argument("--riesgo", type=float, default=0.001,
                    help="Fraccion arriesgada por operacion (tramo 1 del escalado: 0,1%%)")
    ap.add_argument("--max-antiguedad", type=int, default=7,
                    help="Excluir activos cuya ultima barra sea mas antigua "
                         "que esto en dias (deslistados, feeds rotos)")
    ap.add_argument("--retraso", type=int, default=1,
                    help="Barras de retraso entre senal y ejecucion (el archivo llega con 1 dia)")
    args = ap.parse_args()

    catalogo = json.load(open(CATALOGO))
    estado = EstadoPapel.cargar(ESTADO, args.equity)

    if args.informe:
        informe(estado, catalogo)
        return 0

    if args.actualizar:
        print("Actualizando barras recientes desde el archivo diario...")
        simbolos = [os.path.basename(p).split("_")[0]
                    for p in sorted(glob.glob(os.path.join(RAIZ, "data", "cripto", "*_1d.csv")))]
        subprocess.run([sys.executable,
                        os.path.join(RAIZ, "scripts", "fetch_binance_public.py"),
                        "--recientes", "10", "--interval", "1d",
                        "--symbols", *simbolos], check=False)

    perfil = get_market("cripto")
    cfg = BacktestConfig(initial_equity=args.equity, risk_per_trade=args.riesgo,
                         costs=perfil.costs, entry_delay_bars=args.retraso)
    broker = PaperBroker(cfg)

    aprobadas = [e for e in catalogo["aprobadas_para_paper"] if e["orden_paper"] == 1]
    if not aprobadas:
        print("No hay ninguna estrategia con orden_paper=1 en el catalogo.")
        return 1
    print(f"Estrategias en paper: {', '.join(e['id'] for e in aprobadas)}")
    print(f"Riesgo por operacion: {args.riesgo:.2%}   Retraso: {args.retraso} barra(s)\n")

    ficheros = sorted(glob.glob(os.path.join(RAIZ, "data", "cripto", "*_1d.csv")))

    # Un activo cuyo historico deja de actualizarse suele estar deslistado.
    # Operar sobre datos rancios generaria senales sobre precios que ya no
    # existen, asi que se excluye en vez de arrastrarlo en silencio.
    limite = pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=args.max_antiguedad)
    vivos, rancios = [], []
    for path in ficheros:
        ultima = pd.read_csv(path, parse_dates=["date"])["date"].max()
        (vivos if ultima >= limite else rancios).append((path, ultima))
    if rancios:
        print(f"[!] Excluidos por datos rancios (>{args.max_antiguedad} dias):")
        for path, ultima in rancios:
            print(f"    {os.path.basename(path).split('_')[0]:10s} ultima barra {ultima.date()}")
        print()

    log_total = []
    for entrada in aprobadas:
        est = build(entrada["id"], **entrada.get("parametros", {}))
        for path, _ in vivos:
            simbolo = os.path.basename(path).split("_")[0]
            log = broker.procesar(estado, est, simbolo, load_csv(path))
            log_total += log

    for linea in log_total:
        print(linea)
    if not log_total:
        print("Sin barras nuevas que procesar.")

    estado.registrar_snapshot(pd.Timestamp.now("UTC").strftime("%Y-%m-%d"))
    estado.guardar(ESTADO)
    informe(estado, catalogo)
    print(f"Estado guardado en {os.path.relpath(ESTADO, RAIZ)}. "
          f"Recuerda commitearlo: es el registro de la puerta 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
