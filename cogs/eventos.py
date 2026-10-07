"""
Cog con los comandos de administración de eventos:
crear, cerrar, registrar ganador, listar, cancelar.
"""

import io
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.anuncios import anunciar_publicacion
from utils.banner_ganador import ERRORES_IMAGEN, crear_banner_ganador, validar_imagen_fondo
from utils.equipos import buscar_equipo, numero_de_equipo
from utils.equipos_armados import MAX_EQUIPOS, inscritos_csv, texto_para_ia
from utils.recordatorios import (
    AYUDA_DURACION, campos_recordatorio_extra, parsear_duracion, texto_recordatorio_extra,
)
from utils.permisos import es_administrador, es_organizador, mensaje_error_permiso
from utils.tiempo import fecha_hora_desde_timestamp, parse_fecha_hora
from cogs.vistas import EventoView, anunciar_promovidos, construir_embed_evento
from cogs.vistas_armado import ArmarEquiposView

logger = logging.getLogger(__name__)


def _construir_anuncio_ganador(
    titulo_evento: str,
    nombre_ganador: str,
    integrantes: str | None = None,
) -> str:
    anuncio = (
        f"🏆 **¡Tenemos ganador en {titulo_evento}!**\n"
        f"{nombre_ganador} se lleva la victoria 🎉"
    )
    if integrantes is not None:
        anuncio += f"\n\n**Integrantes**\n{integrantes}"
    return anuncio

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
        cantidad_equipos: int | None = None,
        recordatorio_extra_min: int | None = None,
    ):
        super().__init__()
        self.cantidad_equipos = cantidad_equipos
        self.recordatorio_extra_min = recordatorio_extra_min
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
            cantidad_equipos=self.cantidad_equipos,
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

        campos_extra = campos_recordatorio_extra(
            self.recordatorio_extra_min, self.fecha_hora_ts, int(time.time())
        )
        storage.actualizar_evento(evento_id, mensaje_id=mensaje.id, **campos_extra)
        advertencia = await anunciar_publicacion(
            interaction.client, interaction.guild, "Evento", self.titulo, mensaje
        )
        detalle_aviso = f"\n⚠️ {advertencia}" if advertencia else ""
        detalle_aviso += texto_recordatorio_extra(self.recordatorio_extra_min, campos_extra)
        await interaction.followup.send(
            f"✅ Evento **{self.titulo}** publicado en {self.canal_publicacion.mention} "
            f"(ID: {evento_id}).{detalle_aviso}",
            ephemeral=True,
        )


