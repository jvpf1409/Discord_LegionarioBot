"""Formulario de interés PvP y estadísticas de sus respuestas."""

from collections import Counter
import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.permisos import ROL_OFICIAL, es_organizador
from utils.wow_data import CLASES, icono_clase, icono_especializacion, rol_de

logger = logging.getLogger(__name__)
NIVELES = ("Principiante", "Intermedio", "Experto")


def construir_embed_formulario(formulario: dict) -> discord.Embed:
    abierto = formulario["estado"] == "abierto"
    embed = discord.Embed(
        title=f"⚔️ {formulario['titulo']}",
        description=formulario["descripcion"],
        color=discord.Color.green() if abierto else discord.Color.orange(),
    )
    embed.add_field(name="Estado", value="Abierto" if abierto else "Cerrado", inline=True)
    respuestas = formulario["respuestas"]
    personas = len({r["user_id"] for r in respuestas})
    embed.add_field(name="Personas inscritas", value=str(personas), inline=True)
    embed.add_field(name="Personajes inscritos", value=str(len(respuestas)), inline=True)
    embed.add_field(
        name="¿Cómo participar?",
        value="Pulsa **Inscribir personaje**, escribe su nombre y elige su clase, especialización y nivel de conocimiento en PvP.",
        inline=False,
    )
    embed.set_footer(text=f"Formulario PvP #{formulario['id']} · Máximo 2 personajes por persona")
    return embed


async def actualizar_mensaje(client: discord.Client, formulario: dict):
    try:
        canal = client.get_channel(formulario["canal_id"]) or await client.fetch_channel(formulario["canal_id"])
        mensaje = await canal.fetch_message(formulario["mensaje_id"])
        await mensaje.edit(embed=construir_embed_formulario(formulario))
    except (discord.HTTPException, AttributeError):
        logger.warning("No se pudo actualizar el mensaje del formulario PvP %s", formulario["id"])


class NivelSelect(discord.ui.Select):
    def __init__(self, formulario_id: str, personaje: str, clase: str, especializacion: str):
        super().__init__(
            placeholder="Selecciona tu nivel de conocimiento en PvP",
            options=[discord.SelectOption(label=nivel, value=nivel) for nivel in NIVELES],
        )
        self.formulario_id = formulario_id
        self.personaje = personaje
        self.clase = clase
        self.especializacion = especializacion

    async def callback(self, interaction: discord.Interaction):
        rol = rol_de(self.clase, self.especializacion)
        respuesta = {
            "user_id": interaction.user.id,
            "nombre_discord": interaction.user.display_name,
            "personaje": self.personaje,
            "clase": self.clase,
            "especializacion": self.especializacion,
            "rol": rol,
            "nivel": self.values[0],
        }
        ok, mensaje = storage.responder_formulario(self.formulario_id, respuesta)
        await interaction.response.edit_message(content=("✅ " if ok else "❌ ") + mensaje, view=None)
        if ok:
            await actualizar_mensaje(interaction.client, storage.obtener_formulario(self.formulario_id))


class NivelView(discord.ui.View):
    def __init__(self, formulario_id: str, personaje: str, clase: str, especializacion: str):
        super().__init__(timeout=120)
        self.add_item(NivelSelect(formulario_id, personaje, clase, especializacion))


class EspecializacionSelect(discord.ui.Select):
    def __init__(self, formulario_id: str, personaje: str, clase: str):
        super().__init__(
            placeholder="Selecciona tu especialización",
            options=[
                discord.SelectOption(label=spec, value=spec, emoji=icono_especializacion(clase, spec) or None)
                for spec, _ in CLASES[clase]
            ],
        )
        self.formulario_id = formulario_id
        self.personaje = personaje
        self.clase = clase

    async def callback(self, interaction: discord.Interaction):
        spec = self.values[0]
        await interaction.response.edit_message(
            content=f"Por último, indica tu nivel de conocimiento en PvP con **{self.clase} {spec}**:",
            view=NivelView(self.formulario_id, self.personaje, self.clase, spec),
        )


class EspecializacionView(discord.ui.View):
    def __init__(self, formulario_id: str, personaje: str, clase: str):
        super().__init__(timeout=120)
        self.add_item(EspecializacionSelect(formulario_id, personaje, clase))


