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
from shortbot.risk_filters import veto_evento_macro  # noqa: E402
from shortbot.strategies import build  # noqa: E402

ESTADO = os.path.join(RAIZ, "state", "paper.json")
CATALOGO = os.path.join(RAIZ, "config", "catalogo.json")
CALENDARIO = os.path.join(RAIZ, "data", "eventos", "calendario_macro.csv")
# Ventana adoptada en docs/10, seccion 5.5: se veta la entrada que caeria la
# vispera o el mismo dia de un FOMC o una publicacion del IPC.
VENTANA_EVENTOS = (1, 0)


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
    ap.add_argument("--sin-filtro-eventos", action="store_true",
                    help="desactiva el filtro macro adoptado en docs/10")
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
        # Vuelto a 10 (no 35). La ventana ancha solo tenia sentido para que la
        # API en vivo pudiera rellenar el hueco de funding de todo el mes -esa
        # via esta confirmada bloqueada (docs/07, seccion 4.1) y apagada por
        # defecto, asi que ampliar la ventana ya no rellena nada de funding,
        # solo pide 3,5x mas ficheros diarios de velas sin ningun beneficio.
        # Medido: 35 dias tardaba ~51s para 3 simbolos -> ~11 min para los 40,
        # justo lo que se vio atascado en un run real. Con 10, ~3 min.
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

    # El filtro de eventos macro (docs/10, ADOPTADO). Si el calendario no
    # alcanza al futuro no puede vetar nada, y entonces callarse seria el peor
    # de los fallos: el sistema parecería estar protegido sin estarlo.
    fechas_evento = None
    if not args.sin_filtro_eventos and os.path.exists(CALENDARIO):
        cal = pd.read_csv(CALENDARIO)
        fechas_evento = list(cal["fecha"])
        futuras = (pd.to_datetime(cal["fecha"]) > pd.Timestamp.now("UTC").tz_localize(None)).sum()
        print(f"Filtro de eventos macro: {len(fechas_evento)} fechas, {futuras} futuras "
              f"(ventana T-{VENTANA_EVENTOS[0]} a T+{VENTANA_EVENTOS[1]})")
        if futuras == 0:
            print("[!] El calendario no tiene eventos futuros: el filtro NO vetaria nada. "
                  "Ejecuta scripts/fetch_calendario_macro.py")
    elif args.sin_filtro_eventos:
        print("Filtro de eventos macro: DESACTIVADO por --sin-filtro-eventos")
    else:
        print("[!] Sin calendario de eventos: el filtro no se aplica")

    log_total = []
    # Ultimo cierre de cada activo, para valorar a mercado lo que quede abierto.
    # Sin esto la curva diaria solo refleja lo realizado y no se mueve mientras
    # hay posiciones vivas, que es como mirar el saldo del banco ignorando lo
    # que tienes invertido.
    ultimos_precios: dict[str, float] = {}
    for entrada in aprobadas:
        est = build(entrada["id"], **entrada.get("parametros", {}))
        for path, _ in vivos:
            simbolo = os.path.basename(path).split("_")[0]
            df = load_csv(path)
            ultimos_precios[simbolo] = float(df["close"].iloc[-1])
            veto = (veto_evento_macro(df.index, fechas_evento, *VENTANA_EVENTOS,
                                      retraso_entrada=args.retraso)
                    if fechas_evento else None)
            log = broker.procesar(estado, est, simbolo, df, veto)
            log_total += log

    for linea in log_total:
        print(linea)
    if not log_total:
        print("Sin barras nuevas que procesar.")

    estado.registrar_snapshot(pd.Timestamp.now("UTC").strftime("%Y-%m-%d"),
                              ultimos_precios)
    estado.guardar(ESTADO)
    informe(estado, catalogo)
    print(f"Estado guardado en {os.path.relpath(ESTADO, RAIZ)}. "
          f"Recuerda commitearlo: es el registro de la puerta 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
