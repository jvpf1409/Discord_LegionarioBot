"""
Parseo de fecha/hora ingresadas por el usuario (zona horaria del servidor)
a timestamp UTC, para mostrarlas con el formato dinámico <t:...> de Discord.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA_HORARIA = os.getenv("ZONA_HORARIA", "Etc/GMT+5")  # CST fijo (UTC-6), sin horario de verano


def parse_fecha_hora(fecha: str, hora: str) -> int:
    """
    fecha: "DD/MM/AAAA" (ej: 30/06/2026)
    hora: "HH:MM" en formato 24h (ej: 23:00)
    Devuelve el timestamp UTC (segundos) o lanza ValueError si el formato es inválido.
    """
    try:
        zona = ZoneInfo(ZONA_HORARIA)
    except ZoneInfoNotFoundError:
        zona = ZoneInfo("UTC")

    dt_naive = datetime.strptime(f"{fecha.strip()} {hora.strip()}", "%d/%m/%Y %H:%M")
    dt = dt_naive.replace(tzinfo=zona)
    return int(dt.timestamp())
