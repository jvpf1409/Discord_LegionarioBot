"""
Componentes de UI para las raids: selección de clase/especialización en
cascada (dos selects encadenados, ya que Discord no permite responder un
select con un modal pero sí con otro mensaje/select) y botón para darse de baja.
"""

import discord

from utils import storage
from utils.wow_data import CLASES, etiqueta_rol, icono_clase, icono_especializacion, rol_de


def construir_embed_raid(raid: dict) -> discord.Embed:
    color = {
        "abierto": discord.Color.green(),
        "cerrado": discord.Color.orange(),
        "cancelado": discord.Color.dark_grey(),
    }.get(raid["estado"], discord.Color.blurple())

    embed = discord.Embed(
        title=f"🐉 {raid['titulo']}",
        description=raid["descripcion"],
        color=color,
    )

    ts = raid.get("fecha_hora_ts")
    if ts:
        embed.add_field(name="📅 Fecha", value=f"<t:{ts}:D>", inline=True)
        embed.add_field(name="🕐 Hora", value=f"<t:{ts}:t>", inline=True)
        embed.add_field(name="⏳ Faltan", value=f"<t:{ts}:R>", inline=True)

    estado_txt = {
        "abierto": "Abierto",
        "cerrado": "Cerrado",
        "cancelado": "Cancelado",
    }[raid["estado"]]
    embed.add_field(name="Inscripciones", value=estado_txt, inline=True)
    embed.add_field(name="Inscritos", value=str(len(raid["inscritos"])), inline=True)

    conteos = {"tank": 0, "healer": 0, "melee": 0, "ranged": 0}
    for i in raid["inscritos"]:
        conteos[i["rol"]] = conteos.get(i["rol"], 0) + 1
    resumen_roles = "  ".join(f"{etiqueta_rol(r)}: {conteos[r]}" for r in ("tank", "healer", "melee", "ranged"))
    embed.add_field(name="Roles", value=resumen_roles, inline=False)

    def _linea_integrante(i: dict) -> str:
        icono_spec = icono_especializacion(i["clase"], i["especializacion"])
        icono_mostrado = icono_spec or icono_clase(i["clase"]) or "▫️"
        return (
            f"• {icono_mostrado} {i['clase']} "
            f"{i['especializacion']} - {i['nombre_discord']}"
        )

    for rol in ("tank", "healer", "melee", "ranged"):
        integrantes = [i for i in raid["inscritos"] if i["rol"] == rol]
        if integrantes:
            lista = "\n".join(_linea_integrante(i) for i in integrantes)
            if len(lista) > 1000:
                lista = lista[:1000] + "\n… (lista truncada)"
            embed.add_field(name=etiqueta_rol(rol), value=lista, inline=True)

    if raid.get("imagen_url"):
        embed.set_image(url=raid["imagen_url"])

    #embed.set_footer(text=f"ID de la raid: {raid['id']}")
    return embed


async def _actualizar_mensaje_raid(client: discord.Client, raid: dict):
    try:
        canal = client.get_channel(raid["canal_id"])
        mensaje = await canal.fetch_message(raid["mensaje_id"])
        await mensaje.edit(embed=construir_embed_raid(raid))
    except Exception:
        pass


async def _anunciar_inscripcion_raid(client: discord.Client, raid: dict, texto: str):
    canal_id = raid.get("canal_inscripciones_id")
    if not canal_id:
        return
    try:
        canal = client.get_channel(canal_id)
        if canal:
            await canal.send(texto)
    except Exception:
        pass


class EspecialidadSelect(discord.ui.Select):
    def __init__(self, raid_id: str, clase: str):
        opciones = [
            discord.SelectOption(
                label=especializacion,
                value=especializacion,
                emoji=icono_especializacion(clase, especializacion) or None,
            )
            for especializacion, _rol in CLASES[clase]
        ]
        super().__init__(placeholder="Selecciona tu especialización", options=opciones)
        self.raid_id = raid_id
        self.clase = clase

    async def callback(self, interaction: discord.Interaction):
        especializacion = self.values[0]
        rol = rol_de(self.clase, especializacion)
        inscrito = {
            "user_id": interaction.user.id,
            "nombre_discord": interaction.user.display_name,
            "clase": self.clase,
            "especializacion": especializacion,
            "rol": rol,
        }
        ok, mensaje = storage.inscribir_en_raid(self.raid_id, inscrito)
        await interaction.response.edit_message(content=("✅ " if ok else "❌ ") + mensaje, view=None)

        if ok:
            raid = storage.obtener_raid(self.raid_id)
            await _actualizar_mensaje_raid(interaction.client, raid)
            await _anunciar_inscripcion_raid(
                interaction.client,
                raid,
                f"📋 **{interaction.user.display_name}** se inscribió a **{raid['titulo']}** "
                f"como {self.clase} ({especializacion}).",
            )


class EspecialidadView(discord.ui.View):
    def __init__(self, raid_id: str, clase: str):
        super().__init__(timeout=120)
        self.add_item(EspecialidadSelect(raid_id, clase))


class ClaseSelect(discord.ui.Select):
    def __init__(self, raid_id: str):
        opciones = [
            discord.SelectOption(
                label=clase,
                value=clase,
                emoji=icono_clase(clase) or None,
            )
            for clase in CLASES
        ]
        super().__init__(
            placeholder="Selecciona tu clase",
            options=opciones,
            custom_id=f"wow_raid:clase:{raid_id}",
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        raid = storage.obtener_raid(self.raid_id)
        if raid is None or raid["estado"] != "abierto":
            await interaction.response.send_message(
                "❌ Las inscripciones ya no están disponibles para esta raid.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Elige tu especialización de **{self.values[0]}**:",
            view=EspecialidadView(self.raid_id, self.values[0]),
            ephemeral=True,
        )


class RaidView(discord.ui.View):
    """Vista persistente asociada a una raid concreta (custom_id incluye el id)."""

    def __init__(self, raid_id: str, abierta: bool):
        super().__init__(timeout=None)
        self.raid_id = raid_id

        select = ClaseSelect(raid_id)
        if not abierta:
            select.disabled = True
            select.placeholder = "Inscripciones cerradas"
        self.add_item(select)

        boton_baja = discord.ui.Button(
            label="Darme de baja",
            style=discord.ButtonStyle.danger,
            emoji="🚪",
            disabled=not abierta,
            custom_id=f"wow_raid:baja:{raid_id}",
        )
        boton_baja.callback = self._darse_de_baja
        self.add_item(boton_baja)

    async def _darse_de_baja(self, interaction: discord.Interaction):
        raid = storage.obtener_raid(self.raid_id)
        if raid is None or raid["estado"] != "abierto":
            await interaction.response.send_message(
                "❌ Ya no puedes darte de baja de esta raid.", ephemeral=True
            )
            return
        quitado = storage.quitar_de_raid(self.raid_id, interaction.user.id)
        if quitado:
            raid = storage.obtener_raid(self.raid_id)
            await _actualizar_mensaje_raid(interaction.client, raid)
            await interaction.response.send_message("✅ Te has dado de baja de la raid.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No estabas inscrito en esta raid.", ephemeral=True)
