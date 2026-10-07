"""Tarea periódica para avisar antes de eventos y raids: 30 minutos antes y,
si se configuró, un recordatorio extra con la anticipación elegida."""

import logging
import time

from discord.ext import commands, tasks

from utils import storage
from utils.anuncios import avisos_configurados, enviar_recordatorio
from utils.recordatorios import VENTANA_RECORDATORIO, accion_recordatorio_extra


logger = logging.getLogger(__name__)


def debe_recordar(item: dict, ahora: int) -> bool:
    inicio = item.get("fecha_hora_ts")
    return bool(
        inicio
        and item.get("mensaje_id")
        and not item.get("recordatorio_enviado", False)
        and 0 < inicio - ahora <= VENTANA_RECORDATORIO
    )


class Recordatorios(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.revisar.start()

    def cog_unload(self):
        self.revisar.cancel()

    @tasks.loop(seconds=30)
    async def revisar(self):
        if not avisos_configurados():
            return
        ahora = int(time.time())
        grupos = (
            ("Evento", storage.listar_todos_los_eventos(), {"abierto", "cerrado"}, storage.actualizar_evento),
            ("Raid", storage.listar_todas_las_raids(), {"abierto", "cerrado"}, storage.actualizar_raid),
        )
        for tipo, items, estados, actualizar in grupos:
            for item in items:
                if item.get("estado") not in estados:
                    continue
                guild = self.bot.get_guild(item["guild_id"])
                if guild is None:
                    continue

                extra = accion_recordatorio_extra(item, ahora)
                if extra == "descartar":
                    actualizar(item["id"], recordatorio_extra_enviado=True)
                elif extra == "enviar":
                    error = await enviar_recordatorio(self.bot, guild, tipo, item)
                    if error is None:
                        actualizar(item["id"], recordatorio_extra_enviado=True)
                    else:
                        logger.warning("Recordatorio extra no enviado para %s %s: %s", tipo, item["id"], error)

                if debe_recordar(item, ahora):
                    error = await enviar_recordatorio(self.bot, guild, tipo, item)
                    if error is None:
                        actualizar(item["id"], recordatorio_enviado=True)
                    else:
                        logger.warning("Recordatorio no enviado para %s %s: %s", tipo, item["id"], error)

    @revisar.before_loop
    async def antes_de_revisar(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Recordatorios(bot))
