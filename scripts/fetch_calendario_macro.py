#!/usr/bin/env python3
"""Descarga las fechas de eventos macro del pre-registro (docs/10, seccion 1).

Dos fuentes, las dos publicas y sin clave:

  FOMC  federalreserve.gov. Se leen los enlaces a las ACTAS
        (`fomcminutes<AAAAMMDD>`), no a los comunicados: solo las reuniones
        de verdad tienen actas, mientras que los comunicados incluyen cosas
        que no son reuniones -el 2025-08-22 (Jackson Hole) o las actuaciones
        de emergencia de marzo de 2020 aparecerian como si lo fueran.

  IPC   bls.gov, indice de notas de prensa archivadas. La URL de cada nota
        (`cpi_MMDDAAAA.htm`) ES la fecha de publicacion real, no la
        programada: recoge sin esfuerzo las irregularidades (el IPC de
        octubre de 2025 salio el dia 24, y el de noviembre no salio).
        Deducir las fechas de una regla ("mediados de mes") las habria dado
        por buenas.

Escribe data/eventos/calendario_macro.csv, que es lo que consume la
calibracion. El CSV se versiona: si manana la Fed reorganiza su web, la
calibracion de ayer sigue siendo reproducible.

    python scripts/fetch_calendario_macro.py [--desde 2020]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SALIDA = os.path.join(RAIZ, "data", "eventos", "calendario_macro.csv")

FOMC_CALENDARIO = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FOMC_HISTORICO = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{anio}.htm"
BLS_ARCHIVO = "https://www.bls.gov/bls/news-release/cpi.htm"

# El BLS rechaza con 403 los agentes de herramienta conocidos (curl, urllib)
# y tambien las cadenas que contienen una URL. Un nombre simple pasa.
AGENTE = "ShortTradingBot"


def descargar(url: str) -> str:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fechas_fomc(desde: int) -> tuple[set[str], list[str]]:
    """Fechas de decision del FOMC. Devuelve (fechas, avisos)."""
    avisos: list[str] = []
    html = descargar(FOMC_CALENDARIO)
    actas = {_iso(d) for d in re.findall(r"fomcminutes(\d{8})", html)}

    # Una reunion reciente aun no tiene actas publicadas (salen ~3 semanas
    # despues). Se detecta comparando con los comunicados, que salen el mismo
    # dia, y se avisa en vez de rellenar a ojo.
    comunicados = {_iso(d) for d in re.findall(r"monetary(\d{8})a?\.htm", html)}
    posteriores = {f for f in comunicados if actas and f > max(actas)}
    if posteriores:
        avisos.append(f"FOMC: reuniones sin actas todavia, NO incluidas: {sorted(posteriores)}")

    anios_en_pagina = {int(f[:4]) for f in actas}
    for anio in range(desde, min(anios_en_pagina) if anios_en_pagina else desde):
        try:
            actas |= {_iso(d) for d in re.findall(r"fomcminutes(\d{8})",
                                                  descargar(FOMC_HISTORICO.format(anio=anio)))}
        except Exception as e:  # noqa: BLE001
            avisos.append(f"FOMC {anio}: no se pudo leer el historico ({e})")

    return {f for f in actas if int(f[:4]) >= desde}, avisos


def fechas_ipc(desde: int) -> tuple[set[str], list[str]]:
    """Fechas de publicacion del IPC de EEUU. Devuelve (fechas, avisos)."""
    html = descargar(BLS_ARCHIVO)
    fechas = {f"{d[4:]}-{d[:2]}-{d[2:4]}" for d in re.findall(r"cpi_(\d{8})\.htm", html)}
    return {f for f in fechas if int(f[:4]) >= desde}, []


def _iso(aaaammdd: str) -> str:
    return f"{aaaammdd[:4]}-{aaaammdd[4:6]}-{aaaammdd[6:]}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=int, default=2020,
                   help="primer año a incluir (por defecto 2020: los datos empiezan en 2020-10)")
    args = p.parse_args()

    fomc, avisos_fomc = fechas_fomc(args.desde)
    ipc, avisos_ipc = fechas_ipc(args.desde)
    for aviso in avisos_fomc + avisos_ipc:
        print(f"AVISO  {aviso}", file=sys.stderr)

    filas = sorted([(f, "fomc") for f in fomc] + [(f, "ipc") for f in ipc])
    if not filas:
        print("No se obtuvo ninguna fecha: se aborta sin escribir.", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w") as fh:
        fh.write("fecha,tipo\n")
        for fecha, tipo in filas:
            fh.write(f"{fecha},{tipo}\n")

    print(f"{len(filas)} eventos -> {os.path.relpath(SALIDA, RAIZ)}")
    print(f"  FOMC {len(fomc):3d}  ({min(fomc)} -> {max(fomc)})")
    print(f"  IPC  {len(ipc):3d}  ({min(ipc)} -> {max(ipc)})")
    for anio in sorted({f[:4] for f, _ in filas}):
        n_f = sum(1 for f in fomc if f.startswith(anio))
        n_i = sum(1 for f in ipc if f.startswith(anio))
        print(f"    {anio}: {n_f} FOMC, {n_i} IPC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
