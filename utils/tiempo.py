"""
Parseo de fecha/hora ingresadas por el usuario (zona horaria del servidor)
a timestamp UTC, para mostrarlas con el formato dinámico <t:...> de Discord.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA_HORARIA = os.getenv("ZONA_HORARIA", "America/Santiago")  # Hora de Chile


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


def fecha_hora_desde_timestamp(timestamp: int) -> tuple[str, str]:
    """Convierte un timestamp a fecha y hora locales en los formatos del bot."""
    try:
        zona = ZoneInfo(ZONA_HORARIA)
    except ZoneInfoNotFoundError:
        zona = ZoneInfo("UTC")

    dt = datetime.fromtimestamp(timestamp, tz=zona)
    return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M")


def dia_semana_hora_desde_timestamp(timestamp: int) -> tuple[int, str]:
    """Devuelve el día semanal (lunes=0) y la hora local de un timestamp."""
    try:
        zona = ZoneInfo(ZONA_HORARIA)
    except ZoneInfoNotFoundError:
        zona = ZoneInfo("UTC")
    dt = datetime.fromtimestamp(timestamp, tz=zona)
    return dt.weekday(), dt.strftime("%H:%M")


def siguiente_ocurrencia_semanal(dia_semana: int, hora: str, desde_ts: int) -> int:
    """Devuelve la siguiente ocurrencia local (lunes=0), incluyendo hoy si aún no pasó."""
    if dia_semana not in range(7):
        raise ValueError("Día de la semana inválido")
    try:
        hora_local = datetime.strptime(hora.strip(), "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Hora inválida") from exc
    try:
        zona = ZoneInfo(ZONA_HORARIA)
    except ZoneInfoNotFoundError:
        zona = ZoneInfo("UTC")
    desde = datetime.fromtimestamp(desde_ts, tz=zona)
    dias = (dia_semana - desde.weekday()) % 7
    candidata = datetime.combine(desde.date() + timedelta(days=dias), hora_local, tzinfo=zona)
    if candidata.timestamp() <= desde_ts:
        candidata += timedelta(days=7)
    return int(candidata.timestamp())
