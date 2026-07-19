"""
Cog con los comandos de administración de eventos:
crear, cerrar, registrar ganador, listar, cancelar.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.anuncios import anunciar_publicacion
from utils.permisos import es_organizador
from utils.tiempo import parse_fecha_hora
from cogs.vistas import EventoView, construir_embed_evento


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
        self.imagen_url = imagen_url
        self.canal_inscripciones_id = canal_inscripciones_id
        self.guild_id = guild_id
        self.creado_por = creado_por

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        evento_id = storage.crear_evento(
            titulo=self.titulo,
            descripcion=self.descripcion.value.strip(),
            guild_id=self.guild_id,
            canal_id=self.canal_publicacion.id,
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
            await interaction.followup.send(
                f"❌ No tengo permiso para publicar en {self.canal_publicacion.mention}.", ephemeral=True
            )
            return

        storage.actualizar_evento(evento_id, mensaje_id=mensaje.id)
        advertencia = await anunciar_publicacion(
            interaction.client, interaction.guild, "Evento", self.titulo, mensaje
        )
        detalle_aviso = f"\n⚠️ {advertencia}" if advertencia else ""
        await interaction.followup.send(
            f"✅ Evento **{self.titulo}** publicado en {self.canal_publicacion.mention} "
            f"(ID: {evento_id}).{detalle_aviso}",
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
        tipo_inscripcion="Individual (solo nombre de personaje) o Grupal (equipos completos ya formados)",
        fecha="Fecha del evento en formato DD/MM/AAAA (ej: 30/06/2026)",
        hora="Hora del evento en formato 24h HH:MM (ej: 23:00)",
        canal_publicacion="Canal donde se publicará el evento (embed + botones)",
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
    @evento_group.command(name="registrar_ganador", description="Registra al ganador y finaliza el evento")
    @app_commands.describe(
        evento_id="ID del evento",
        ganador="Participante ganador (solo para eventos individuales)",
        numero_equipo="Número del equipo ganador (solo para eventos grupales)",
    )
    @es_organizador()
    async def registrar_ganador(
        self,
        interaction: discord.Interaction,
        evento_id: str,
        ganador: discord.Member = None,
        numero_equipo: app_commands.Range[int, 1, 20] = None,
    ):
        evento = storage.obtener_evento(evento_id)
        if evento is None:
            await interaction.response.send_message("❌ No existe ese evento.", ephemeral=True)
            return
        if evento["tipo_inscripcion"] == "grupal":
            if numero_equipo is None:
                await interaction.response.send_message(
                    "❌ Indica `numero_equipo` para este evento grupal.", ephemeral=True
                )
                return
            if not evento["equipos"]:
                await interaction.response.send_message("⚠️ No hay equipos inscritos en este evento.", ephemeral=True)
                return
            if numero_equipo > len(evento["equipos"]):
                await interaction.response.send_message(
                    f"❌ Ese equipo no existe. Hay {len(evento['equipos'])} equipos.", ephemeral=True
                )
                return
            equipo_ganador = evento["equipos"][numero_equipo - 1]
            nombre_ganador = equipo_ganador["nombre_equipo"]
            detalle_nombre = "Integrantes"
            detalle = "\n".join(
                f"• **{i['rol']}** — {i['personaje']}" for i in equipo_ganador["integrantes"]
            ) or "_(sin integrantes)_"
        else:
            if ganador is None:
                await interaction.response.send_message(
                    "❌ Selecciona `ganador` para este evento individual.", ephemeral=True
                )
                return
            participante = next(
                (p for p in evento["participantes"] if p["user_id"] == ganador.id), None
            )
            if participante is None:
                await interaction.response.send_message(
                    "❌ Ese usuario no está inscrito en el evento.", ephemeral=True
                )
                return
            nombre_ganador = participante["personaje"]
            detalle_nombre = "Ganador"
            detalle = f"**{participante['personaje']}** — {ganador.mention}"

        storage.actualizar_evento(evento_id, estado="finalizado", ganador=nombre_ganador)

        evento = storage.obtener_evento(evento_id)
        try:
            canal = self.bot.get_channel(evento["canal_id"])
            mensaje_original = await canal.fetch_message(evento["mensaje_id"])
            await mensaje_original.edit(embed=construir_embed_evento(evento), view=EventoView(evento_id, abierto=False))
        except Exception:
            pass

        embed = discord.Embed(
            title=f"🏆 ¡Tenemos ganador! — {evento['titulo']}",
            description=f"**{nombre_ganador}** se lleva la victoria 🎉",
            color=discord.Color.gold(),
        )
        embed.add_field(name=detalle_nombre, value=detalle, inline=False)
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
                resumen = f"Equipos: {len(e['equipos'])}"
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
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 Necesitas permiso de **Gestionar servidor** (o el rol de oficial configurado) para usar este comando.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(f"⚠️ Ocurrió un error: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Eventos(bot))
