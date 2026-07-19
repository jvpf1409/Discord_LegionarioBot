"""
Cog con los comandos de administración de raids:
crear, cerrar, cancelar, listar.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.permisos import es_organizador
from utils.tiempo import parse_fecha_hora, ZONA_HORARIA
from utils.wow_data import rol_de
from cogs.vistas_raid import RaidView, construir_embed_raid

logger = logging.getLogger(__name__)

# Inscritos de ejemplo para /raid test: 2 tank, 2 healer, 3 melee, 3 ranged.
INSCRITOS_DE_PRUEBA = [
    ("Jugador 1", "Guerrero", "Protección"),
    ("Jugador 2", "Monje", "Maestro Cervecero"),
    ("Jugador 3", "Paladín", "Sagrado"),
    ("Jugador 4", "Chamán", "Restauración"),
    ("Jugador 5", "Pícaro", "Asesinato"),
    ("Jugador 6", "Cazador de Demonios", "Asolamiento"),
    ("Jugador 7", "Druida", "Feral"),
    ("Jugador 8", "Mago", "Fuego"),
    ("Jugador 9", "Cazador", "Puntería"),
    ("Jugador 10", "Brujo", "Destrucción"),
]


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
            await interaction.response.send_message(
                f"❌ No tengo permiso para publicar en {self.canal_publicacion.mention}.", ephemeral=True
            )
            return

        storage.actualizar_raid(raid_id, mensaje_id=mensaje.id)
        await interaction.response.send_message(
            f"✅ Raid **{self.titulo}** publicada en {self.canal_publicacion.mention} (ID: {raid_id}).",
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

    # ---------------------- TEST ----------------------
    @raid_group.command(name="test", description="Publica una raid de prueba al instante, para revisar el formato")
    @app_commands.describe(
        titulo="Título de la raid de prueba (opcional)",
        imagen="Imagen opcional para probar cómo se ve",
    )
    @es_organizador()
    async def test(
        self,
        interaction: discord.Interaction,
        titulo: str = "Raid de prueba",
        imagen: discord.Attachment = None,
    ):
        if imagen is not None and not (imagen.content_type or "").startswith("image/"):
            await interaction.response.send_message(
                "❌ El archivo adjunto debe ser una imagen.", ephemeral=True
            )
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Usa este comando en un canal de texto normal del servidor.", ephemeral=True
            )
            return

        fecha_hora_ts = int((datetime.now(ZoneInfo(ZONA_HORARIA)) + timedelta(days=3)).timestamp())

        raid_id = storage.crear_raid(
            titulo=titulo,
            descripcion=(
                "Esto es una publicación de **prueba** para revisar el formato. "
                "Bórrala cuando termines con `/raid cancelar`."
            ),
            guild_id=interaction.guild_id,
            canal_id=interaction.channel.id,
            fecha_hora_ts=fecha_hora_ts,
            creado_por=interaction.user.id,
            imagen_url=imagen.url if imagen else None,
        )

        for i, (nombre, clase, especializacion) in enumerate(INSCRITOS_DE_PRUEBA, start=1):
            storage.inscribir_en_raid(raid_id, {
                "user_id": -i,
                "nombre_discord": nombre,
                "clase": clase,
                "especializacion": especializacion,
                "rol": rol_de(clase, especializacion),
            })

        raid = storage.obtener_raid(raid_id)
        embed = construir_embed_raid(raid)
        view = RaidView(raid_id, abierta=True)

        mensaje = await interaction.channel.send(embed=embed, view=view)
        storage.actualizar_raid(raid_id, mensaje_id=mensaje.id)

        await interaction.response.send_message(
            f"✅ Raid de prueba publicada aquí mismo (ID: {raid_id}). "
            f"Bórrala con `/raid cancelar raid_id:{raid_id}` cuando termines.",
            ephemeral=True,
        )

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
    @test.error
    @cerrar.error
    @cancelar.error
    async def on_permission_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            mensaje = "🚫 Necesitas permiso de **Gestionar servidor** (o el rol de oficial configurado) para usar este comando."
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
