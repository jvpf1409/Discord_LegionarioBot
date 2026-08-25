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
from utils.tiempo import fecha_hora_desde_timestamp, parse_fecha_hora
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


class ConfirmarEliminarRaidView(discord.ui.View):
    """Confirmación antes de borrar una raid de forma permanente."""

    def __init__(self, raid_id: str, titulo: str, autor_id: int):
        super().__init__(timeout=60)
        self.raid_id = raid_id
        self.titulo = titulo
        self.autor_id = autor_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "❌ Solo quien ejecutó el comando puede confirmar esto.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(
                    content="⌛ Se acabó el tiempo, la raid no fue eliminada.", view=self
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Sí, eliminar permanentemente",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
    )
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        raid = storage.obtener_raid(self.raid_id)
        if raid is not None:
            try:
                canal = interaction.client.get_channel(raid["canal_id"])
                mensaje = await canal.fetch_message(raid["mensaje_id"])
                await mensaje.delete()
            except Exception:
                pass
            storage.eliminar_raid(self.raid_id)

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"🗑️ Raid **{self.titulo}** (ID: {self.raid_id}) eliminada permanentemente.",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="Operación cancelada — la raid **no** fue eliminada.", view=self
        )
        self.stop()


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

    # ---------------------- DUPLICAR ----------------------
    @raid_group.command(
        name="duplicar",
        description="Duplica una raid cambiando solamente su fecha y hora",
    )
    @app_commands.describe(
        raid_id="ID de la raid que quieres duplicar",
        fecha="Nueva fecha en formato DD/MM/AAAA (ej: 07/08/2026)",
        hora="Nueva hora en formato 24h HH:MM (ej: 22:00)",
    )
    @es_organizador()
    async def duplicar(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        fecha: str,
        hora: str,
    ):
        raid_original = storage.obtener_raid(raid_id)
        if raid_original is None or raid_original.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe esa raid en este servidor.", ephemeral=True
            )
            return

        try:
            fecha_hora_ts = parse_fecha_hora(fecha, hora)
        except ValueError:
            await interaction.response.send_message(
                "❌ Fecha u hora inválidas. Usa `DD/MM/AAAA` para la fecha y "
                "`HH:MM` (24h) para la hora.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        canal_publicacion = self.bot.get_channel(raid_original["canal_id"])
        if canal_publicacion is None:
            try:
                canal_publicacion = await self.bot.fetch_channel(raid_original["canal_id"])
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                canal_publicacion = None

        if not isinstance(canal_publicacion, discord.abc.Messageable):
            await interaction.followup.send(
                "❌ No pude encontrar el canal donde se publicó la raid original.",
                ephemeral=True,
            )
            return

        nueva_raid_id = storage.crear_raid(
            titulo=raid_original["titulo"],
            descripcion=raid_original["descripcion"],
            guild_id=interaction.guild_id,
            canal_id=raid_original["canal_id"],
            fecha_hora_ts=fecha_hora_ts,
            creado_por=interaction.user.id,
            canal_inscripciones_id=raid_original.get("canal_inscripciones_id"),
            imagen_url=raid_original.get("imagen_url"),
        )
        nueva_raid = storage.obtener_raid(nueva_raid_id)

        try:
            mensaje = await canal_publicacion.send(
                embed=construir_embed_raid(nueva_raid),
                view=RaidView(nueva_raid_id, abierta=True),
            )
        except (discord.Forbidden, discord.HTTPException):
            storage.actualizar_raid(nueva_raid_id, estado="cancelado")
            await interaction.followup.send(
                "❌ No pude publicar la copia en el canal de la raid original.",
                ephemeral=True,
            )
            return

        storage.actualizar_raid(nueva_raid_id, mensaje_id=mensaje.id)
        advertencia = await anunciar_publicacion(
            interaction.client,
            interaction.guild,
            "Raid",
            raid_original["titulo"],
            mensaje,
        )
        detalle_aviso = f"\n⚠️ {advertencia}" if advertencia else ""
        await interaction.followup.send(
            f"✅ Raid **{raid_original['titulo']}** duplicada y publicada "
            f"(ID original: {raid_id}, ID nuevo: {nueva_raid_id}).{detalle_aviso}",
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

    # ---------------------- EDITAR ----------------------
    @raid_group.command(
        name="editar",
        description="Edita una raid existente sin perder sus inscritos (solo administradores)",
    )
    @app_commands.describe(
        raid_id="ID de la raid a editar",
        titulo="Nuevo título (opcional)",
        descripcion="Nueva descripción (opcional)",
        fecha="Nueva fecha DD/MM/AAAA; conserva la actual si se omite",
        hora="Nueva hora HH:MM; conserva la actual si se omite",
        imagen="Nueva imagen (opcional)",
        quitar_imagen="Quita la imagen actual de la raid",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def editar(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        titulo: str = None,
        descripcion: str = None,
        fecha: str = None,
        hora: str = None,
        imagen: discord.Attachment = None,
        quitar_imagen: bool = False,
    ):
        if not raid_id.isdecimal():
            await interaction.response.send_message("❌ El ID de la raid no es válido.", ephemeral=True)
            return

        raid = storage.obtener_raid(raid_id)
        if raid is None or raid.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe esa raid en este servidor.", ephemeral=True
            )
            return

        if imagen is not None and quitar_imagen:
            await interaction.response.send_message(
                "❌ No puedes subir una imagen y quitarla al mismo tiempo.", ephemeral=True
            )
            return
        if imagen is not None and not (imagen.content_type or "").startswith("image/"):
            await interaction.response.send_message(
                "❌ El archivo adjunto debe ser una imagen.", ephemeral=True
            )
            return

        cambios = {}
        if titulo is not None:
            titulo = titulo.strip()
            if not titulo:
                await interaction.response.send_message(
                    "❌ El título no puede quedar vacío.", ephemeral=True
                )
                return
            cambios["titulo"] = titulo
        if descripcion is not None:
            descripcion = descripcion.strip()
            if not descripcion:
                await interaction.response.send_message(
                    "❌ La descripción no puede quedar vacía.", ephemeral=True
                )
                return
            cambios["descripcion"] = descripcion

        if fecha is not None or hora is not None:
            fecha_actual, hora_actual = fecha_hora_desde_timestamp(raid["fecha_hora_ts"])
            try:
                cambios["fecha_hora_ts"] = parse_fecha_hora(
                    fecha or fecha_actual, hora or hora_actual
                )
            except ValueError:
                await interaction.response.send_message(
                    "❌ Fecha u hora inválidas. Usa `DD/MM/AAAA` y `HH:MM` (24h).",
                    ephemeral=True,
                )
                return
            cambios["recordatorio_enviado"] = False

        if imagen is not None:
            cambios["imagen_url"] = imagen.url
        elif quitar_imagen:
            cambios["imagen_url"] = None

        if not cambios:
            await interaction.response.send_message(
                "⚠️ Indica al menos un dato para modificar.", ephemeral=True
            )
            return

        raid = storage.actualizar_raid(raid_id, **cambios)
        aviso = ""
        try:
            canal = self.bot.get_channel(raid["canal_id"])
            if canal is None:
                canal = await self.bot.fetch_channel(raid["canal_id"])
            mensaje = await canal.fetch_message(raid["mensaje_id"])
            if raid["estado"] == "abierto":
                view = RaidView(raid_id, abierta=True)
            elif raid["estado"] == "cerrado":
                view = RaidView(raid_id, abierta=False)
            else:
                view = None
            await mensaje.edit(embed=construir_embed_raid(raid), view=view)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, AttributeError):
            aviso = "\n⚠️ Los datos se guardaron, pero no pude actualizar el mensaje publicado."

        await interaction.response.send_message(
            f"✅ Raid **{raid['titulo']}** (ID: {raid_id}) actualizada sin perder inscritos.{aviso}",
            ephemeral=True,
        )

    # ---------------------- ELIMINAR ----------------------
    @raid_group.command(
        name="eliminar",
        description="Elimina una raid de forma PERMANENTE (solo administradores)",
    )
    @app_commands.describe(raid_id="ID de la raid a eliminar")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def eliminar(self, interaction: discord.Interaction, raid_id: str):
        if not raid_id.isdecimal():
            await interaction.response.send_message("❌ El ID de la raid no es válido.", ephemeral=True)
            return

        raid = storage.obtener_raid(raid_id)
        if raid is None or raid.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe esa raid en este servidor.", ephemeral=True
            )
            return

        view = ConfirmarEliminarRaidView(raid_id, raid["titulo"], interaction.user.id)
        await interaction.response.send_message(
            f"⚠️ **¿Seguro que quieres eliminar la raid #{raid_id} — {raid['titulo']}?**\n"
            "Esta acción es **permanente**: borra el mensaje de la raid y todos sus datos "
            "incluidas las inscripciones.",
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()

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
            if r.get("creado_por"):
                resumen += f"\n👤 Creada por: <@{r['creado_por']}>"
            else:
                resumen += "\n👤 Creada por: No registrado"
            embed.add_field(name=f"#{r['id']} — {r['titulo']} ({r['estado']})", value=resumen, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Manejo de errores de permisos para todo el grupo
    @crear.error
    @duplicar.error
    @cerrar.error
    @cancelar.error
    @editar.error
    @eliminar.error
    async def on_permission_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            mensaje = f"🚫 Necesitas el rol **{ROL_OFICIAL}** para usar este comando."
        elif isinstance(error, app_commands.MissingPermissions):
            mensaje = "🚫 Necesitas permisos de administrador para usar este comando."
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
