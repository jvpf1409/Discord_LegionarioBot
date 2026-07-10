"""
Cog con los comandos de administración de eventos:
crear, cerrar, registrar ganador, listar, cancelar.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.tiempo import parse_fecha_hora
from cogs.vistas import EventoView, construir_embed_evento

logger = logging.getLogger(__name__)

ROL_OFICIAL = "Legionario Oficial"


def es_organizador():
    """Requiere el rol de oficial de la hermandad (ajustable arriba en ROL_OFICIAL)."""
    return app_commands.checks.has_role(ROL_OFICIAL)


class DescripcionEventoModal(discord.ui.Modal, title="Descripción del evento"):
    """
    Los parámetros de un slash command son campos de una sola línea (Discord no
    permite saltos de línea ahí). Por eso la descripción se pide aparte, en un
    modal con un campo tipo párrafo, que sí admite varias líneas.
    """

    descripcion = discord.ui.TextInput(
        label="Descripción",
        style=discord.TextStyle.paragraph,
        placeholder="Detalles del evento",
        max_length=1000,
        required=True,
    )

    def __init__(
        self,
        *,
        titulo: str,
        tipo_inscripcion: str,
        fecha_hora_ts: int,
        canal_publicacion: discord.TextChannel,
        num_equipos: int | None,
        imagen_url: str | None,
        canal_inscripciones_id: int | None,
        guild_id: int,
        creado_por: int,
    ):
        super().__init__()
        self.titulo = titulo
        self.tipo_inscripcion = tipo_inscripcion
        self.fecha_hora_ts = fecha_hora_ts
        self.canal_publicacion = canal_publicacion
        self.num_equipos = num_equipos
        self.imagen_url = imagen_url
        self.canal_inscripciones_id = canal_inscripciones_id
        self.guild_id = guild_id
        self.creado_por = creado_por

    async def on_submit(self, interaction: discord.Interaction):
        evento_id = storage.crear_evento(
            titulo=self.titulo,
            descripcion=self.descripcion.value.strip(),
            guild_id=self.guild_id,
            canal_id=self.canal_publicacion.id,
            num_equipos=self.num_equipos,
            creado_por=self.creado_por,
            fecha_hora_ts=self.fecha_hora_ts,
            tipo_inscripcion=self.tipo_inscripcion,
            canal_inscripciones_id=self.canal_inscripciones_id,
            imagen_url=self.imagen_url,
        )
        evento = storage.obtener_evento(evento_id)
        embed = construir_embed_evento(evento)
        view = EventoView(evento_id, abierto=True)

        try:
            mensaje = await self.canal_publicacion.send(embed=embed, view=view)
        except discord.Forbidden:
            storage.actualizar_evento(evento_id, estado="finalizado")
            await interaction.response.send_message(
                f"❌ No tengo permiso para publicar en {self.canal_publicacion.mention}.", ephemeral=True
            )
            return

        storage.actualizar_evento(evento_id, mensaje_id=mensaje.id)
        await interaction.response.send_message(
            f"✅ Evento **{self.titulo}** publicado en {self.canal_publicacion.mention} (ID: {evento_id}).",
            ephemeral=True,
        )


class Eventos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    evento_group = app_commands.Group(
        name="evento", description="Gestiona eventos de la hermandad"
    )

    # ---------------------- CREAR ----------------------
    @evento_group.command(name="crear", description="Crea un nuevo evento con inscripciones abiertas")
    @app_commands.describe(
        titulo="Título del evento (ej: Mítico+ semanal)",
        tipo_inscripcion="Individual (lista simple de inscritos, sin equipos) o Grupal (equipos completos ya formados)",
        fecha="Fecha del evento en formato DD/MM/AAAA (ej: 30/06/2026)",
        hora="Hora del evento en formato 24h HH:MM (ej: 23:00)",
        canal_publicacion="Canal donde se publicará el evento (embed + botones)",
        num_equipos="Solo para Grupal: cupo máximo de equipos (vacío = sin límite)",
        imagen="Imagen opcional para el evento (banner, logo del jefe, etc.)",
        canal_inscripciones="Canal opcional donde se irá anunciando cada inscripción en vivo",
    )
    @app_commands.choices(tipo_inscripcion=[
        app_commands.Choice(name="Individual", value="individual"),
        app_commands.Choice(name="Grupal", value="grupal"),
    ])
    @es_organizador()
    async def crear(
        self,
        interaction: discord.Interaction,
        titulo: str,
        tipo_inscripcion: app_commands.Choice[str],
        fecha: str,
        hora: str,
        canal_publicacion: discord.TextChannel,
        num_equipos: app_commands.Range[int, 1, 20] = None,
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

        modal = DescripcionEventoModal(
            titulo=titulo,
            tipo_inscripcion=tipo_inscripcion.value,
            fecha_hora_ts=fecha_hora_ts,
            canal_publicacion=canal_publicacion,
            num_equipos=num_equipos if tipo_inscripcion.value == "grupal" else None,
            imagen_url=imagen.url if imagen else None,
            canal_inscripciones_id=canal_inscripciones.id if canal_inscripciones else None,
            guild_id=interaction.guild_id,
            creado_por=interaction.user.id,
        )
        await interaction.response.send_modal(modal)

    # ---------------------- CERRAR ----------------------
    @evento_group.command(name="cerrar", description="Cierra las inscripciones de un evento")
    @app_commands.describe(evento_id="ID del evento a cerrar")
    @es_organizador()
    async def cerrar(self, interaction: discord.Interaction, evento_id: str):
        evento = storage.obtener_evento(evento_id)
        if evento is None:
            await interaction.response.send_message("❌ No existe ese evento.", ephemeral=True)
            return
        if evento["estado"] != "abierto":
            await interaction.response.send_message("⚠️ Este evento ya no está abierto.", ephemeral=True)
            return

        storage.actualizar_evento(evento_id, estado="cerrado")
        evento = storage.obtener_evento(evento_id)

        embed = construir_embed_evento(evento)
        view = EventoView(evento_id, abierto=False)
        try:
            canal = self.bot.get_channel(evento["canal_id"])
            mensaje_original = await canal.fetch_message(evento["mensaje_id"])
            await mensaje_original.edit(embed=embed, view=view)
        except Exception:
            pass

        if evento["tipo_inscripcion"] == "grupal":
            resumen = f"{len(evento['equipos'])} equipos inscritos"
        else:
            resumen = f"{len(evento['participantes'])} inscritos"
        await interaction.response.send_message(
            f"🔒 Inscripciones cerradas para **{evento['titulo']}** ({resumen}).",
        )

    # ---------------------- REGISTRAR GANADOR ----------------------
    @evento_group.command(name="registrar_ganador", description="Marca el equipo ganador y finaliza el evento (solo eventos grupales)")
    @app_commands.describe(evento_id="ID del evento", numero_equipo="Número del equipo ganador (según el orden de inscripción)")
    @es_organizador()
    async def registrar_ganador(self, interaction: discord.Interaction, evento_id: str, numero_equipo: app_commands.Range[int, 1, 20]):
        evento = storage.obtener_evento(evento_id)
        if evento is None:
            await interaction.response.send_message("❌ No existe ese evento.", ephemeral=True)
            return
        if evento["tipo_inscripcion"] != "grupal":
            await interaction.response.send_message(
                "⚠️ Este evento es individual: no tiene equipos ni ganador, es solo una lista de inscritos.",
                ephemeral=True,
            )
            return
        if not evento["equipos"]:
            await interaction.response.send_message("⚠️ Todavía no se ha inscrito ningún equipo.", ephemeral=True)
            return
        if numero_equipo < 1 or numero_equipo > len(evento["equipos"]):
            await interaction.response.send_message(f"❌ Ese equipo no existe. Hay {len(evento['equipos'])} equipos.", ephemeral=True)
            return

        equipo_ganador = evento["equipos"][numero_equipo - 1]
        nombre_ganador = equipo_ganador["nombre_equipo"]
        storage.actualizar_evento(evento_id, estado="finalizado", ganador=nombre_ganador)

        evento = storage.obtener_evento(evento_id)
        try:
            canal = self.bot.get_channel(evento["canal_id"])
            mensaje_original = await canal.fetch_message(evento["mensaje_id"])
            await mensaje_original.edit(embed=construir_embed_evento(evento), view=EventoView(evento_id, abierto=False))
        except Exception:
            pass

        integrantes = "\n".join(
            f"• **{i['rol']}** — {i['personaje']}" for i in equipo_ganador["integrantes"]
        ) or "_(sin integrantes)_"
        embed = discord.Embed(
            title=f"🏆 ¡Tenemos ganador! — {evento['titulo']}",
            description=f"**{nombre_ganador}** se lleva la victoria 🎉",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Integrantes", value=integrantes, inline=False)
        await interaction.response.send_message(embed=embed)

    # ---------------------- LISTAR ----------------------
    @evento_group.command(name="listar", description="Lista los eventos del servidor")
    @app_commands.describe(estado="Filtra por estado (opcional)")
    @app_commands.choices(estado=[
        app_commands.Choice(name="Abiertos", value="abierto"),
        app_commands.Choice(name="Cerrados", value="cerrado"),
        app_commands.Choice(name="Finalizados", value="finalizado"),
    ])
    async def listar(self, interaction: discord.Interaction, estado: app_commands.Choice[str] = None):
        eventos = storage.listar_eventos(interaction.guild_id, estado.value if estado else None)
        if not eventos:
            await interaction.response.send_message("No hay eventos que coincidan.", ephemeral=True)
            return

        embed = discord.Embed(title="📅 Eventos de la hermandad", color=discord.Color.blurple())
        for e in eventos:
            if e["tipo_inscripcion"] == "grupal":
                resumen = f"Equipos: {len(e['equipos'])}/{e['num_equipos']}" if e["num_equipos"] else f"Equipos: {len(e['equipos'])}"
            else:
                resumen = f"Inscritos: {len(e['participantes'])}"
            tipo_emoji = "👥" if e["tipo_inscripcion"] == "grupal" else "🙋"
            if e.get("fecha_hora_ts"):
                resumen += f"\n📅 <t:{e['fecha_hora_ts']}:f>"
            embed.add_field(
                name=f"#{e['id']} — {e['titulo']} ({e['estado']}) {tipo_emoji}",
                value=resumen,
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------------------- CANCELAR ----------------------
    @evento_group.command(name="cancelar", description="Cancela un evento por completo")
    @app_commands.describe(evento_id="ID del evento a cancelar")
    @es_organizador()
    async def cancelar(self, interaction: discord.Interaction, evento_id: str):
        evento = storage.obtener_evento(evento_id)
        if evento is None:
            await interaction.response.send_message("❌ No existe ese evento.", ephemeral=True)
            return
        storage.actualizar_evento(evento_id, estado="finalizado", ganador="— Evento cancelado —")
        try:
            canal = self.bot.get_channel(evento["canal_id"])
            mensaje_original = await canal.fetch_message(evento["mensaje_id"])
            await mensaje_original.edit(embed=construir_embed_evento(storage.obtener_evento(evento_id)), view=None)
        except Exception:
            pass
        await interaction.response.send_message(f"🗑️ Evento **{evento['titulo']}** cancelado.")

    # Manejo de errores de permisos para todo el grupo
    @crear.error
    @cerrar.error
    @registrar_ganador.error
    @cancelar.error
    async def on_permission_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            mensaje = f"🚫 Necesitas el rol **{ROL_OFICIAL}** para usar este comando."
        else:
            # CommandInvokeError envuelve la excepción real en .original; la mostramos
            # y la registramos completa para poder diagnosticarla en los logs de Render.
            original = getattr(error, "original", error)
            logger.exception("Error inesperado en un comando de /evento", exc_info=original)
            mensaje = f"⚠️ Ocurrió un error: {original}"

        try:
            if interaction.response.is_done():
                await interaction.followup.send(mensaje, ephemeral=True)
            else:
                await interaction.response.send_message(mensaje, ephemeral=True)
        except discord.HTTPException:
            # La interacción ya expiró o fue respondida por otra vía: no hay forma
            # de avisar al usuario, pero no debe tumbar el bot.
            logger.warning("No se pudo notificar el error al usuario (interacción ya cerrada).")


async def setup(bot: commands.Bot):
    await bot.add_cog(Eventos(bot))
