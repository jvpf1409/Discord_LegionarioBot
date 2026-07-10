"""
Íconos personalizados del bot, como "application emojis" de Discord:
le pertenecen a la aplicación del bot (no a un servidor puntual), así que
funcionan en cualquier servidor donde esté el bot y sobreviven a un cambio
de servidor o de cuenta de administración.

Las imágenes viven en assets/icons/ (parte del repo). Al iniciar el bot,
cargar_iconos() las sube una sola vez —si no existen ya— y deja disponibles
sus códigos <:nombre:id> en ICONOS. Si un ícono no está configurado o falla
la subida, icono() devuelve el emoji unicode de reserva: el bot nunca se
rompe por esto, con o sin íconos personalizados.
"""

import logging
import os

import discord

logger = logging.getLogger(__name__)

ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons")
EXTENSIONES_VALIDAS = (".png", ".jpg", ".jpeg", ".gif")

ICONOS: dict[str, str] = {}


async def cargar_iconos(bot: discord.Client):
    if not os.path.isdir(ICONS_DIR):
        return

    try:
        existentes = {e.name: e for e in await bot.fetch_application_emojis()}
    except discord.HTTPException:
        logger.exception("No se pudieron consultar los application emojis existentes")
        return

    for archivo in os.listdir(ICONS_DIR):
        nombre, ext = os.path.splitext(archivo)
        if ext.lower() not in EXTENSIONES_VALIDAS:
            continue

        emoji = existentes.get(nombre)
        if emoji is None:
            try:
                with open(os.path.join(ICONS_DIR, archivo), "rb") as f:
                    emoji = await bot.create_application_emoji(name=nombre, image=f.read())
            except discord.HTTPException:
                logger.exception(f"No se pudo subir el ícono '{nombre}'")
                continue

        ICONOS[nombre] = str(emoji)

    if ICONOS:
        logger.info(f"Íconos personalizados cargados: {', '.join(ICONOS)}")


def icono(nombre: str, reserva: str) -> str:
    """Ícono personalizado si está cargado; si no, el emoji unicode de reserva."""
    return ICONOS.get(nombre, reserva)
