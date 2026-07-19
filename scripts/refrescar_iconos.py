"""
Utilidad de mantenimiento: borra los application emojis indicados, para que
el bot vuelva a subirlos (con el archivo actual de assets/icons/) la próxima
vez que arranque.

Uso, desde la raíz del proyecto:
    python scripts/refrescar_iconos.py healer
    python scripts/refrescar_iconos.py healer tank
"""

import asyncio
import os
import sys

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


async def main(nombres: list[str]):
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        existentes = {e.name: e for e in await client.fetch_application_emojis()}
        for nombre in nombres:
            emoji = existentes.get(nombre)
            if emoji is None:
                print(f"No había ningún ícono llamado '{nombre}' (nada que borrar).")
                continue
            await emoji.delete()
            print(f"✅ Borrado '{nombre}'. Corre el bot normal para que lo vuelva a subir.")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python scripts/refrescar_iconos.py <nombre1> [nombre2 ...]")
    if not TOKEN:
        raise SystemExit("❌ Falta DISCORD_TOKEN en el archivo .env")
    asyncio.run(main(sys.argv[1:]))
