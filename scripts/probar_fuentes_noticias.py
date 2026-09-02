#!/usr/bin/env python3
"""Sondea que fuentes de noticias/calendario son alcanzables desde un runner real.

Un filtro de eventos solo sirve si el dato se puede refrescar donde el bot
opera de verdad: el runner de GitHub Actions, no la sesion de desarrollo (que
tiene su propia politica de red, mas restrictiva -desde ella ni example.com
responde). Con el funding de Binance ya se pago el precio de no comprobarlo
antes: el mecanismo se calibro entero y luego resulto inoperable en vivo
(docs/07, seccion 4.1). Esta vez la comprobacion va primero.

La distincion que importa no es "funciona / no funciona", sino:

  ALCANZABLE    el servidor responde HTTP -incluido 401/403 pidiendo clave.
                Hay ruta de red; lo demas es cuestion de credenciales.
  GEOBLOQUEADO  responde, pero rechaza la IP del runner (451 y equivalentes).
                Es el caso de la API en vivo de Binance: hay ruta, no hay
                permiso. Una clave no lo arregla.
  BLOQUEADO     no hay respuesta HTTP (DNS, timeout, conexion rechazada).
                No hay ruta: ninguna clave ni plan de pago lo arregla.

Solo las ALCANZABLE son candidatas reales para el filtro de eventos.

    python scripts/probar_fuentes_noticias.py
"""

from __future__ import annotations

import json
import socket
import ssl
import sys
import urllib.error
import urllib.request

TIMEOUT = 15

# Cabecera de navegador: varios medios devuelven 403 al User-Agent por defecto
# de urllib, lo que se confundiria con un bloqueo de red.
CABECERAS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "*/*",
}

# (categoria, nombre, url, para que serviria)
FUENTES = [
    # --- Controles: sin estos no se puede interpretar el resto -------------
    ("control", "GitHub API", "https://api.github.com",
     "Debe responder: el runner habla con GitHub por definicion"),
    ("control", "example.com", "https://example.com",
     "Dominio neutro: mide si hay salida general a internet"),
    ("control", "Binance archivo estatico", "https://data.binance.vision/",
     "La fuente de precios que YA usamos: debe responder"),
    ("control", "Binance API en vivo", "https://fapi.binance.com/fapi/v1/time",
     "Bloqueada en docs/07: sirve para comparar contra ese caso conocido"),

    # --- Calendario macro: la via recomendada (fechas, no texto) ----------
    ("macro", "Reserva Federal (FOMC)",
     "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
     "Fechas FOMC historicas y futuras, publicas, sin clave"),
    ("macro", "FRED (St. Louis Fed)",
     "https://api.stlouisfed.org/fred/releases?file_type=json",
     "Calendario de publicaciones macro; 400/403 sin clave = alcanzable"),
    ("macro", "BLS (IPC de EEUU)",
     "https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0",
     "Serie del IPC con fechas de publicacion, sin clave en v2 limitado"),
    ("macro", "ForexFactory (espejo JSON)",
     "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
     "Calendario economico semanal en JSON, gratuito"),

    # --- Noticias cripto: texto libre, peor candidato para backtest -------
    ("noticias", "CryptoPanic",
     "https://cryptopanic.com/api/v1/posts/",
     "Agregador cripto con API; historico limitado en plan gratuito"),
    ("noticias", "CoinDesk RSS",
     "https://www.coindesk.com/arc/outboundfeeds/rss/",
     "Titulares en vivo; sin historico profundo"),
    ("noticias", "Cointelegraph RSS", "https://cointelegraph.com/rss",
     "Idem: titulares en vivo, sin historico"),
    ("noticias", "NewsAPI", "https://newsapi.org/v2/top-headlines?country=us",
     "Agregador generalista; historico solo en plan de pago"),

    # --- Eventos estructurados cripto -------------------------------------
    ("eventos", "DefiLlama", "https://api.llama.fi/protocols",
     "Sin clave; publica desbloqueos de tokens (emissions)"),
    ("eventos", "Deribit", "https://www.deribit.com/api/v2/public/get_time",
     "Vencimientos de opciones: fechas fijas, historico reconstruible"),
    ("eventos", "CoinGecko", "https://api.coingecko.com/api/v3/ping",
     "Metadatos de mercado y eventos; bloqueado en esta sesion"),
]


def sondear(url: str) -> tuple[str, str]:
    """Devuelve (veredicto, detalle) para una URL."""
    peticion = urllib.request.Request(url, headers=CABECERAS, method="GET")
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
            return "ALCANZABLE", f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # Hubo respuesta del servidor: la ruta de red existe. Lo unico que
        # invalida la fuente aqui es el rechazo por region (451 / 403 de
        # Binance), no un 401 que solo pide credenciales.
        if e.code in (451, 429):
            etiqueta = "GEOBLOQUEADO" if e.code == 451 else "ALCANZABLE"
            return etiqueta, f"HTTP {e.code}"
        if e.code in (401, 403):
            return "ALCANZABLE", f"HTTP {e.code} (pide clave o rechaza UA)"
        return "ALCANZABLE", f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return "BLOQUEADO", f"{type(e.reason).__name__}: {e.reason}"
    except (socket.timeout, TimeoutError):
        return "BLOQUEADO", f"timeout tras {TIMEOUT}s"
    except ssl.SSLError as e:
        return "BLOQUEADO", f"SSL: {e}"
    except Exception as e:  # noqa: BLE001 - el sondeo nunca debe tumbar el job
        return "BLOQUEADO", f"{type(e).__name__}: {e}"


def main() -> int:
    print(f"Sondeo de fuentes (timeout {TIMEOUT}s por fuente)\n")
    filas = []
    for categoria, nombre, url, nota in FUENTES:
        veredicto, detalle = sondear(url)
        filas.append({"categoria": categoria, "nombre": nombre, "url": url,
                      "veredicto": veredicto, "detalle": detalle, "nota": nota})
        marca = {"ALCANZABLE": "OK ", "GEOBLOQUEADO": "GEO", "BLOQUEADO": "-- "}[veredicto]
        print(f"  [{marca}] {categoria:9s} {nombre:26s} {veredicto:13s} {detalle}")

    print("\nResumen por categoria (solo ALCANZABLE cuenta como candidata):")
    for categoria in ("control", "macro", "noticias", "eventos"):
        grupo = [f for f in filas if f["categoria"] == categoria]
        ok = [f["nombre"] for f in grupo if f["veredicto"] == "ALCANZABLE"]
        print(f"  {categoria:9s} {len(ok)}/{len(grupo)} alcanzables"
              f"{': ' + ', '.join(ok) if ok else ''}")

    # JSON al final para poder pegarlo en el pre-registro sin transcribir a mano.
    print("\n--- JSON ---")
    print(json.dumps(filas, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
