"""Tarjeta de bienvenida y registro guiado para nuevos miembros."""

from __future__ import annotations

import io
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
CANAL_ID = int(os.getenv("CANAL_BIENVENIDA_ID", "0") or 0)
ROL_INVITADO_ID = int(os.getenv("ROL_INVITADO_ID", "0") or 0)
ROL_LEGIONARIO_ID = int(os.getenv("ROL_LEGIONARIO_ID", "0") or 0)
ROL_RAID_ID = int(os.getenv("ROL_RAID_ID", "0") or 0)
SERVER_NAME = os.getenv("WELCOME_SERVER_NAME", "Legionarios de la Furia")
BACKGROUND = Path(os.getenv("WELCOME_BACKGROUND", "assets/welcome_background.png"))
if not BACKGROUND.is_absolute():
    BACKGROUND = ROOT / BACKGROUND


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
        avatar = ImageOps.fit(source.convert("RGB"), (190, 190))

    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 189, 189), fill=255)
    border = Image.new("RGBA", (210, 210), (0, 0, 0, 0))
    ImageDraw.Draw(border).ellipse((0, 0, 209, 209), fill="#2537ef")
    border.paste(avatar, (10, 10), mask)
    canvas.paste(border, (345, 28), border)

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


async def _asignar_rol(interaction: discord.Interaction, role_id: int, label: str) -> None:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.edit_message(content="Este registro solo funciona dentro del servidor.", view=None)
        return
    role = interaction.guild.get_role(role_id)
    if role is None:
        await interaction.response.edit_message(
            content=f"No pude encontrar el rol **{label}**. Avísale a un administrador.", view=None
        )
        return
    configured = [interaction.guild.get_role(rid) for rid in (ROL_INVITADO_ID, ROL_LEGIONARIO_ID, ROL_RAID_ID)]
    try:
        roles_to_remove = [r for r in configured if r and r != role]
        if roles_to_remove:
            await interaction.user.remove_roles(*roles_to_remove, reason="Actualización de registro")
        await interaction.user.add_roles(role, reason="Formulario de bienvenida")
    except discord.Forbidden:
        await interaction.response.edit_message(
            content="No pude asignar el rol. El rol del bot debe estar por encima de los roles de registro.", view=None
        )
        return
    await interaction.response.edit_message(content=f"Registro completado. Se te asignó el rol **{role.name}**.", view=None)


class RegistroInicialView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Completar registro", style=discord.ButtonStyle.primary,
                       emoji="📝", custom_id="bienvenida:registro")
    async def registro(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_message("**1/3 · ¿Juegas World of Warcraft?**", view=JuegaWowView(), ephemeral=True)


class JuegaWowView(discord.ui.View):
    @discord.ui.button(label="Sí", style=discord.ButtonStyle.success)
    async def si(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="**2/3 · ¿Eres parte de la hermandad?**", view=HermandadView())

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await _asignar_rol(interaction, ROL_INVITADO_ID, "Invitado")


class HermandadView(discord.ui.View):
    @discord.ui.button(label="Sí", style=discord.ButtonStyle.success)
    async def si(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await _asignar_rol(interaction, ROL_LEGIONARIO_ID, "Legionario")

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="**3/3 · ¿Juegas Raid?**", view=RaidView())


class RaidView(discord.ui.View):
    @discord.ui.button(label="Sí", style=discord.ButtonStyle.success)
    async def si(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await _asignar_rol(interaction, ROL_RAID_ID, "Raid")

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await _asignar_rol(interaction, ROL_INVITADO_ID, "Invitado")


class Bienvenida(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot or not CANAL_ID:
            return
        channel = member.guild.get_channel(CANAL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            card = await crear_tarjeta(member)
            await channel.send(content=member.mention, file=card, view=RegistroInicialView())
        except (discord.HTTPException, OSError):
            await channel.send(
                content=f"¡Bienvenido/a {member.mention} a **{SERVER_NAME}**!",
                view=RegistroInicialView(),
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bienvenida(bot))