class ClaseSelect(discord.ui.Select):
    def __init__(self, formulario_id: str, personaje: str):
        super().__init__(
            placeholder="Selecciona tu clase",
            options=[discord.SelectOption(label=c, value=c, emoji=icono_clase(c) or None) for c in CLASES],
        )
        self.formulario_id = formulario_id
        self.personaje = personaje

    async def callback(self, interaction: discord.Interaction):
        clase = self.values[0]
        await interaction.response.edit_message(
            content=f"Ahora elige tu especialización de **{clase}**:",
            view=EspecializacionView(self.formulario_id, self.personaje, clase),
        )


class ClaseView(discord.ui.View):
    def __init__(self, formulario_id: str, personaje: str):
        super().__init__(timeout=120)
        self.add_item(ClaseSelect(formulario_id, personaje))


class PersonajeModal(discord.ui.Modal, title="Inscribir personaje en PvP"):
    personaje = discord.ui.TextInput(
        label="Nombre del personaje",
        placeholder="Ej: Thrall",
        min_length=2,
        max_length=30,
    )

    def __init__(self, formulario_id: str):
        super().__init__()
        self.formulario_id = formulario_id

    async def on_submit(self, interaction: discord.Interaction):
        nombre = self.personaje.value.strip()
        await interaction.response.send_message(
            f"Inscribiendo a **{nombre}**. Ahora elige su clase:",
            view=ClaseView(self.formulario_id, nombre),
            ephemeral=True,
        )


class BajaPersonajeSelect(discord.ui.Select):
    def __init__(self, formulario_id: str, respuestas: list[dict]):
        opciones = [
            discord.SelectOption(
                label=r.get("personaje") or "Personaje sin nombre (inscripción antigua)",
                description=f"{r['clase']} {r['especializacion']}",
                value=r.get("personaje") or "__inscripcion_antigua__",
            )
            for r in respuestas[:25]
        ]
        super().__init__(placeholder="Elige el personaje que quieres retirar", options=opciones)
        self.formulario_id = formulario_id

    async def callback(self, interaction: discord.Interaction):
        personaje = "" if self.values[0] == "__inscripcion_antigua__" else self.values[0]
        quitada = storage.quitar_respuesta_formulario(self.formulario_id, interaction.user.id, personaje)
        await interaction.response.edit_message(
            content="✅ Personaje retirado del formulario." if quitada else "❌ No se encontró esa inscripción.",
            view=None,
        )
        if quitada:
            await actualizar_mensaje(interaction.client, storage.obtener_formulario(self.formulario_id))


class BajaPersonajeView(discord.ui.View):
    def __init__(self, formulario_id: str, respuestas: list[dict]):
        super().__init__(timeout=120)
        self.add_item(BajaPersonajeSelect(formulario_id, respuestas))


class EditarPersonajeSelect(discord.ui.Select):
    def __init__(self, formulario_id: str, respuestas: list[dict]):
        opciones = [
            discord.SelectOption(
                label=r.get("personaje") or "Personaje sin nombre (inscripción antigua)",
                description=f"{r['clase']} {r['especializacion']}",
                value=r.get("personaje") or "__inscripcion_antigua__",
            )
            for r in respuestas
        ]
        super().__init__(placeholder="Elige un personaje para actualizar", options=opciones)
        self.formulario_id = formulario_id

    async def callback(self, interaction: discord.Interaction):
        personaje = "" if self.values[0] == "__inscripcion_antigua__" else self.values[0]
        nombre_mostrado = personaje or "personaje sin nombre"
        await interaction.response.edit_message(
            content=f"Actualizando a **{nombre_mostrado}**. Elige su clase:",
            view=ClaseView(self.formulario_id, personaje),
        )


class EditarPersonajeView(discord.ui.View):
    def __init__(self, formulario_id: str, respuestas: list[dict]):
        super().__init__(timeout=120)
        self.add_item(EditarPersonajeSelect(formulario_id, respuestas))


