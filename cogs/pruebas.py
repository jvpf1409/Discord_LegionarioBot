"""
Cog con los comandos de prueba (/test ...): generan vistas previas privadas
sin publicar nada ni modificar datos.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.bienvenida import crear_tarjeta
from cogs.eventos import _construir_anuncio_ganador
from utils.banner_ganador import ERRORES_IMAGEN, crear_banner_ganador, validar_imagen_fondo
from utils.permisos import es_administrador, es_organizador, mensaje_error_permiso

logger = logging.getLogger(__name__)


class Pruebas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    test_group = app_commands.Group(
        name="test",
        description="Vistas previas privadas para probar funciones del bot",
        guild_only=True,
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
