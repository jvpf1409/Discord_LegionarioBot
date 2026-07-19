"""Avisos automáticos y recordatorios en un canal configurado."""

import logging
import os

import discord


logger = logging.getLogger(__name__)


def avisos_configurados() -> bool:
    return bool(os.getenv("CANAL_AVISOS_ID", "").strip())


async def _resolver_destino(client: discord.Client, guild: discord.Guild):
    canal_id = os.getenv("CANAL_AVISOS_ID", "").strip()
    rol_id = os.getenv("ROL_AVISOS_ID", "").strip()
    if not canal_id:
        return None, None, None
    try:
        canal = client.get_channel(int(canal_id)) or await client.fetch_channel(int(canal_id))
    except (ValueError, discord.HTTPException):
        logger.exception("No se pudo encontrar CANAL_AVISOS_ID=%s", canal_id)
        return None, None, "Revisa `CANAL_AVISOS_ID`."
    if not isinstance(canal, discord.abc.Messageable):
        return None, None, "`CANAL_AVISOS_ID` no es un canal de mensajes."

    rol = None
    if rol_id:
        try:
            rol = guild.get_role(int(rol_id))
        except ValueError:
            rol = None
        if rol is None:
            return None, None, "Revisa `ROL_AVISOS_ID`."
    return canal, rol, None


async def _enviar(client: discord.Client, guild: discord.Guild, contenido: str) -> str | None:
    canal, rol, error = await _resolver_destino(client, guild)
    if error or canal is None:
        return error
    mencion = f"{rol.mention}, " if rol else ""
    try:
        await canal.send(
            mencion + contenido,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=False, roles=[rol] if rol else False
            ),
        )
    except (discord.Forbidden, discord.HTTPException):
        logger.exception("No se pudo enviar un aviso automático")
        return "No pude enviar el aviso automático."
    return None


async def anunciar_publicacion(
    client: discord.Client,
    guild: discord.Guild,
    tipo: str,
    titulo: str,
    mensaje: discord.Message,
) -> str | None:
    contenido = (
        f"tenemos **{tipo}**: **{titulo}**. "
        f"¡Recuerden inscribirse!\n{mensaje.jump_url}"
    )
    return await _enviar(client, guild, contenido)


async def enviar_recordatorio(
    client: discord.Client, guild: discord.Guild, tipo: str, item: dict
) -> str | None:
    enlace = (
        f"https://discord.com/channels/{item['guild_id']}/"
        f"{item['canal_id']}/{item['mensaje_id']}"
    )
    contenido = (
        f"recordatorio: **{tipo} {item['titulo']}** comienza "
        f"<t:{item['fecha_hora_ts']}:R>. ¡No olviden prepararse!\n{enlace}"
    )
    return await _enviar(client, guild, contenido)
