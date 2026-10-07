"""
Cog con los comandos de prueba (/test ...). La mayoría generan vistas previas
privadas sin modificar datos; /test equipos_armados crea un evento de prueba
con inscritos ficticios para ensayar el armado de equipos.
"""

import logging
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from cogs.bienvenida import crear_tarjeta
from cogs.eventos import _construir_anuncio_ganador
from cogs.vistas import EventoView, construir_embed_evento
from utils import storage
from utils.banner_ganador import ERRORES_IMAGEN, crear_banner_ganador, validar_imagen_fondo
from utils.equipos_armados import CUPOS_POR_EQUIPO, MAX_EQUIPOS, categoria, resumen_cupos
from utils.permisos import es_administrador, es_organizador, mensaje_error_permiso
from utils.wow_data import CLASES

logger = logging.getLogger(__name__)

# IDs que no pertenecen a ninguna cuenta real: las menciones se ven como
# usuario desconocido y no notifican a nadie.
ID_FICTICIO_BASE = 100_000_000_000_000_000
NOMBRES_FICTICIOS = [
    "Thrallito", "Jainita", "Varianx", "Sylvanita", "Anduinn", "Tyrandë", "Malfurión",
    "Illidán", "Garroshh", "Vol'jinn", "Baine", "Lor'themar", "Velen", "Khadgarr",
    "Medivhh", "Uther", "Arthaz", "Bolvarr", "Magni", "Muradín", "Genn", "Alleria",
    "Turalyon", "Rexxar", "Chen", "Lili", "Zul'jin", "Rokhan", "Talanji", "Gelbin",
    "Mekkatorque", "Gazlowe", "Faol", "Liadrin", "Valeera", "Mathias", "Shaw",
    "Aethas", "Rommath", "Kael", "Vereesa", "Rhonin", "Modera", "Ansirem", "Kalec",
    "Wrathion", "Ebyssian", "Alexstrasza", "Ysera", "Nozdormu", "Chromie", "Merithra",
]


def inscritos_de_prueba(cantidad_equipos: int, suplentes: bool) -> list[dict]:
    """Inscritos ficticios: los cupos llenos de cada rol y, si se pide, algunos suplentes."""
    especializaciones = {"tank": [], "healer": [], "dps": []}
    for clase, specs in CLASES.items():
        for spec, rol in specs:
            especializaciones[categoria(rol)].append((clase, spec, rol))

    extra = {"tank": 1, "healer": 1, "dps": 2} if suplentes else {"tank": 0, "healer": 0, "dps": 0}
    nombres = random.sample(NOMBRES_FICTICIOS, len(NOMBRES_FICTICIOS))
    inscritos = []
    for c, por_equipo in CUPOS_POR_EQUIPO.items():
        for _ in range(por_equipo * cantidad_equipos + extra[c]):
            clase, spec, rol = random.choice(especializaciones[c])
            n = len(inscritos) + 1
            nombre = nombres[(n - 1) % len(nombres)]
            if n > len(nombres):
                nombre += str(n)
            inscritos.append({
                "user_id": ID_FICTICIO_BASE + n,
                "nombre_discord": f"Prueba{n:02d}",
                "personaje": nombre,
                "clase": clase,
                "especializacion": spec,
                "rol": rol,
                "ilvl": random.randint(610, 665),
                "io": random.randint(12, 36) * 100 + random.randint(0, 99),
            })
    # Mezcla el orden para que titulares y suplentes no queden agrupados por rol.
    random.shuffle(inscritos)
    return inscritos


