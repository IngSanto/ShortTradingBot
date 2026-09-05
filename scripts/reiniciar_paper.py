#!/usr/bin/env python3
"""Cierra el registro de paper trading en curso y abre uno nuevo.

La puerta 4 vale porque no se puede rehacer: una operacion registrada ayer no
se reinterpreta hoy. Cambiar la configuracion a mitad de camino -activar una
estrategia, conectar un filtro- rompe esa garantia sin dar ningun error: las
operaciones de antes y las de despues salen de sistemas distintos y sumarlas
produce una expectativa que no corresponde a ninguno de los dos.

Por eso este script no reinicia: ARCHIVA y luego abre uno nuevo. El registro
viejo queda intacto en state/archivo/ con el motivo del cierre escrito dentro,
y el nuevo nace declarando que configuracion mide. Borrar el anterior seria
destruir la unica evidencia fuera de muestra que tiene el proyecto.

    python scripts/reiniciar_paper.py --motivo "..." [--equity 100000]
    python scripts/reiniciar_paper.py --motivo "..." --simular   # no escribe
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from shortbot.paper import EstadoPapel  # noqa: E402

ESTADO = os.path.join(RAIZ, "state", "paper.json")
ARCHIVO = os.path.join(RAIZ, "state", "archivo")
CATALOGO = os.path.join(RAIZ, "config", "catalogo.json")


def configuracion_actual() -> dict:
    """Que mide exactamente el registro que se abre.

    Se guarda dentro del estado para que dentro de dos meses no haya que
    deducirlo del historial de git: sin esto, un registro es una lista de
    numeros sin saber de que sistema salieron.
    """
    catalogo = json.load(open(CATALOGO))
    return {
        "estrategias": sorted(e["id"] for e in catalogo["aprobadas_para_paper"]
                              if e["orden_paper"] == 1),
        "filtro_eventos_macro": True,
        "ventana_eventos": [1, 0],
        "retraso_entrada_barras": 1,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--motivo", required=True,
                   help="por que se cierra el registro anterior (queda escrito en el archivo)")
    p.add_argument("--equity", type=float, default=100_000.0)
    p.add_argument("--simular", action="store_true", help="muestra lo que haria, sin escribir")
    args = p.parse_args()

    if not os.path.exists(ESTADO):
        print(f"No hay registro en {os.path.relpath(ESTADO, RAIZ)}: nada que archivar.")
        viejo = None
    else:
        viejo = json.load(open(ESTADO))
        ultima = viejo["historial"][-1]["fecha"] if viejo.get("historial") else "sin-sesiones"
        destino = os.path.join(ARCHIVO, f"paper_{viejo['creado'][:10]}_a_{ultima}.json")
        if os.path.exists(destino):
            print(f"Ya existe {os.path.relpath(destino, RAIZ)}: se aborta para no pisarlo.",
                  file=sys.stderr)
            return 1

        print("Registro que se cierra:")
        print(f"  arrancado    {viejo['creado']}")
        print(f"  sesiones     {len(viejo.get('historial', []))}")
        print(f"  cerradas     {len(viejo.get('cerradas', []))}")
        print(f"  abiertas     {len(viejo.get('abiertas', []))}  (se dan por no concluidas)")
        print(f"  equity       {viejo['equity']:,.2f}")
        print(f"  -> {os.path.relpath(destino, RAIZ)}")

        if not args.simular:
            os.makedirs(ARCHIVO, exist_ok=True)
            viejo["cerrado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            viejo["motivo_cierre"] = args.motivo
            json.dump(viejo, open(destino, "w"), indent=2, ensure_ascii=False)

    nuevo = EstadoPapel(
        creado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        equity_inicial=args.equity, equity=args.equity,
        configuracion=configuracion_actual())

    print("\nRegistro nuevo:")
    print(f"  arrancado    {nuevo.creado}")
    print(f"  equity       {args.equity:,.2f}")
    for k, v in nuevo.configuracion.items():
        print(f"  {k:24s} {v}")

    if args.simular:
        print("\n--simular: no se ha escrito nada.")
        return 0

    nuevo.guardar(ESTADO)
    print(f"\nEscrito {os.path.relpath(ESTADO, RAIZ)}. Commitealo: es el arranque del "
          f"registro nuevo y su fecha tiene que ser verificable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