class PvpView(discord.ui.View):
    def __init__(self, formulario_id: str, abierto: bool = True):
        super().__init__(timeout=None)
        self.formulario_id = formulario_id
        inscribir = discord.ui.Button(
            label="Inscribir personaje", emoji="📝", style=discord.ButtonStyle.success,
            custom_id=f"wow_pvp:inscribir:{formulario_id}", disabled=not abierto,
        )
        inscribir.callback = self.inscribir
        self.add_item(inscribir)
        baja = discord.ui.Button(
            label="Retirar personaje", emoji="🚪", style=discord.ButtonStyle.danger,
            custom_id=f"wow_pvp:baja:{formulario_id}", disabled=not abierto,
        )
        baja.callback = self.baja
        self.add_item(baja)

    async def inscribir(self, interaction: discord.Interaction):
        formulario = storage.obtener_formulario(self.formulario_id)
        if formulario is None or formulario["estado"] != "abierto":
            await interaction.response.send_message("❌ Este formulario ya no acepta respuestas.", ephemeral=True)
            return
        respuestas = [
            r for r in formulario.get("respuestas", []) if r["user_id"] == interaction.user.id
        ]
        if len(respuestas) >= 2:
            await interaction.response.send_message(
                "⚠️ Ya alcanzaste el máximo de **2 personajes**. "
                "Puedes elegir uno para actualizarlo o usar **Retirar personaje**.",
                view=EditarPersonajeView(self.formulario_id, respuestas),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(PersonajeModal(self.formulario_id))

    async def baja(self, interaction: discord.Interaction):
        formulario = storage.obtener_formulario(self.formulario_id)
        respuestas = [r for r in formulario.get("respuestas", []) if r["user_id"] == interaction.user.id]
        if not respuestas:
            await interaction.response.send_message("❌ No tienes personajes inscritos.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Selecciona el personaje que quieres retirar:",
            view=BajaPersonajeView(self.formulario_id, respuestas),
            ephemeral=True,
        )


def construir_estadisticas(formulario: dict) -> discord.Embed:
    respuestas = formulario["respuestas"]
    total_personas = len({r["user_id"] for r in respuestas})
    roles = Counter("dps" if r["rol"] in ("melee", "ranged") else r["rol"] for r in respuestas)
    clases = Counter(r["clase"] for r in respuestas)
    niveles = Counter(r["nivel"] for r in respuestas)
    specs = Counter(f"{r['clase']} — {r['especializacion']}" for r in respuestas)
    embed = discord.Embed(title=f"📊 Estadísticas · {formulario['titulo']}", color=discord.Color.blurple())
    embed.description = (
        f"**{total_personas}** personas inscritas · "
        f"**{len(respuestas)}** personajes inscritos."
    )
    embed.add_field(
        name="Roles",
        value=f"🛡️ Tank: **{roles['tank']}**\n➕ Healer: **{roles['healer']}**\n⚔️ DPS: **{roles['dps']}**",
        inline=True,
    )
    embed.add_field(
        name="Conocimiento PvP",
        value="\n".join(f"{n}: **{niveles[n]}**" for n in NIVELES),
        inline=True,
    )
    embed.add_field(
        name="Clases",
        value="\n".join(f"{clase}: **{cantidad}**" for clase, cantidad in clases.most_common()) or "Sin datos",
        inline=False,
    )
    lineas_specs = [f"{spec}: **{cantidad}**" for spec, cantidad in specs.most_common()]
    if not lineas_specs:
        embed.add_field(name="Especializaciones", value="Sin datos", inline=False)
    else:
        bloques, bloque = [], ""
        for linea in lineas_specs:
            candidato = f"{bloque}\n{linea}" if bloque else linea
            if len(candidato) > 1000:
                bloques.append(bloque)
                bloque = linea
            else:
                bloque = candidato
        bloques.append(bloque)
        for indice, contenido in enumerate(bloques):
            embed.add_field(
                name="Especializaciones" if indice == 0 else "Especializaciones (continuación)",
                value=contenido,
                inline=False,
            )

    embed.set_footer(text=f"Formulario PvP #{formulario['id']}")
    return embed


def construir_lista_inscritos(formulario: dict) -> list[discord.Embed]:
    respuestas = sorted(
        formulario["respuestas"],
        key=lambda r: (r["nombre_discord"].casefold(), r.get("personaje", "").casefold()),
    )
    if not respuestas:
        embed = discord.Embed(
            title=f"👥 Inscritos · {formulario['titulo']}",
            description="No hay personas inscritas.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Formulario PvP #{formulario['id']}")
        return [embed]

    lineas = [
        f"• **{r['nombre_discord']}** — {r.get('personaje') or '(sin nombre)'} · "
        f"{r['clase']} {r['especializacion']} · {r['nivel']}"
        for r in respuestas
    ]
    paginas, pagina = [], ""
    for linea in lineas:
        candidata = f"{pagina}\n{linea}" if pagina else linea
        if len(candidata) > 3800:
            paginas.append(pagina)
            pagina = linea
        else:
            pagina = candidata
    if pagina:
        paginas.append(pagina)

    total_personas = len({r["user_id"] for r in respuestas})
    embeds = []
    for indice, contenido in enumerate(paginas, start=1):
        embed = discord.Embed(
            title=f"👥 Inscritos · {formulario['titulo']}",
            description=contenido,
            color=discord.Color.blurple(),
        )
        embed.set_footer(
            text=(
                f"{total_personas} personas · {len(respuestas)} personajes · "
                f"Página {indice}/{len(paginas)} · Formulario #{formulario['id']}"
            )
        )
        embeds.append(embed)
    return embeds


class Formularios(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    formulario = app_commands.Group(name="form", description="Gestiona formularios de la comunidad")
    pvp = app_commands.Group(name="pvp", description="Formulario de interés en PvP", parent=formulario)

    @pvp.command(name="publicar", description="Publica un formulario de interés en PvP")
    @app_commands.describe(titulo="Título del formulario", descripcion="Texto introductorio")
    @es_organizador()
    async def publicar(self, interaction: discord.Interaction, titulo: str, descripcion: str):
        canal = interaction.channel
        if canal is None or not isinstance(canal, discord.abc.Messageable):
            await interaction.response.send_message(
                "❌ No puedo publicar el formulario en este canal.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        formulario_id = storage.crear_formulario_pvp(titulo, descripcion, interaction.guild_id, canal.id, interaction.user.id)
        formulario = storage.obtener_formulario(formulario_id)
        try:
            mensaje = await canal.send(embed=construir_embed_formulario(formulario), view=PvpView(formulario_id))
        except discord.Forbidden:
            storage.actualizar_formulario(formulario_id, estado="cerrado")
            await interaction.followup.send(f"❌ No tengo permiso para publicar en {canal.mention}.", ephemeral=True)
            return
        storage.actualizar_formulario(formulario_id, mensaje_id=mensaje.id)
        await interaction.followup.send(f"✅ Formulario publicado en este canal (ID: **{formulario_id}**).", ephemeral=True)

    @pvp.command(name="estadisticas", description="Muestra las estadísticas de un formulario PvP")
    @app_commands.describe(formulario_id="ID indicado al publicar el formulario")
    @es_organizador()
    async def estadisticas(self, interaction: discord.Interaction, formulario_id: str):
        formulario = storage.obtener_formulario(formulario_id)
        if formulario is None or formulario.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message("❌ No existe ese formulario en este servidor.", ephemeral=True)
            return
        await interaction.response.send_message(embed=construir_estadisticas(formulario))

    @pvp.command(name="inscritos", description="Muestra las personas y personajes inscritos en un formulario PvP")
    @app_commands.describe(formulario_id="ID indicado al publicar el formulario")
    @es_organizador()
    async def inscritos(self, interaction: discord.Interaction, formulario_id: str):
        formulario = storage.obtener_formulario(formulario_id)
        if formulario is None or formulario.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message(
                "❌ No existe ese formulario en este servidor.", ephemeral=True
            )
            return
        embeds = construir_lista_inscritos(formulario)
        await interaction.response.send_message(embeds=embeds[:10])
        for inicio in range(10, len(embeds), 10):
            await interaction.followup.send(embeds=embeds[inicio:inicio + 10])

    @pvp.command(name="cerrar", description="Cierra un formulario PvP")
    @app_commands.describe(formulario_id="ID indicado al publicar el formulario")
    @es_organizador()
    async def cerrar(self, interaction: discord.Interaction, formulario_id: str):
        formulario = storage.obtener_formulario(formulario_id)
        if formulario is None or formulario.get("guild_id") != interaction.guild_id:
            await interaction.response.send_message("❌ No existe ese formulario en este servidor.", ephemeral=True)
            return
        storage.actualizar_formulario(formulario_id, estado="cerrado")
        formulario = storage.obtener_formulario(formulario_id)
        try:
            canal = self.bot.get_channel(formulario["canal_id"]) or await self.bot.fetch_channel(formulario["canal_id"])
            mensaje = await canal.fetch_message(formulario["mensaje_id"])
            await mensaje.edit(embed=construir_embed_formulario(formulario), view=PvpView(formulario_id, abierto=False))
        except (discord.HTTPException, AttributeError):
            pass
        await interaction.response.send_message(f"🔒 Formulario cerrado con **{len(formulario['respuestas'])}** respuestas.")

    @publicar.error
    @estadisticas.error
    @inscritos.error
    @cerrar.error
    async def error_permisos(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        mensaje = f"🚫 Necesitas el rol **{ROL_OFICIAL}** para usar este comando."
        if not isinstance(error, app_commands.MissingRole):
            logger.exception("Error en un comando PvP", exc_info=getattr(error, "original", error))
            mensaje = "⚠️ Ocurrió un error al ejecutar el comando."
        if interaction.response.is_done():
            await interaction.followup.send(mensaje, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Formularios(bot))
