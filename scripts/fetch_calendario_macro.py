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

Las dos fuentes anteriores solo miran hacia ATRAS -las actas y las notas
publicadas-, y un filtro que veta la vispera de un evento necesita saber
cuando es el PROXIMO. Por eso se leen ademas las reuniones ya convocadas del
panel del año y el calendario mensual de publicaciones del BLS. Sin esa parte
el filtro no vetaria nunca nada en vivo, fallando en silencio.

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

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SALIDA = os.path.join(RAIZ, "data", "eventos", "calendario_macro.csv")

FOMC_CALENDARIO = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FOMC_HISTORICO = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{anio}.htm"
BLS_ARCHIVO = "https://www.bls.gov/bls/news-release/cpi.htm"

# El BLS rechaza con 403 los agentes de herramienta conocidos (curl, urllib)
# y tambien las cadenas que contienen una URL. Un nombre simple pasa.
AGENTE = "ShortTradingBot"

MESES = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


def descargar(url: str) -> str:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fomc_futuras(html: str) -> set[str]:
    """Reuniones YA CONVOCADAS pero aun sin celebrar.

    Sin esto el calendario solo miraria hacia atras, y un filtro que veta la
    vispera de un evento no vetaria nunca nada en vivo: fallaria en silencio
    pareciendo que funciona. Las actas solo existen para reuniones pasadas,
    asi que las futuras hay que leerlas del panel del año, donde figuran como
    mes + rango de dias ("March 17-18"). La decision se toma el ULTIMO dia del
    rango.
    """
    fechas = set()
    for anio in re.findall(r"(20\d\d) FOMC Meetings", html):
        i = html.find(f"{anio} FOMC Meetings")
        j = html.find("FOMC Meetings", i + 20)
        trozo = re.sub(r"<[^>]+>", "|", html[i:j if j > 0 else len(html)])
        trozo = re.sub(r"\|+", "|", trozo)
        for mes, dias in re.findall(
                r"\|(" + "|".join(MESES) + r")\|[\s|]*(\d{1,2}(?:-\d{1,2})?)\*?\|", trozo):
            fechas.add(f"{anio}-{MESES[mes]:02d}-{int(dias.split('-')[-1]):02d}")
    return fechas


def ipc_futuras(desde_anio: int) -> set[str]:
    """Publicaciones del IPC ya programadas, del calendario mensual del BLS.

    El indice de notas archivadas solo tiene las ya publicadas. Los meses que
    aun no han llegado se leen de /schedule/<anio>/<mes>_sched.htm, donde el
    IPC aparece en la rejilla precedido por su dia.
    """
    hoy = pd.Timestamp.utcnow().tz_localize(None)
    fechas = set()
    for delta in range(0, 15):          # ~15 meses hacia delante
        f = (hoy + pd.DateOffset(months=delta))
        try:
            h = descargar(f"https://www.bls.gov/schedule/{f.year}/{f.month:02d}_sched.htm")
        except Exception:  # noqa: BLE001 - un mes sin publicar aun no es un error
            continue
        h = re.sub(r"<(script|style).*?</\1>", "", h, flags=re.S | re.I)
        t = re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", h))
        m = re.search(r"\|(\d{1,2})\|Consumer Price Index\|", t)
        if m:
            fechas.add(f"{f.year}-{f.month:02d}-{int(m.group(1)):02d}")
    return fechas


def fechas_fomc(desde: int) -> tuple[set[str], list[str]]:
    """Fechas de decision del FOMC, pasadas y ya convocadas."""
    avisos: list[str] = []
    html = descargar(FOMC_CALENDARIO)
    actas = {_iso(d) for d in re.findall(r"fomcminutes(\d{8})", html)}
    actas |= fomc_futuras(html)

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
    fechas |= ipc_futuras(desde)
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
