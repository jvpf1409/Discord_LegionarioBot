"""Generación de la imagen anunciando al ganador de un evento."""

from __future__ import annotations

import asyncio
import io
import textwrap
from pathlib import Path

import discord
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent.parent
TAMANO_MAXIMO_FONDO = 10 * 1024 * 1024
# Errores posibles al descargar o decodificar la imagen de fondo subida.
ERRORES_IMAGEN = (discord.HTTPException, OSError, ValueError, Image.DecompressionBombError)


def validar_imagen_fondo(adjunto: discord.Attachment) -> str | None:
    """Devuelve el mensaje de error para el usuario, o ``None`` si es válida."""
    if not (adjunto.content_type or "").startswith("image/"):
        return "❌ `imagen_fondo` debe ser un archivo de imagen."
    if adjunto.size > TAMANO_MAXIMO_FONDO:
        return "❌ La imagen de fondo no puede superar los 10 MB."
    return None


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        ROOT / "assets/fonts/winner.ttf",
        ROOT / "assets/fonts/winner.otf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _fit_multiline(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int
) -> tuple[str, ImageFont.ImageFont]:
    """Reduce la fuente y divide el título hasta que quepa en el banner."""
    for size in range(start, 21, -2):
        font = _font(size)
        approximate_chars = max(12, int(max_width / (size * 0.58)))
        wrapped = "\n".join(textwrap.wrap(text, width=approximate_chars))
        box = draw.multiline_textbbox(
            (0, 0), wrapped, font=font, spacing=6, stroke_width=3, align="center"
        )
        if box[2] - box[0] <= max_width and box[3] - box[1] <= 125:
            return wrapped, font
    return text, _font(20)


def renderizar_banner_ganador(
    fondo_data: bytes,
    avatar_data: bytes | None = None,
    nombre_equipo: str | None = None,
) -> io.BytesIO:
    """
    Renderiza el banner sobre ``fondo_data``: el avatar del ganador individual
    o, si se omite, el nombre del equipo ganador.
    """
    with Image.open(io.BytesIO(fondo_data)) as source:
        canvas = ImageOps.fit(source.convert("RGB"), (900, 500))

    # Oscurece ligeramente el fondo para mantener legible el anuncio.
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 72))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)

    avatar_size = 174
    avatar_position = (360, 32)
    if avatar_data:
        with Image.open(io.BytesIO(avatar_data)) as source:
            avatar = ImageOps.fit(source.convert("RGB"), (avatar_size, avatar_size))
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
        border = Image.new("RGBA", (avatar_size + 12, avatar_size + 12), (0, 0, 0, 0))
        ImageDraw.Draw(border).ellipse((0, 0, avatar_size + 11, avatar_size + 11), fill="#f6c344")
        border.paste(avatar, (6, 6), mask)
        canvas.alpha_composite(border, (avatar_position[0] - 6, avatar_position[1] - 6))
    elif nombre_equipo:
        texto_equipo, fuente_equipo = _fit_multiline(draw, nombre_equipo, 700, 70)
        draw.multiline_text(
            (450, 119),
            texto_equipo,
            font=fuente_equipo,
            fill="#f6c344",
            anchor="mm",
            align="center",
            spacing=6,
            stroke_width=2,
            stroke_fill="#101010",
        )

    output = io.BytesIO()
    canvas.convert("RGB").save(output, "PNG", optimize=True)
    output.seek(0)
    return output


async def crear_banner_ganador(
    fondo_data: bytes,
    miembro: discord.abc.User | None = None,
    nombre_equipo: str | None = None,
) -> discord.File:
    avatar_data = None
    if miembro is not None:
        avatar_data = await miembro.display_avatar.with_size(256).read()
    # Pillow es síncrono: se renderiza en otro hilo para no congelar al bot.
    output = await asyncio.to_thread(
        renderizar_banner_ganador, fondo_data, avatar_data, nombre_equipo
    )
    return discord.File(output, filename="ganador-evento.png")