class Pruebas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    test_group = app_commands.Group(
        name="test",
        description="Comandos para probar funciones del bot",
        guild_only=True,
    )

    # ---------------------- EQUIPOS ARMADOS ----------------------
    @test_group.command(
        name="equipos_armados",
        description="Publica aquí un evento de Equipos armados de prueba con inscritos ficticios",
    )
    @app_commands.describe(
        cantidad_equipos="Cuántos equipos de 1 Tank, 1 Healer y 3 DPS (por defecto 3)",
        suplentes="Agrega suplentes además de los cupos llenos (por defecto sí)",
        canal_inscripciones="Canal opcional para ver los avisos de suplentes que suben a titular",
    )
    @es_organizador()
    async def equipos_armados(
        self,
        interaction: discord.Interaction,
        cantidad_equipos: app_commands.Range[int, 1, MAX_EQUIPOS] = 3,
        suplentes: bool = True,
        canal_inscripciones: discord.TextChannel = None,
    ):
        canal = interaction.channel
        evento_id = storage.crear_evento(
            titulo="🧪 [TEST] Equipos armados",
            descripcion=(
                "Evento de prueba con inscritos ficticios para ensayar "
                "`/evento armar_equipos`. Bórralo con `/evento eliminar` al terminar."
            ),
            guild_id=interaction.guild_id,
            canal_id=canal.id,
            creado_por=interaction.user.id,
            fecha_hora_ts=int(time.time()) + 24 * 3600,
            tipo_inscripcion="armado",
            canal_inscripciones_id=canal_inscripciones.id if canal_inscripciones else None,
            cantidad_equipos=cantidad_equipos,
        )
        evento = storage.actualizar_evento(
            evento_id, participantes=inscritos_de_prueba(cantidad_equipos, suplentes)
        )

        try:
            mensaje = await canal.send(
                embed=construir_embed_evento(evento), view=EventoView(evento_id, abierto=True)
            )
        except discord.HTTPException:
            storage.eliminar_evento(evento_id)
            await interaction.response.send_message(
                f"❌ No pude publicar en {canal.mention}.", ephemeral=True
            )
            return
        storage.actualizar_evento(evento_id, mensaje_id=mensaje.id)

        await interaction.response.send_message(
            f"🧪 Evento de prueba **#{evento_id}** publicado con "
            f"{len(evento['participantes'])} inscritos ficticios.\n"
            f"{resumen_cupos(evento)}\n\n"
            f"• Arma los equipos: `/evento armar_equipos evento_id:{evento_id}`\n"
            f"• Exporta para la IA: `/evento exportar_inscritos evento_id:{evento_id}`\n"
            f"• Prueba ampliar: `/evento editar evento_id:{evento_id} cantidad_equipos:{min(cantidad_equipos + 1, MAX_EQUIPOS)}`\n"
            f"• Al terminar: `/evento eliminar evento_id:{evento_id}`\n"
            "Tú también puedes inscribirte con el botón para probar el flujo real.",
            ephemeral=True,
        )

    # ---------------------- GANADOR ----------------------
    @test_group.command(
        name="ganador",
        description="Muestra una vista previa privada del anuncio de un ganador",
    )
    @app_commands.describe(
        nombre_evento="Nombre del evento para el mensaje de prueba",
        imagen_fondo="Imagen de fondo que quieres probar",
        ganador="Usuario cuyo avatar aparecerá en la imagen",
        nombre_equipo="Nombre del equipo que aparecerá sobre el banner",
    )
    @es_organizador()
    async def ganador(
        self,
        interaction: discord.Interaction,
        nombre_evento: app_commands.Range[str, 1, 100],
        imagen_fondo: discord.Attachment,
        ganador: discord.Member = None,
        nombre_equipo: app_commands.Range[str, 1, 100] = None,
    ):
        if ganador is None and nombre_equipo is None:
            await interaction.response.send_message(
                "❌ Selecciona `ganador` o escribe `nombre_equipo`.", ephemeral=True
            )
            return
        if ganador is not None and nombre_equipo is not None:
            await interaction.response.send_message(
                "❌ Usa solo una opción: `ganador` o `nombre_equipo`.", ephemeral=True
            )
            return
        error_imagen = validar_imagen_fondo(imagen_fondo)
        if error_imagen:
            await interaction.response.send_message(error_imagen, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        nombre_ganador = ganador.mention if ganador else nombre_equipo.strip()
        try:
            fondo_data = await imagen_fondo.read()
            banner = await crear_banner_ganador(
                fondo_data,
                ganador,
                nombre_equipo=nombre_ganador if ganador is None else None,
            )
        except ERRORES_IMAGEN:
            logger.exception("No se pudo generar la vista previa del banner ganador")
            await interaction.followup.send(
                "❌ No pude procesar esa imagen. Prueba con un archivo PNG, JPG o WebP válido.",
                ephemeral=True,
            )
            return

        anuncio = _construir_anuncio_ganador(nombre_evento, nombre_ganador)
        await interaction.followup.send(content=anuncio, file=banner, ephemeral=True)

    # ---------------------- BIENVENIDA ----------------------
    @test_group.command(
        name="bienvenida",
        description="Genera una vista previa privada de la bienvenida",
    )
    @es_administrador()
    async def bienvenida(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            card = await crear_tarjeta(interaction.user)
        except (discord.HTTPException, OSError):
            await interaction.followup.send(
                "No pude generar la tarjeta. Revisa la imagen configurada en "
                "`WELCOME_BACKGROUND`.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            content="Vista previa de la bienvenida:",
            file=card,
            ephemeral=True,
        )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        mensaje = mensaje_error_permiso(error)
        if mensaje is None:
            raise error
        if interaction.response.is_done():
            await interaction.followup.send(mensaje, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Pruebas(bot))
