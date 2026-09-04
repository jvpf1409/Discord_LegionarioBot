"""Pase y consulta de listas de asistencia en canales de voz."""

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.permisos import ROL_OFICIAL, es_organizador


logger = logging.getLogger(__name__)


def _embed_lista(lista: dict) -> discord.Embed:
    miembros = lista["miembros"]
    lineas = [
        f"{indice}. {miembro['nombre']}"
        for indice, miembro in enumerate(miembros, start=1)
    ]
    embed = discord.Embed(
        title=f"📋 Lista de asistencia #{lista['id']}",
        description="\n".join(lineas) if lineas else "No había personas conectadas.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Canal de voz",
        value=f"<#{lista['canal_voz_id']}> ({lista['canal_voz_nombre']})",
        inline=True,
    )
    embed.add_field(name="Fecha y hora", value=f"<t:{lista['fecha_hora_ts']}:F>", inline=True)
    embed.add_field(name="Total", value=str(len(miembros)), inline=True)
    embed.set_footer(text="Registro guardado en la base de datos")
    return embed


class Asistencia(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="pasar-lista",
        description="Registra y publica quiénes están conectados a un canal de voz",
    )
    @app_commands.describe(canal="Canal de voz del que se tomará la asistencia")
    @app_commands.guild_only()
    @es_organizador()
    async def pasar_lista(
        self, interaction: discord.Interaction, canal: discord.VoiceChannel
    ) -> None:
        await interaction.response.defer()
        miembros = sorted(
            (miembro for miembro in canal.members if not miembro.bot),
            key=lambda miembro: miembro.display_name.casefold(),
        )
        fecha_hora_ts = int(time.time())
        registros = [
            {"user_id": miembro.id, "nombre": miembro.display_name}
            for miembro in miembros
        ]
        lista_id = storage.crear_lista_asistencia(
            guild_id=interaction.guild_id,
            canal_voz_id=canal.id,
            canal_voz_nombre=canal.name,
            canal_publicacion_id=interaction.channel_id,
            creado_por=interaction.user.id,
            fecha_hora_ts=fecha_hora_ts,
            miembros=registros,
        )
        lista = storage.obtener_lista_asistencia(lista_id, interaction.guild_id)
        await interaction.followup.send(embed=_embed_lista(lista))

    @app_commands.command(
        name="consultar-lista",
        description="Consulta una lista guardada o muestra las listas más recientes",
    )
    @app_commands.describe(lista_id="ID de la lista; déjalo vacío para ver las últimas")
    @app_commands.guild_only()
    @es_organizador()
    async def consultar_lista(
        self, interaction: discord.Interaction, lista_id: str | None = None
    ) -> None:
        if lista_id:
            lista = storage.obtener_lista_asistencia(lista_id, interaction.guild_id)
            if lista is None:
                await interaction.response.send_message(
                    "❌ No existe una lista con ese ID en este servidor.", ephemeral=True
                )
                return
            await interaction.response.send_message(embed=_embed_lista(lista), ephemeral=True)
            return

        listas = storage.listar_listas_asistencia(interaction.guild_id, limite=10)
        if not listas:
            await interaction.response.send_message(
                "Todavía no hay listas de asistencia guardadas.", ephemeral=True
            )
            return
        lineas = [
            f"**#{lista['id']}** · <t:{lista['fecha_hora_ts']}:f> · "
            f"{lista['canal_voz_nombre']} · **{len(lista['miembros'])}** personas"
            for lista in listas
        ]
        embed = discord.Embed(
            title="📚 Listas de asistencia recientes",
            description="\n".join(lineas),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Usa /consultar-lista lista_id para ver el detalle")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="update-asist",
        description="Actualiza una lista con quienes están ahora en su canal de voz",
    )
    @app_commands.describe(lista_id="ID de la lista que quieres actualizar")
    @app_commands.guild_only()
    @es_organizador()
    async def actualizar_lista(
        self, interaction: discord.Interaction, lista_id: str
    ) -> None:
        lista = storage.obtener_lista_asistencia(lista_id, interaction.guild_id)
        if lista is None:
            await interaction.response.send_message(
                "❌ No existe una lista con ese ID en este servidor.", ephemeral=True
            )
            return

        canal = interaction.guild.get_channel(lista["canal_voz_id"])
        if not isinstance(canal, discord.VoiceChannel):
            await interaction.response.send_message(
                "❌ El canal de voz original ya no existe o no está disponible.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        miembros = sorted(
            (miembro for miembro in canal.members if not miembro.bot),
            key=lambda miembro: miembro.display_name.casefold(),
        )
        registros = [
            {"user_id": miembro.id, "nombre": miembro.display_name}
            for miembro in miembros
        ]
        lista = storage.actualizar_lista_asistencia(
            lista_id,
            interaction.guild_id,
            miembros=registros,
            fecha_hora_ts=int(time.time()),
            canal_voz_nombre=canal.name,
            canal_publicacion_id=interaction.channel_id,
            actualizado_por=interaction.user.id,
        )
        await interaction.followup.send(embed=_embed_lista(lista))

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingRole):
            aviso = f"🚫 Necesitas el rol **{ROL_OFICIAL}** para usar este comando."
        else:
            original = getattr(error, "original", error)
            logger.exception("Error en un comando de asistencia", exc_info=original)
            aviso = "⚠️ No pude procesar la lista de asistencia. Inténtalo nuevamente."
        if interaction.response.is_done():
            await interaction.followup.send(aviso, ephemeral=True)
        else:
            await interaction.response.send_message(aviso, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Asistencia(bot))
