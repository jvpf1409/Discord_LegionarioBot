"""
Reglas de los recordatorios: el fijo de 30 minutos antes y un recordatorio
extra opcional por evento/raid, configurable con textos como "2h" o "1d12h".
"""

from __future__ import annotations

import re

VENTANA_RECORDATORIO = 30 * 60
EXTRA_MINIMO_MIN = 5
EXTRA_MAXIMO_MIN = 30 * 24 * 60

_DURACION = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?$")

AYUDA_DURACION = (
    "Usa por ejemplo `2h`, `90m`, `1d` o `1d12h` (entre 5 minutos y 30 días), "
    "o `0` para no tener recordatorio extra."
)


def parsear_duracion(texto: str) -> int | None:
    """
    Convierte '2h', '90m', '1d', '1d12h' o '1h 30m' a minutos. '0' devuelve 0
    (sin recordatorio extra). Lanza ValueError si el formato o el rango no son válidos.
    """
    limpio = texto.strip().lower().replace(" ", "")
    if limpio in ("0", "no", "ninguno"):
        return 0
    coincidencia = _DURACION.match(limpio)
    if not limpio or coincidencia is None:
        raise ValueError(texto)
    dias, horas, minutos = (int(g or 0) for g in coincidencia.groups())
    total = dias * 24 * 60 + horas * 60 + minutos
    if not EXTRA_MINIMO_MIN <= total <= EXTRA_MAXIMO_MIN:
        raise ValueError(texto)
    if total * 60 == VENTANA_RECORDATORIO:
        raise ValueError("El recordatorio de 30 minutos ya existe siempre.")
    return total


def formatear_duracion(minutos: int) -> str:
    dias, resto = divmod(minutos, 24 * 60)
    horas, mins = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias} día" if dias == 1 else f"{dias} días")
    if horas:
        partes.append(f"{horas} h")
    if mins:
        partes.append(f"{mins} min")
    return " ".join(partes)


def campos_recordatorio_extra(minutos: int | None, inicio: int | None, ahora: int) -> dict:
    """
    Campos a guardar al configurar el recordatorio extra o cambiar la fecha.
    Si su momento ya pasó, se marca como enviado para no mandarlo de golpe.
    """
    if not minutos:
        return {"recordatorio_extra_min": None, "recordatorio_extra_enviado": False}
    ya_paso = bool(inicio) and inicio - ahora <= minutos * 60
    return {"recordatorio_extra_min": minutos, "recordatorio_extra_enviado": ya_paso}


def texto_recordatorio_extra(minutos: int | None, campos: dict) -> str:
    """Línea para las confirmaciones de crear/editar ('' si no hay recordatorio extra)."""
    if not minutos:
        return ""
    texto = f"\n🔔 Recordatorio extra: {formatear_duracion(minutos)} antes"
    if campos.get("recordatorio_extra_enviado"):
        texto += " — ⚠️ ese momento ya pasó, así que no se enviará (solo el de 30 minutos)"
    return texto + "."


def accion_recordatorio_extra(item: dict, ahora: int) -> str | None:
    """
    'enviar' si toca mandar el recordatorio extra, 'descartar' si quedó
    atrasado (el bot estuvo apagado y ya corresponde el de 30 minutos),
    o None si no hay nada que hacer.
    """
    minutos = item.get("recordatorio_extra_min")
    inicio = item.get("fecha_hora_ts")
    if not minutos or not inicio or not item.get("mensaje_id"):
        return None
    if item.get("recordatorio_extra_enviado", False):
        return None
    restante = inicio - ahora
    if not 0 < restante <= minutos * 60:
        return None
    if minutos * 60 > VENTANA_RECORDATORIO and restante <= VENTANA_RECORDATORIO:
        return "descartar"
    return "enviar"
