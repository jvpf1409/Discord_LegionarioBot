"""Publicación de raids semanales y cierre automático de inscripciones."""

import logging
import time

import discord
from discord.ext import commands, tasks

from cogs.vistas import EventoView, construir_embed_evento
from cogs.vistas_raid import RaidView, construir_embed_raid
from utils import storage
from utils.anuncios import anunciar_publicacion
from utils.recordatorios import campos_recordatorio_extra
from utils.tiempo import siguiente_ocurrencia_semanal

logger = logging.getLogger(__name__)
UN_DIA = 3 * 60 * 60  # 3 horas en segundos


def vencido(item: dict, ahora: int) -> bool:
    """Las inscripciones se cierran 3 horas después del inicio indicado."""
    inicio = item.get("fecha_hora_ts")
    return bool(inicio and item.get("estado") == "abierto" and ahora >= inicio + UN_DIA)


def toca_publicar(programacion: dict, ahora: int) -> bool:
    publicacion = programacion.get("siguiente_publicacion_ts")
    return bool(programacion.get("activa", True) and publicacion and ahora >= publicacion)


class Automatizacion(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.revisar.start()

    def cog_unload(self):
        self.revisar.cancel()

    async def _editar_mensaje(self, item: dict, *, es_raid: bool):
        if not item.get("mensaje_id"):
            return
        try:
            canal = self.bot.get_channel(item["canal_id"]) or await self.bot.fetch_channel(item["canal_id"])
            mensaje = await canal.fetch_message(item["mensaje_id"])
            if es_raid:
                await mensaje.edit(embed=construir_embed_raid(item), view=RaidView(item["id"], abierta=False))
            else:
                await mensaje.edit(embed=construir_embed_evento(item), view=EventoView(item["id"], abierto=False))
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, AttributeError) as exc:
            logger.warning("No se pudo actualizar el cierre automático de %s: %s", item["id"], exc)

    async def _cerrar_vencidos(self, ahora: int):
        for evento in storage.listar_todos_los_eventos():
            try:
                if vencido(evento, ahora):
                    evento = storage.actualizar_evento(evento["id"], estado="cerrado")
                    await self._editar_mensaje(evento, es_raid=False)
                    logger.info("Evento %s cerrado automáticamente", evento["id"])
            except Exception:
                logger.exception("Error al procesar el cierre del evento %s", evento.get("id"))
        for raid in storage.listar_todas_las_raids():
            try:
                if vencido(raid, ahora):
                    raid = storage.actualizar_raid(raid["id"], estado="cerrado")
                    await self._editar_mensaje(raid, es_raid=True)
                    logger.info("Raid %s cerrada automáticamente", raid["id"])
            except Exception:
                logger.exception("Error al procesar el cierre de la raid %s", raid.get("id"))

    async def _publicar_programada(self, programacion: dict, ahora: int):
        publicacion = programacion["siguiente_publicacion_ts"]
        inicio = programacion.get("siguiente_raid_ts")
        if not inicio:
            plantilla_anterior = storage.obtener_raid(programacion["raid_plantilla_id"])
            if plantilla_anterior is None:
                storage.actualizar_raid_programada(programacion["id"], activa=False)
                return
            inicio = siguiente_ocurrencia_semanal(
                programacion["dia_raid"],
                programacion["hora_raid"],
                plantilla_anterior["fecha_hora_ts"] + 60,
            )
            storage.actualizar_raid_programada(
                programacion["id"], siguiente_raid_ts=inicio
            )
        # Si el bot estuvo apagado hasta después del cierre de esa raid, salta la semana.
        if ahora >= inicio + UN_DIA:
            siguiente = siguiente_ocurrencia_semanal(
                programacion["dia_publicacion"], programacion["hora_publicacion"], ahora
            )
            siguiente_raid = inicio
            while ahora >= siguiente_raid + UN_DIA:
                siguiente_raid = siguiente_ocurrencia_semanal(
                    programacion["dia_raid"],
                    programacion["hora_raid"],
                    siguiente_raid + 60,
                )
            storage.actualizar_raid_programada(
                programacion["id"],
                siguiente_publicacion_ts=siguiente,
                siguiente_raid_ts=siguiente_raid,
            )
            return

        existente = next(
            (
                raid for raid in storage.listar_todas_las_raids()
                if raid.get("programacion_id") == programacion["id"]
                and raid.get("publicacion_programada_ts") == publicacion
            ),
            None,
        )
        if existente and existente.get("mensaje_id"):
            siguiente_raid = siguiente_ocurrencia_semanal(
                programacion["dia_raid"], programacion["hora_raid"], inicio + 60
            )
            storage.actualizar_raid_programada(
                programacion["id"],
                siguiente_publicacion_ts=siguiente_ocurrencia_semanal(
                    programacion["dia_publicacion"],
                    programacion["hora_publicacion"],
                    publicacion + 60,
                ),
                siguiente_raid_ts=siguiente_raid,
            )
            return

        plantilla = storage.obtener_raid(programacion["raid_plantilla_id"])
        if plantilla is None:
            storage.actualizar_raid_programada(programacion["id"], activa=False)
            logger.error(
                "Programación %s pausada porque la raid plantilla %s fue eliminada",
                programacion["id"], programacion["raid_plantilla_id"],
            )
            return

        canal = self.bot.get_channel(plantilla["canal_id"])
        if canal is None:
            try:
                canal = await self.bot.fetch_channel(plantilla["canal_id"])
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                canal = None
        if not isinstance(canal, discord.abc.Messageable):
            logger.warning("Canal no disponible para programación %s", programacion["id"])
            return

        if existente:
            raid_id = existente["id"]
            raid = storage.actualizar_raid(raid_id, estado="abierto")
        else:
            raid_id = storage.crear_raid(
                titulo=plantilla["titulo"], descripcion=plantilla["descripcion"],
                guild_id=programacion["guild_id"], canal_id=plantilla["canal_id"],
                fecha_hora_ts=inicio, creado_por=programacion["creado_por"],
                canal_inscripciones_id=plantilla.get("canal_inscripciones_id"),
                imagen_url=plantilla.get("imagen_url"),
            )
            raid = storage.actualizar_raid(
                raid_id,
                programacion_id=programacion["id"],
                publicacion_programada_ts=publicacion,
            )
        try:
            mensaje = await canal.send(
                embed=construir_embed_raid(raid), view=RaidView(raid_id, abierta=True)
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            storage.actualizar_raid(raid_id, estado="cancelado")
            logger.warning("No se pudo publicar programación %s: %s", programacion["id"], exc)
            return

        storage.actualizar_raid(
            raid_id,
            mensaje_id=mensaje.id,
            # Cada copia semanal hereda la anticipación del recordatorio extra de la plantilla.
            **campos_recordatorio_extra(plantilla.get("recordatorio_extra_min"), inicio, ahora),
        )
        guild = self.bot.get_guild(programacion["guild_id"])
        if guild:
            await anunciar_publicacion(self.bot, guild, "Raid", plantilla["titulo"], mensaje)
        siguiente = siguiente_ocurrencia_semanal(
            programacion["dia_publicacion"],
            programacion["hora_publicacion"],
            publicacion + 60,
        )
        siguiente_raid = siguiente_ocurrencia_semanal(
            programacion["dia_raid"], programacion["hora_raid"], inicio + 60
        )
        storage.actualizar_raid_programada(
            programacion["id"],
            siguiente_publicacion_ts=siguiente,
            siguiente_raid_ts=siguiente_raid,
        )
        logger.info("Raid %s publicada desde programación %s", raid_id, programacion["id"])

    @tasks.loop(minutes=1)
    async def revisar(self):
        ahora = int(time.time())
        try:
            await self._cerrar_vencidos(ahora)
        except Exception:
            logger.exception("Error general al revisar cierres automáticos")
        for programacion in storage.listar_raids_programadas():
            try:
                if toca_publicar(programacion, ahora):
                    await self._publicar_programada(programacion, ahora)
            except Exception:
                logger.exception(
                    "Error al procesar la programación de raid %s", programacion.get("id")
                )

    @revisar.before_loop
    async def antes_de_revisar(self):
        await self.bot.wait_until_ready()
        logger.info("Automatización de eventos y raids iniciada; revisión cada minuto")

    @revisar.error
    async def error_revisar(self, error: Exception):
        logger.exception("La revisión automática encontró un error inesperado", exc_info=error)


async def setup(bot: commands.Bot):
    await bot.add_cog(Automatizacion(bot))
