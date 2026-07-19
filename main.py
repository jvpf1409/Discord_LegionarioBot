"""
Punto de entrada del bot.
Carga variables de entorno, registra vistas persistentes de eventos abiertos/cerrados
y sincroniza los comandos slash.
"""

import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils import storage
from utils.iconos import cargar_iconos
from cogs.vistas import EventoView
from cogs.vistas_raid import RaidView

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # opcional: sincroniza más rápido solo en un servidor de pruebas

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
# No se necesita message_content porque todo funciona con comandos slash y componentes.

bot = commands.Bot(command_prefix="!wow ", intents=intents)


@bot.event
async def on_ready():
    # Sube (una sola vez) los íconos personalizados de assets/icons/ como
    # application emojis, y deja el resto del bot listo para usarlos.
    await cargar_iconos(bot)

    # Volver a registrar las vistas de todos los eventos no finalizados,
    # para que los botones sigan funcionando tras reiniciar el bot.
    for evento in storage.listar_todos_los_eventos():
        if evento["estado"] in ("abierto", "cerrado") and evento.get("mensaje_id"):
            abierto = evento["estado"] == "abierto"
            bot.add_view(EventoView(evento["id"], abierto=abierto), message_id=evento["mensaje_id"])

    for raid in storage.listar_todas_las_raids():
        if raid["estado"] in ("abierto", "cerrado") and raid.get("mensaje_id"):
            abierta = raid["estado"] == "abierto"
            bot.add_view(RaidView(raid["id"], abierta=abierta), message_id=raid["mensaje_id"])

    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
    else:
        synced = await bot.tree.sync()

    print(f"✅ Conectado como {bot.user} — {len(synced)} comandos sincronizados.")


async def main():
    async with bot:
        await bot.load_extension("cogs.eventos")
        await bot.load_extension("cogs.raids")
        await bot.load_extension("cogs.recordatorios")
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Falta DISCORD_TOKEN en el archivo .env")
    asyncio.run(main())