class ConfirmarEliminarView(discord.ui.View):
    """Confirmación antes de borrar un evento de forma permanente."""

    def __init__(self, evento_id: str, titulo: str, autor_id: int):
        super().__init__(timeout=60)
        self.evento_id = evento_id
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
                await self.message.edit(content="⌛ Se acabó el tiempo, el evento no fue eliminado.", view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Sí, eliminar permanentemente", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        evento = storage.obtener_evento(self.evento_id)
        if evento is not None:
            try:
                canal = interaction.client.get_channel(evento["canal_id"])
                mensaje = await canal.fetch_message(evento["mensaje_id"])
                await mensaje.delete()
            except Exception:
                pass
            storage.eliminar_evento(self.evento_id)

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"🗑️ Evento **{self.titulo}** (ID: {self.evento_id}) eliminado permanentemente.",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="Operación cancelada — el evento **no** fue eliminado.", view=self
        )
        self.stop()


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
        tipo_inscripcion="Individual (lista simple), Grupal (equipos ya formados) o Equipos armados (individual, la organización arma los equipos)",
        fecha="Fecha del evento en formato DD/MM/AAAA (ej: 30/06/2026)",
        hora="Hora del evento en formato 24h HH:MM (ej: 23:00)",
        canal_publicacion="Canal donde se publicará el evento (embed + botones)",
        imagen="Imagen opcional para el evento (banner, logo del jefe, etc.)",
        canal_inscripciones="Canal opcional donde se irá anunciando cada inscripción en vivo",
        cantidad_equipos="Solo Equipos armados: cuántos equipos de 1 Tank, 1 Healer y 3 DPS se formarán",
        recordatorio_extra="Recordatorio adicional al de 30 min, ej: 2h, 1d, 1d12h (opcional)",
    )
    @app_commands.choices(tipo_inscripcion=[
        app_commands.Choice(name="Individual", value="individual"),
        app_commands.Choice(name="Grupal", value="grupal"),
        app_commands.Choice(name="Equipos armados por la organización", value="armado"),
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
        cantidad_equipos: app_commands.Range[int, 1, MAX_EQUIPOS] = None,
        recordatorio_extra: str = None,
    ):
        try:
            recordatorio_extra_min = parsear_duracion(recordatorio_extra) if recordatorio_extra else None
        except ValueError:
            await interaction.response.send_message(
                f"❌ `recordatorio_extra` no es válido. {AYUDA_DURACION}", ephemeral=True
            )
            return
        if tipo_inscripcion.value == "armado" and cantidad_equipos is None:
            await interaction.response.send_message(
                "❌ Indica `cantidad_equipos` para un evento de Equipos armados.", ephemeral=True
            )
            return
        if tipo_inscripcion.value != "armado" and cantidad_equipos is not None:
            await interaction.response.send_message(
                "❌ `cantidad_equipos` solo aplica a eventos de Equipos armados.", ephemeral=True
            )
            return
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
            cantidad_equipos=cantidad_equipos,
            recordatorio_extra_min=recordatorio_extra_min,
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

    # ---------------------- EDITAR ----------------------
    @evento_group.command(
        name="editar",
        description="Edita un evento sin perder sus inscripciones (solo Maestro)",
    )
    @app_commands.describe(
        evento_id="ID del evento que quieres editar",
        titulo="Nuevo título (opcional)",
        descripcion="Nueva descripción (opcional)",
        fecha="Nueva fecha DD/MM/AAAA; conserva la actual si se omite",
        hora="Nueva hora HH:MM; conserva la actual si se omite",
        imagen="Nueva imagen (opcional)",
        quitar_imagen="Quita la imagen actual del evento",
        cantidad_equipos="Solo Equipos armados: nueva cantidad de equipos (amplía o reduce los cupos)",
        recordatorio_extra="Recordatorio adicional al de 30 min, ej: 2h, 1d; 0 para quitarlo",
    )
    @es_administrador()
    async def editar(
        self,
        interaction: discord.Interaction,
        evento_id: str,
        titulo: str = None,
        descripcion: str = None,
        fecha: str = None,
        hora: str = None,
        imagen: discord.Attachment = None,
        quitar_imagen: bool = False,
        cantidad_equipos: app_commands.Range[int, 1, MAX_EQUIPOS] = None,
        recordatorio_extra: str = None,
    ):
        try:
            recordatorio_extra_min = parsear_duracion(recordatorio_extra) if recordatorio_extra else None
        except ValueError:
            await interaction.response.send_message(
                f"❌ `recordatorio_extra` no es válido. {AYUDA_DURACION}", ephemeral=True
            )
            return
        evento = storage.obtener_evento(evento_id) if evento_id.isdecimal() else None
        if evento is None or evento.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe ese evento en este servidor.", ephemeral=True
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
        for campo, valor in (("titulo", titulo), ("descripcion", descripcion)):
            if valor is not None:
                valor = valor.strip()
                if not valor:
                    await interaction.response.send_message(
                        f"❌ {campo.capitalize()} no puede quedar vacío.", ephemeral=True
                    )
                    return
                cambios[campo] = valor

        if fecha is not None or hora is not None:
            if not evento.get("fecha_hora_ts"):
                if fecha is None or hora is None:
                    await interaction.response.send_message(
                        "❌ El evento no tiene una fecha anterior válida; indica fecha y hora.",
                        ephemeral=True,
                    )
                    return
                fecha_actual, hora_actual = fecha, hora
            else:
                fecha_actual, hora_actual = fecha_hora_desde_timestamp(
                    evento["fecha_hora_ts"]
                )
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

        if cantidad_equipos is not None:
            if evento["tipo_inscripcion"] != "armado":
                await interaction.response.send_message(
                    "❌ `cantidad_equipos` solo aplica a eventos de Equipos armados.", ephemeral=True
                )
                return
            if cantidad_equipos < len(evento["equipos"]):
                await interaction.response.send_message(
                    f"❌ Ya hay {len(evento['equipos'])} equipos publicados. Vuelve a armarlos "
                    "con `/evento armar_equipos` antes de reducir la cantidad.",
                    ephemeral=True,
                )
                return
            cambios["cantidad_equipos"] = cantidad_equipos

        campos_extra = None
        if recordatorio_extra_min is not None or "fecha_hora_ts" in cambios:
            # Un cambio de fecha también reprograma el recordatorio extra.
            minutos = (
                recordatorio_extra_min
                if recordatorio_extra_min is not None
                else evento.get("recordatorio_extra_min")
            )
            campos_extra = campos_recordatorio_extra(
                minutos, cambios.get("fecha_hora_ts", evento.get("fecha_hora_ts")), int(time.time())
            )
            cambios.update(campos_extra)

        if not cambios:
            await interaction.response.send_message(
                "⚠️ Indica al menos un dato para modificar.", ephemeral=True
            )
            return

        antes = evento
        evento = storage.actualizar_evento(evento_id, **cambios)
        if evento["tipo_inscripcion"] == "armado":
            await anunciar_promovidos(self.bot, antes, evento)
        aviso = ""
        try:
            canal = self.bot.get_channel(evento["canal_id"])
            if canal is None:
                canal = await self.bot.fetch_channel(evento["canal_id"])
            mensaje = await canal.fetch_message(evento["mensaje_id"])
            view = EventoView(evento_id, abierto=evento["estado"] == "abierto")
            await mensaje.edit(embed=construir_embed_evento(evento), view=view)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, AttributeError):
            aviso = "\n⚠️ Los datos se guardaron, pero no pude actualizar el mensaje publicado."

        if recordatorio_extra_min == 0:
            aviso += "\n🔕 Recordatorio extra quitado; queda solo el de 30 minutos."
        elif campos_extra is not None:
            aviso += texto_recordatorio_extra(campos_extra["recordatorio_extra_min"], campos_extra)
        await interaction.response.send_message(
            f"✅ Evento **{evento['titulo']}** (ID: {evento_id}) actualizado sin perder "
            f"participantes ni equipos.{aviso}",
            ephemeral=True,
        )

    # ---------------------- REGISTRAR GANADOR ----------------------
    @evento_group.command(name="registrar_ganador", description="Registra al ganador y finaliza el evento")
    @app_commands.describe(
        evento_id="ID del evento",
        imagen_fondo="Imagen de fondo personalizada para el banner del ganador",
        ganador="Usuario ganador (opcional, solo para eventos individuales)",
        numero_equipo="Número del equipo ganador (solo para eventos grupales)",
    )
    @es_organizador()
    async def registrar_ganador(
        self,
        interaction: discord.Interaction,
        evento_id: str,
        imagen_fondo: discord.Attachment,
        ganador: discord.Member = None,
        numero_equipo: app_commands.Range[int, 1] = None,
    ):
        evento = storage.obtener_evento(evento_id)
        if evento is None:
            await interaction.response.send_message("❌ No existe ese evento.", ephemeral=True)
            return
        error_imagen = validar_imagen_fondo(imagen_fondo)
        if error_imagen:
            await interaction.response.send_message(error_imagen, ephemeral=True)
            return
        if evento["tipo_inscripcion"] in ("grupal", "armado"):
            if numero_equipo is None:
                await interaction.response.send_message(
                    "❌ Indica `numero_equipo` para este evento grupal.", ephemeral=True
                )
                return
            if not evento["equipos"]:
                if evento["tipo_inscripcion"] == "armado":
                    mensaje = "⚠️ Aún no se publican los equipos. Usa `/evento armar_equipos`."
                else:
                    mensaje = "⚠️ No hay equipos inscritos en este evento."
                await interaction.response.send_message(mensaje, ephemeral=True)
                return
            equipo_ganador = buscar_equipo(evento, numero_equipo)
            if equipo_ganador is None:
                disponibles = ", ".join(
                    f"#{numero_de_equipo(e, posicion)}"
                    for posicion, e in enumerate(evento["equipos"], start=1)
                )
                await interaction.response.send_message(
                    f"❌ Ese equipo no existe. Equipos inscritos: {disponibles}.", ephemeral=True
                )
                return
            nombre_ganador = equipo_ganador["nombre_equipo"]
            miembro_banner = None
            integrantes = "\n".join(
                f"• **{i['rol']}** — {i['personaje']}" for i in equipo_ganador["integrantes"]
            ) or "_(sin integrantes)_"
        else:
            if ganador is None:
                await interaction.response.send_message(
                    "❌ Selecciona `ganador` para este evento individual.",
                    ephemeral=True,
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
            nombre_ganador = ganador.mention
            miembro_banner = ganador
            integrantes = None

        await interaction.response.defer()
        try:
            fondo_data = await imagen_fondo.read()
            banner = await crear_banner_ganador(
                fondo_data,
                miembro_banner,
                nombre_equipo=nombre_ganador if miembro_banner is None else None,
            )
        except ERRORES_IMAGEN:
            logger.exception("La imagen de fondo del evento %s no es válida", evento_id)
            # Tras un defer público, el primer followup reemplazaría el mensaje
            # visible para todos; se borra para que el error llegue en privado.
            await interaction.delete_original_response()
            await interaction.followup.send(
                "❌ No pude procesar esa imagen. Prueba con un archivo PNG, JPG o WebP válido.",
                ephemeral=True,
            )
            return
        storage.actualizar_evento(evento_id, estado="finalizado", ganador=nombre_ganador)

        evento = storage.obtener_evento(evento_id)
        try:
            canal = self.bot.get_channel(evento["canal_id"])
            mensaje_original = await canal.fetch_message(evento["mensaje_id"])
            await mensaje_original.edit(embed=construir_embed_evento(evento), view=EventoView(evento_id, abierto=False))
        except Exception:
            pass

        anuncio = _construir_anuncio_ganador(evento["titulo"], nombre_ganador, integrantes)
        await interaction.followup.send(content=anuncio, file=banner)

    # ---------------------- ARMAR EQUIPOS ----------------------
    @evento_group.command(
        name="armar_equipos",
        description="Arma y publica los equipos de un evento de Equipos armados",
    )
    @app_commands.describe(evento_id="ID del evento")
    @es_organizador()
    async def armar_equipos(self, interaction: discord.Interaction, evento_id: str):
        evento = storage.obtener_evento(evento_id) if evento_id.isdecimal() else None
        if evento is None or evento.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe ese evento en este servidor.", ephemeral=True
            )
            return
        if evento["tipo_inscripcion"] != "armado":
            await interaction.response.send_message(
                "❌ Este comando solo aplica a eventos de Equipos armados.", ephemeral=True
            )
            return
        if evento["estado"] == "finalizado":
            await interaction.response.send_message("⚠️ Este evento ya finalizó.", ephemeral=True)
            return
        if not evento["participantes"]:
            await interaction.response.send_message(
                "⚠️ Todavía no hay inscritos en este evento.", ephemeral=True
            )
            return

        view = ArmarEquiposView(evento, interaction.user.id)
        await interaction.response.send_message(view.contenido(), view=view, ephemeral=True)
        view.interaccion_inicial = interaction

    # ---------------------- EXPORTAR INSCRITOS ----------------------
    @evento_group.command(
        name="exportar_inscritos",
        description="Descarga los inscritos de un evento de Equipos armados (para armar equipos con una IA)",
    )
    @app_commands.describe(evento_id="ID del evento")
    @es_organizador()
    async def exportar_inscritos(self, interaction: discord.Interaction, evento_id: str):
        evento = storage.obtener_evento(evento_id) if evento_id.isdecimal() else None
        if evento is None or evento.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe ese evento en este servidor.", ephemeral=True
            )
            return
        if evento["tipo_inscripcion"] != "armado":
            await interaction.response.send_message(
                "❌ Este comando solo aplica a eventos de Equipos armados.", ephemeral=True
            )
            return
        if not evento["participantes"]:
            await interaction.response.send_message(
                "⚠️ Todavía no hay inscritos en este evento.", ephemeral=True
            )
            return

        # utf-8-sig para que Excel respete los acentos al abrir el CSV.
        para_ia = discord.File(
            io.BytesIO(texto_para_ia(evento).encode("utf-8")),
            filename=f"evento-{evento_id}-para-ia.txt",
        )
        csv_inscritos = discord.File(
            io.BytesIO(inscritos_csv(evento).encode("utf-8-sig")),
            filename=f"evento-{evento_id}-inscritos.csv",
        )
        await interaction.response.send_message(
            f"📋 Inscritos de **{evento['titulo']}** ({len(evento['participantes'])}).\n"
            "• `para-ia.txt`: pégalo completo en la IA, ya incluye las instrucciones.\n"
            "• `inscritos.csv`: los mismos datos para abrir en Excel o Google Sheets.\n"
            "Con la propuesta, arma los equipos en `/evento armar_equipos`.",
            files=[para_ia, csv_inscritos],
            ephemeral=True,
        )

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
            elif e["tipo_inscripcion"] == "armado":
                resumen = f"Inscritos: {len(e['participantes'])} · Equipos: {e.get('cantidad_equipos', 1)}"
            else:
                resumen = f"Inscritos: {len(e['participantes'])}"
            tipo_emoji = {"grupal": "👥", "armado": "🧩"}.get(e["tipo_inscripcion"], "🙋")
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

    # ---------------------- ELIMINAR ----------------------
    @evento_group.command(name="eliminar", description="Elimina un evento de forma PERMANENTE (borra el mensaje y los datos)")
    @app_commands.describe(evento_id="ID del evento a eliminar")
    @es_organizador()
    async def eliminar(self, interaction: discord.Interaction, evento_id: str):
        evento = storage.obtener_evento(evento_id)
        if evento is None:
            await interaction.response.send_message("❌ No existe ese evento.", ephemeral=True)
            return

        view = ConfirmarEliminarView(evento_id, evento["titulo"], interaction.user.id)
        await interaction.response.send_message(
            f"⚠️ **¿Seguro que quieres eliminar el evento #{evento_id} — {evento['titulo']}?**\n"
            "Esta acción es **permanente**: borra el mensaje del evento y todos sus datos "
            "(inscritos, equipos, etc.) de la base de datos. No se puede deshacer.",
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()

    # Manejo de errores de permisos para todo el grupo
    @crear.error
    @cerrar.error
    @editar.error
    @registrar_ganador.error
    @armar_equipos.error
    @exportar_inscritos.error
    @cancelar.error
    @eliminar.error
    async def on_permission_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        mensaje = mensaje_error_permiso(error)
        if mensaje is None:
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
