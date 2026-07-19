"""
Cog con los comandos de administración de raids:
crear, cerrar, cancelar, listar.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.anuncios import anunciar_publicacion
from utils.permisos import ROL_OFICIAL, es_organizador
from utils.tiempo import parse_fecha_hora
from cogs.vistas_raid import RaidView, construir_embed_raid

logger = logging.getLogger(__name__)

class DescripcionRaidModal(discord.ui.Modal, title="Descripción de la raid"):
    """
    La descripción se pide en un modal aparte (campo tipo párrafo) porque los
    parámetros de un slash command no admiten saltos de línea.
    """

    descripcion = discord.ui.TextInput(
        label="Descripción",
        style=discord.TextStyle.paragraph,
        placeholder="Detalles de la raid",
        max_length=1000,
        required=True,
    )

    def __init__(
        self,
        *,
        titulo: str,
        fecha_hora_ts: int,
        canal_publicacion: discord.TextChannel,
        imagen_url: str | None,
        canal_inscripciones_id: int | None,
        guild_id: int,
        creado_por: int,
    ):
        super().__init__()
        self.titulo = titulo
        self.fecha_hora_ts = fecha_hora_ts
        self.canal_publicacion = canal_publicacion
        self.imagen_url = imagen_url
        self.canal_inscripciones_id = canal_inscripciones_id
        self.guild_id = guild_id
        self.creado_por = creado_por

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        raid_id = storage.crear_raid(
            titulo=self.titulo,
            descripcion=self.descripcion.value.strip(),
            guild_id=self.guild_id,
            canal_id=self.canal_publicacion.id,
            fecha_hora_ts=self.fecha_hora_ts,
            creado_por=self.creado_por,
            canal_inscripciones_id=self.canal_inscripciones_id,
            imagen_url=self.imagen_url,
        )
        raid = storage.obtener_raid(raid_id)
        embed = construir_embed_raid(raid)
        view = RaidView(raid_id, abierta=True)

        try:
            mensaje = await self.canal_publicacion.send(embed=embed, view=view)
        except discord.Forbidden:
            storage.actualizar_raid(raid_id, estado="cancelado")
            await interaction.followup.send(
                f"❌ No tengo permiso para publicar en {self.canal_publicacion.mention}.", ephemeral=True
            )
            return

        storage.actualizar_raid(raid_id, mensaje_id=mensaje.id)
        advertencia = await anunciar_publicacion(
            interaction.client, interaction.guild, "Raid", self.titulo, mensaje
        )
        detalle_aviso = f"\n⚠️ {advertencia}" if advertencia else ""
        await interaction.followup.send(
            f"✅ Raid **{self.titulo}** publicada en {self.canal_publicacion.mention} "
            f"(ID: {raid_id}).{detalle_aviso}",
            ephemeral=True,
        )


class Raids(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    raid_group = app_commands.Group(name="raid", description="Gestiona raids de la hermandad")

    # ---------------------- CREAR ----------------------
    @raid_group.command(name="crear", description="Crea una nueva raid con inscripciones abiertas")
    @app_commands.describe(
        titulo="Título de la raid (ej: Onirifalla Heroico)",
        fecha="Fecha de la raid en formato DD/MM/AAAA (ej: 30/06/2026)",
        hora="Hora de la raid en formato 24h HH:MM (ej: 22:00)",
        canal_publicacion="Canal donde se publicará la raid (embed + selects)",
        imagen="Imagen opcional para la raid (banner del jefe, etc.)",
        canal_inscripciones="Canal opcional donde se irá anunciando cada inscripción en vivo",
    )
    @es_organizador()
    async def crear(
        self,
        interaction: discord.Interaction,
        titulo: str,
        fecha: str,
        hora: str,
        canal_publicacion: discord.TextChannel,
        imagen: discord.Attachment = None,
        canal_inscripciones: discord.TextChannel = None,
    ):
        try:
            fecha_hora_ts = parse_fecha_hora(fecha, hora)
        except ValueError:
            await interaction.response.send_message(
                "❌ Fecha u hora inválidas. Usa el formato `DD/MM/AAAA` para la fecha y `HH:MM` (24h) para la hora.",
                ephemeral=True,
            )
            return

        if imagen is not None and not (imagen.content_type or "").startswith("image/"):
            await interaction.response.send_message(
                "❌ El archivo adjunto debe ser una imagen.", ephemeral=True
            )
            return

        modal = DescripcionRaidModal(
            titulo=titulo,
            fecha_hora_ts=fecha_hora_ts,
            canal_publicacion=canal_publicacion,
            imagen_url=imagen.url if imagen else None,
            canal_inscripciones_id=canal_inscripciones.id if canal_inscripciones else None,
            guild_id=interaction.guild_id,
            creado_por=interaction.user.id,
        )
        await interaction.response.send_modal(modal)

    # ---------------------- CERRAR ----------------------
    @raid_group.command(name="cerrar", description="Cierra las inscripciones de una raid")
    @app_commands.describe(raid_id="ID de la raid a cerrar")
    @es_organizador()
    async def cerrar(self, interaction: discord.Interaction, raid_id: str):
        raid = storage.obtener_raid(raid_id)
        if raid is None:
            await interaction.response.send_message("❌ No existe esa raid.", ephemeral=True)
            return
        if raid["estado"] != "abierto":
            await interaction.response.send_message("⚠️ Esta raid ya no está abierta.", ephemeral=True)
            return

        storage.actualizar_raid(raid_id, estado="cerrado")
        raid = storage.obtener_raid(raid_id)

        embed = construir_embed_raid(raid)
        view = RaidView(raid_id, abierta=False)
        try:
            canal = self.bot.get_channel(raid["canal_id"])
            mensaje = await canal.fetch_message(raid["mensaje_id"])
            await mensaje.edit(embed=embed, view=view)
        except Exception:
            pass

        await interaction.response.send_message(
            f"🔒 Inscripciones cerradas para **{raid['titulo']}** ({len(raid['inscritos'])} inscritos)."
        )

    # ---------------------- CANCELAR ----------------------
    @raid_group.command(name="cancelar", description="Cancela una raid por completo")
    @app_commands.describe(raid_id="ID de la raid a cancelar")
    @es_organizador()
    async def cancelar(self, interaction: discord.Interaction, raid_id: str):
        raid = storage.obtener_raid(raid_id)
        if raid is None:
            await interaction.response.send_message("❌ No existe esa raid.", ephemeral=True)
            return
        storage.actualizar_raid(raid_id, estado="cancelado")
        try:
            canal = self.bot.get_channel(raid["canal_id"])
            mensaje = await canal.fetch_message(raid["mensaje_id"])
            await mensaje.edit(embed=construir_embed_raid(storage.obtener_raid(raid_id)), view=None)
        except Exception:
            pass
        await interaction.response.send_message(f"🗑️ Raid **{raid['titulo']}** cancelada.")

    # ---------------------- LISTAR ----------------------
    @raid_group.command(name="listar", description="Lista las raids del servidor")
    @app_commands.describe(estado="Filtra por estado (opcional)")
    @app_commands.choices(estado=[
        app_commands.Choice(name="Abiertas", value="abierto"),
        app_commands.Choice(name="Cerradas", value="cerrado"),
        app_commands.Choice(name="Canceladas", value="cancelado"),
    ])
    async def listar(self, interaction: discord.Interaction, estado: app_commands.Choice[str] = None):
        raids = storage.listar_raids(interaction.guild_id, estado.value if estado else None)
        if not raids:
            await interaction.response.send_message("No hay raids que coincidan.", ephemeral=True)
            return

        embed = discord.Embed(title="🐉 Raids de la hermandad", color=discord.Color.blurple())
        for r in raids:
            resumen = f"Inscritos: {len(r['inscritos'])}"
            if r.get("fecha_hora_ts"):
                resumen += f"\n📅 <t:{r['fecha_hora_ts']}:f>"
            embed.add_field(name=f"#{r['id']} — {r['titulo']} ({r['estado']})", value=resumen, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Manejo de errores de permisos para todo el grupo
    @crear.error
    @cerrar.error
    @cancelar.error
    async def on_permission_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            mensaje = f"🚫 Necesitas el rol **{ROL_OFICIAL}** para usar este comando."
        else:
            original = getattr(error, "original", error)
            logger.exception("Error inesperado en un comando de /raid", exc_info=original)
            mensaje = f"⚠️ Ocurrió un error: {original}"

        try:
            if interaction.response.is_done():
                await interaction.followup.send(mensaje, ephemeral=True)
            else:
                await interaction.response.send_message(mensaje, ephemeral=True)
        except discord.HTTPException:
            logger.warning("No se pudo notificar el error al usuario (interacción ya cerrada).")


async def setup(bot: commands.Bot):
    await bot.add_cog(Raids(bot))
