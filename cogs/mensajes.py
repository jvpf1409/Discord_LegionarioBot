"""Comando para publicar un mensaje mediante el bot en el canal actual."""

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from utils.permisos import ROL_OFICIAL, es_organizador


logger = logging.getLogger(__name__)


def convertir_menciones_de_roles(
    texto: str, guild: discord.Guild
) -> tuple[str, list[discord.Role]]:
    """Convierte menciones escritas como @Nombre del rol en menciones de Discord."""
    roles_mencionados: list[discord.Role] = []
    roles = sorted(
        (rol for rol in guild.roles if not rol.is_default()),
        key=lambda rol: len(rol.name),
        reverse=True,
    )

    for rol in roles:
        patron = re.compile(
            rf"(?<!\S)@{re.escape(rol.name)}(?=$|\s|[.,!?;:])",
            flags=re.IGNORECASE,
        )
        texto, cantidad = patron.subn(rol.mention, texto)
        if cantidad and rol not in roles_mencionados:
            roles_mencionados.append(rol)

    return texto, roles_mencionados


class MensajeModal(discord.ui.Modal, title="Publicar mensaje"):
    contenido = discord.ui.TextInput(
        label="Mensaje",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe aquí el mensaje que publicará el bot...",
        min_length=1,
        max_length=2000,
        required=True,
    )

    def __init__(self, canal: discord.abc.Messageable, *, usar_embed: bool):
        super().__init__(title="Publicar anuncio" if usar_embed else "Publicar mensaje")
        self.canal = canal
        self.usar_embed = usar_embed
        self.contenido.max_length = 4000 if usar_embed else 2000

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        mensaje, roles = convertir_menciones_de_roles(
            self.contenido.value.strip(), interaction.guild
        )

        limite = 4096 if self.usar_embed else 2000
        if len(mensaje) > limite:
            await interaction.followup.send(
                "❌ El mensaje es demasiado largo. Acórtalo un poco.", ephemeral=True
            )
            return

        permisos = self.canal.permissions_for(interaction.guild.me)
        no_mencionables = [rol for rol in roles if not rol.mentionable]
        if no_mencionables and not permisos.mention_everyone:
            nombres = ", ".join(f"@{rol.name}" for rol in no_mencionables)
            await interaction.followup.send(
                f"❌ No puedo mencionar estos roles: {nombres}. Hazlos mencionables o "
                "concédeme el permiso **Mencionar @everyone, @here y todos los roles**.",
                ephemeral=True,
            )
            return

        try:
            embed = None
            contenido = mensaje
            if self.usar_embed:
                embed = discord.Embed(
                    description=mensaje,
                    color=discord.Color.blurple(),
                )
                # Las menciones dentro de un embed no notifican, por eso se
                # incluyen también como contenido normal sobre el anuncio.
                contenido = " ".join(rol.mention for rol in roles) or None

            publicado = await self.canal.send(
                content=contenido,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    users=False,
                    roles=roles,
                    replied_user=False,
                ),
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ No tengo permiso para publicar en este canal.", ephemeral=True
            )
            return
        except discord.HTTPException:
            logger.exception("Discord rechazó la publicación del mensaje")
            await interaction.followup.send(
                "❌ Discord no pudo publicar el mensaje. Inténtalo de nuevo.", ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ Mensaje publicado: {publicado.jump_url}", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception("Error al publicar un mensaje", exc_info=error)
        aviso = "⚠️ Ocurrió un error inesperado al publicar el mensaje."
        if interaction.response.is_done():
            await interaction.followup.send(aviso, ephemeral=True)
        else:
            await interaction.response.send_message(aviso, ephemeral=True)


class Mensajes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="mensaje",
        description="Publica un mensaje como el bot en este canal",
    )
    @app_commands.guild_only()
    @es_organizador()
    async def mensaje(self, interaction: discord.Interaction):
        await self._abrir_modal(interaction, usar_embed=False)

    @app_commands.command(
        name="anuncio",
        description="Publica un anuncio embebido como el bot en este canal",
    )
    @app_commands.guild_only()
    @es_organizador()
    async def anuncio(self, interaction: discord.Interaction):
        await self._abrir_modal(interaction, usar_embed=True)

    async def _abrir_modal(
        self, interaction: discord.Interaction, *, usar_embed: bool
    ):
        canal = interaction.channel
        if canal is None or not hasattr(canal, "send") or not hasattr(canal, "permissions_for"):
            await interaction.response.send_message(
                "❌ Este comando solo se puede usar en un canal de texto.", ephemeral=True
            )
            return

        permisos = canal.permissions_for(interaction.guild.me)
        if not permisos.view_channel or not permisos.send_messages:
            await interaction.response.send_message(
                "❌ No tengo permiso para publicar en este canal.", ephemeral=True
            )
            return
        if usar_embed and not permisos.embed_links:
            await interaction.response.send_message(
                "❌ Necesito el permiso **Insertar enlaces** para publicar anuncios embebidos.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(MensajeModal(canal, usar_embed=usar_embed))

    @mensaje.error
    async def on_mensaje_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        await self._responder_error(interaction, error)

    @anuncio.error
    async def on_anuncio_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        await self._responder_error(interaction, error)

    async def _responder_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingRole):
            aviso = f"🚫 Necesitas el rol **{ROL_OFICIAL}** para usar este comando."
        else:
            original = getattr(error, "original", error)
            logger.exception("Error inesperado al preparar una publicación", exc_info=original)
            aviso = "⚠️ Ocurrió un error inesperado al preparar el mensaje."

        if interaction.response.is_done():
            await interaction.followup.send(aviso, ephemeral=True)
        else:
            await interaction.response.send_message(aviso, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mensajes(bot))
