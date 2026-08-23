"""Tarjeta de bienvenida y registro guiado para nuevos miembros."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
CANAL_ID = int(os.getenv("CANAL_BIENVENIDA_ID", "0") or 0)
CANAL_REGISTRO_ID = int(os.getenv("CANAL_REGISTRO_ID", "0") or 0)
ROL_INVITADO_ID = int(os.getenv("ROL_INVITADO_ID", "0") or 0)
ROL_LEGIONARIO_ID = int(os.getenv("ROL_LEGIONARIO_ID", "0") or 0)
ROL_RAID_ID = int(os.getenv("ROL_RAID_ID", "0") or 0)
SERVER_NAME = os.getenv("WELCOME_SERVER_NAME", "Legionarios de la Furia")
BACKGROUND = Path(os.getenv("WELCOME_BACKGROUND", "assets/welcome_background.png"))
if not BACKGROUND.is_absolute():
    BACKGROUND = ROOT / BACKGROUND
NORMAS_PATH = Path(os.getenv("NORMAS_REGISTRO_PATH", "assets/normas_registro.txt"))
if not NORMAS_PATH.is_absolute():
    NORMAS_PATH = ROOT / NORMAS_PATH


def cargar_paginas_normas() -> list[str]:
    try:
        contenido = NORMAS_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        contenido = "Lee y respeta las normas de la comunidad antes de continuar."

    def dividir_por_longitud(texto: str, limite: int) -> list[str]:
        paginas: list[str] = []
        pagina_actual = ""
        for parrafo in texto.split("\n\n"):
            candidato = f"{pagina_actual}\n\n{parrafo}".strip()
            if pagina_actual and len(candidato) > limite:
                paginas.append(pagina_actual)
                pagina_actual = parrafo
            else:
                pagina_actual = candidato
        if pagina_actual:
            paginas.append(pagina_actual)
        return paginas

    # Una línea que contenga solamente --- fuerza un salto de página.
    secciones = [
        seccion.strip()
        for seccion in re.split(r"(?m)^\s*---\s*$", contenido)
        if seccion.strip()
    ]
    if len(secciones) > 1:
        paginas: list[str] = []
        for seccion in secciones:
            # Evita superar el límite de 4096 caracteres de un embed.
            paginas.extend(dividir_por_longitud(seccion, 3900))
        return paginas

    # Mantiene tu límite automático de 700 cuando no hay separadores.
    return dividir_por_longitud(contenido, 700) or ["No hay normas configuradas."]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int) -> ImageFont.ImageFont:
    size = start
    while size > 20:
        font = _font(size)
        if draw.textbbox((0, 0), text, font=font, stroke_width=2)[2] <= max_width:
            return font
        size -= 2
    return _font(20)


async def crear_tarjeta(member: discord.Member) -> discord.File:
    if BACKGROUND.exists():
        with Image.open(BACKGROUND) as source:
            canvas = ImageOps.fit(source.convert("RGB"), (900, 500))
    else:
        canvas = Image.new("RGB", (900, 500), "#17385f")

    avatar_data = await member.display_avatar.with_size(256).read()
    with Image.open(io.BytesIO(avatar_data)) as source:
        # Medidas ajustadas al círculo interior del marco del fondo (900x500).
        avatar_size = 158
        avatar = ImageOps.fit(source.convert("RGB"), (avatar_size, avatar_size))

    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)

    # Borde desactivado temporalmente para probar el avatar sin contorno.
    # border = Image.new("RGBA", (210, 210), (0, 0, 0, 0))
    # ImageDraw.Draw(border).ellipse((0, 0, 209, 209), fill="#2537ef")
    # border.paste(avatar, (10, 10), mask)
    # canvas.paste(border, (345, 28), border)

    # Centro aproximado del marco impreso en el fondo: (450, 121).
    canvas.paste(avatar, (368, 41), mask)

    draw = ImageDraw.Draw(canvas)
    name = member.display_name
    line1 = f"¡Bienvenido {name}!"
    line2 = f"a {SERVER_NAME}"
    color, outline = "white", "#101010"
    draw.text((40, 280), line1, font=_fit_text(draw, line1, 820, 48), fill=color,
              stroke_width=4, stroke_fill=outline)
    draw.text((40, 338), line2, font=_fit_text(draw, line2, 820, 44), fill=color,
              stroke_width=4, stroke_fill=outline)
    draw.text((40, 420), "¡Completa tu registro para comenzar!", font=_font(32), fill=color,
              stroke_width=3, stroke_fill=outline)

    output = io.BytesIO()
    canvas.save(output, "PNG", optimize=True)
    output.seek(0)
    return discord.File(output, filename="bienvenida.png")


async def _asignar_rol(
    interaction: discord.Interaction,
    role_id: int,
    label: str,
) -> None:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Este registro solo funciona dentro del servidor.", ephemeral=True)
        return
    role = interaction.guild.get_role(role_id)
    if role is None:
        await interaction.response.send_message(
            f"No pude encontrar el rol **{label}**. Avísale a un administrador.",
            ephemeral=True,
        )
        return
    configured = [interaction.guild.get_role(rid) for rid in (ROL_INVITADO_ID, ROL_LEGIONARIO_ID, ROL_RAID_ID)]
    try:
        roles_to_remove = [r for r in configured if r and r != role]
        if roles_to_remove:
            await interaction.user.remove_roles(*roles_to_remove, reason="Actualización de registro")
        await interaction.user.add_roles(role, reason="Formulario de bienvenida")
    except discord.Forbidden:
        await interaction.response.send_message(
            "No pude asignar el rol. El rol del bot debe estar por encima de los roles de registro.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"Registro completado. Se te asignó el rol **{role.name}**.",
        ephemeral=True,
    )


class RegistroInicialView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Leer Reglas", style=discord.ButtonStyle.primary,
                       emoji="📖", custom_id="bienvenida:registro")
    async def registro(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        paginas = cargar_paginas_normas()
        view = NormasPaginadasView(interaction.user.id, paginas)
        await interaction.response.send_message(
            embed=view.crear_embed(),
            view=view,
            ephemeral=True,
        )


class NormasPaginadasView(discord.ui.View):
    def __init__(self, usuario_id: int, paginas: list[str]) -> None:
        super().__init__(timeout=600)
        self.usuario_id = usuario_id
        self.paginas = paginas
        self.indice = 0
        self._actualizar_botones()

    def crear_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="",
            description=self.paginas[self.indice],
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text=f"Página {self.indice + 1} de {len(self.paginas)}")
        return embed

    def _actualizar_botones(self) -> None:
        self.anterior.disabled = self.indice == 0
        ultima = self.indice == len(self.paginas) - 1

        if ultima:
            if self.siguiente in self.children:
                self.remove_item(self.siguiente)
            if self.comenzar not in self.children:
                self.add_item(self.comenzar)
        else:
            if self.comenzar in self.children:
                self.remove_item(self.comenzar)
            if self.siguiente not in self.children:
                self.add_item(self.siguiente)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.usuario_id:
            return True
        await interaction.response.send_message("Estas normas pertenecen a otra sesión.", ephemeral=True)
        return False

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def anterior(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.indice = max(0, self.indice - 1)
        self._actualizar_botones()
        await interaction.response.edit_message(embed=self.crear_embed(), view=self)

    @discord.ui.button(label="Siguiente", style=discord.ButtonStyle.primary, emoji="➡️")
    async def siguiente(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.indice = min(len(self.paginas) - 1, self.indice + 1)
        self._actualizar_botones()
        await interaction.response.edit_message(embed=self.crear_embed(), view=self)

    @discord.ui.button(label="Comenzar registro", style=discord.ButtonStyle.success, emoji="📝")
    async def comenzar(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(RegistroModal())


class RegistroModal(discord.ui.Modal, title="Formulario de registro"):
    juega_wow = discord.ui.Label(
        text="¿Juegas World of Warcraft?",
        description="Si respondes No, no importan las siguientes respuestas.",
        component=discord.ui.RadioGroup(
            custom_id="registro:juega_wow",
            options=[
                discord.RadioGroupOption(label="Sí", value="si"),
                discord.RadioGroupOption(label="No", value="no"),
            ],
        ),
    )
    hermandad = discord.ui.Label(
        text="¿Perteneces a la hermandad?",
        description="Legionarios de la Furia; debes tener al menos un personaje dentro.",
        component=discord.ui.RadioGroup(
            custom_id="registro:hermandad",
            options=[
                discord.RadioGroupOption(label="Sí", value="si"),
                discord.RadioGroupOption(label="No", value="no"),
            ],
        ),
    )
    raid = discord.ui.Label(
        text="¿Participaras en las Raid?",
        description="Si vienes solo para eso, responde Si.",
        component=discord.ui.RadioGroup(
            custom_id="registro:raid",
            options=[
                discord.RadioGroupOption(label="Sí", value="si"),
                discord.RadioGroupOption(label="No", value="no"),
            ],
        ),
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        juega_wow = self.juega_wow.component.value == "si"
        es_hermandad = self.hermandad.component.value == "si"
        juega_raid = self.raid.component.value == "si"

        # La prioridad impide que combinaciones contradictorias concedan acceso.
        if not juega_wow:
            await _asignar_rol(interaction, ROL_INVITADO_ID, "Invitado")
        elif es_hermandad:
            await _asignar_rol(interaction, ROL_LEGIONARIO_ID, "Legionario")
        elif juega_raid:
            await _asignar_rol(interaction, ROL_RAID_ID, "Raid")
        else:
            await _asignar_rol(interaction, ROL_INVITADO_ID, "Invitado")


class Bienvenida(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="probar_bienvenida",
        description="Genera una vista previa privada de la bienvenida.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def probar_bienvenida(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este comando solo funciona dentro del servidor.",
                ephemeral=True,
            )
            return

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

    @app_commands.command(
        name="publicar_registro",
        description="Publica el panel permanente de registro en el canal configurado.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def publicar_registro(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not CANAL_REGISTRO_ID:
            await interaction.response.send_message(
                "Configura `CANAL_REGISTRO_ID` en el archivo `.env`.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(CANAL_REGISTRO_ID)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "No encontré un canal de texto con el ID configurado en `CANAL_REGISTRO_ID`.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Legionarios de la Furia",
            description=(
                "Antes de acceder al servidor debes leer todas las reglas de la comunidad.\n"
                "Pulsa **Leer reglas** para comenzar.\n\n"
                "**UN FORMULARIO OBLIGATORIO APARECERA AL TERMINAR**"
            ),
            color=discord.Color.dark_red(),
        )
        try:
            message = await channel.send(embed=embed, view=RegistroInicialView())
        except discord.Forbidden:
            await interaction.response.send_message(
                "No tengo permisos para enviar mensajes en el canal de registro.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Panel publicado correctamente: {message.jump_url}",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot or not CANAL_ID:
            return
        channel = member.guild.get_channel(CANAL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            card = await crear_tarjeta(member)
            await channel.send(content=member.mention, file=card)
        except (discord.HTTPException, OSError):
            await channel.send(
                content=f"¡Bienvenido/a {member.mention} a **{SERVER_NAME}**!",
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bienvenida(bot))
