"""
Componentes de UI: botones persistentes e inscripción (individual o por equipos).
"""

import discord
from utils import storage


def construir_embed_evento(evento: dict) -> discord.Embed:
    color = {
        "abierto": discord.Color.red(),
        "cerrado": discord.Color.orange(),
        "finalizado": discord.Color.dark_grey(),
    }.get(evento["estado"], discord.Color.blurple())

    embed = discord.Embed(
        title=f"⚔️ {evento['titulo']}",
        description=evento["descripcion"],
        color=color,
    )
    estado_txt = {
        "abierto": "✅ Inscripciones abiertas",
        "cerrado": "🟠 Inscripciones cerradas",
        "finalizado": "🎉 Finalizado",
    }[evento["estado"]]
    embed.add_field(name="Estado", value=estado_txt, inline=True)

    ts = evento.get("fecha_hora_ts")
    if ts:
        embed.add_field(name="📅 Fecha y hora", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=True)

    es_grupal = evento["tipo_inscripcion"] == "grupal"

    if es_grupal:
        embed.add_field(name="Tipo", value="👥 Grupal", inline=True)
        cupo = f"{len(evento['equipos'])}/{evento['num_equipos']}" if evento["num_equipos"] else str(len(evento["equipos"]))
        embed.add_field(name="Equipos", value=cupo, inline=True)

        for equipo in evento["equipos"]:
            lineas = "\n".join(f"• **{i['rol']}** — {i['personaje']}" for i in equipo["integrantes"])
            embed.add_field(
                name=f"🛡️ {equipo['nombre_equipo']} (por {equipo['nombre_discord']})",
                value=lineas,
                inline=True,
            )
    else:
        embed.add_field(name="Tipo", value="🙋 Individual", inline=True)
        embed.add_field(name="Equipos previstos", value=str(evento["num_equipos"]), inline=True)
        embed.add_field(name="Inscritos", value=str(len(evento["participantes"])), inline=True)

        if evento["participantes"]:
            lista = "\n".join(
                f"• **{p['personaje']}** — <@{p['user_id']}>" for p in evento["participantes"]
            )
            if len(lista) > 1000:
                lista = lista[:1000] + "\n… (lista truncada)"
            embed.add_field(name="Participantes", value=lista, inline=False)

    if evento["estado"] == "finalizado" and evento.get("ganador") is not None:
        embed.add_field(name="🏆 Ganador", value=str(evento["ganador"]), inline=False)

    if evento.get("imagen_url"):
        embed.set_image(url=evento["imagen_url"])

    embed.set_footer(text=f"ID del evento: {evento['id']}")
    return embed


async def _actualizar_mensaje_evento(client: discord.Client, evento: dict):
    try:
        canal = client.get_channel(evento["canal_id"])
        mensaje_original = await canal.fetch_message(evento["mensaje_id"])
        await mensaje_original.edit(embed=construir_embed_evento(evento))
    except Exception:
        pass


async def _anunciar_inscripcion(client: discord.Client, evento: dict, texto: str):
    canal_id = evento.get("canal_inscripciones_id")
    if not canal_id:
        return
    try:
        canal = client.get_channel(canal_id)
        if canal:
            await canal.send(texto)
    except Exception:
        pass


class InscripcionModal(discord.ui.Modal, title="Inscripción al evento"):
    """Formulario de inscripción individual: solo el nombre del personaje."""

    personaje = discord.ui.TextInput(
        label="Nombre del personaje",
        placeholder="Ej: Arkthar",
        max_length=32,
        required=True,
    )

    def __init__(self, evento_id: str):
        super().__init__()
        self.evento_id = evento_id

    async def on_submit(self, interaction: discord.Interaction):
        participante = {
            "user_id": interaction.user.id,
            "nombre_discord": str(interaction.user),
            "personaje": self.personaje.value.strip(),
        }

        ok, mensaje = storage.agregar_participante(self.evento_id, participante)

        await interaction.response.send_message(
            ("✅ " if ok else "❌ ") + mensaje, ephemeral=True
        )

        if ok:
            evento = storage.obtener_evento(self.evento_id)
            await _actualizar_mensaje_evento(interaction.client, evento)
            await _anunciar_inscripcion(
                interaction.client,
                evento,
                f"📋 **{participante['personaje']}** ({interaction.user.mention}) se inscribió en "
                f"**{evento['titulo']}**.",
            )


class EquipoRosterModal(discord.ui.Modal, title="Inscribir equipo (2/2)"):
    """Segundo paso de la inscripción grupal: composición del equipo."""

    tank = discord.ui.TextInput(label="Tank", placeholder="Nombre del personaje", max_length=32, required=True)
    healer = discord.ui.TextInput(label="Healer", placeholder="Nombre del personaje", max_length=32, required=True)
    dps1 = discord.ui.TextInput(label="DPS", placeholder="Nombre del personaje", max_length=32, required=True)
    dps2 = discord.ui.TextInput(label="DPS", placeholder="Nombre del personaje", max_length=32, required=True)
    dps3 = discord.ui.TextInput(label="DPS", placeholder="Nombre del personaje", max_length=32, required=True)

    def __init__(self, evento_id: str, nombre_equipo: str):
        super().__init__()
        self.evento_id = evento_id
        self.nombre_equipo = nombre_equipo

    async def on_submit(self, interaction: discord.Interaction):
        integrantes = [
            {"rol": "Tank", "personaje": self.tank.value.strip()},
            {"rol": "Healer", "personaje": self.healer.value.strip()},
            {"rol": "DPS", "personaje": self.dps1.value.strip()},
            {"rol": "DPS", "personaje": self.dps2.value.strip()},
            {"rol": "DPS", "personaje": self.dps3.value.strip()},
        ]
        equipo = {
            "nombre_equipo": self.nombre_equipo,
            "user_id": interaction.user.id,
            "nombre_discord": str(interaction.user),
            "integrantes": integrantes,
        }

        ok, mensaje = storage.agregar_equipo(self.evento_id, equipo)

        await interaction.response.send_message(
            ("✅ " if ok else "❌ ") + mensaje, ephemeral=True
        )

        if ok:
            evento = storage.obtener_evento(self.evento_id)
            await _actualizar_mensaje_evento(interaction.client, evento)
            lineas = ", ".join(f"{i['rol']}: {i['personaje']}" for i in integrantes)
            await _anunciar_inscripcion(
                interaction.client,
                evento,
                f"👥 Equipo **{self.nombre_equipo}** (por {interaction.user.mention}) se inscribió en "
                f"**{evento['titulo']}** — {lineas}.",
            )


class NombreEquipoModal(discord.ui.Modal, title="Inscribir equipo (1/2)"):
    """Primer paso de la inscripción grupal: nombre del equipo."""

    nombre_equipo = discord.ui.TextInput(
        label="Nombre del equipo",
        placeholder="Ej: Murlocs Anónimos",
        max_length=50,
        required=True,
    )

    def __init__(self, evento_id: str):
        super().__init__()
        self.evento_id = evento_id

    async def on_submit(self, interaction: discord.Interaction):
        # Discord no permite abrir un modal en respuesta al envío de otro modal:
        # se necesita un botón intermedio (sí puede abrir un modal) para el paso 2.
        await interaction.response.send_message(
            f"Equipo **{self.nombre_equipo.value.strip()}** — pulsa continuar para cargar la composición.",
            view=ContinuarEquipoView(self.evento_id, self.nombre_equipo.value.strip()),
            ephemeral=True,
        )


class ContinuarEquipoView(discord.ui.View):
    """Puente entre los dos formularios: un botón sí puede abrir el segundo modal."""

    def __init__(self, evento_id: str, nombre_equipo: str):
        super().__init__(timeout=300)
        self.evento_id = evento_id
        self.nombre_equipo = nombre_equipo

    @discord.ui.button(label="Continuar", style=discord.ButtonStyle.primary, emoji="➡️")
    async def continuar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EquipoRosterModal(self.evento_id, self.nombre_equipo))


class EventoView(discord.ui.View):
    """Vista persistente asociada a un evento concreto (custom_id incluye el id)."""

    def __init__(self, evento_id: str, abierto: bool):
        super().__init__(timeout=None)
        self.evento_id = evento_id

        boton_inscribirse = discord.ui.Button(
            label="Inscribirse" if abierto else "Inscripciones cerradas",
            style=discord.ButtonStyle.success if abierto else discord.ButtonStyle.secondary,
            emoji="📋",
            disabled=not abierto,
            custom_id=f"wow_evento:inscribirse:{evento_id}",
        )
        boton_inscribirse.callback = self._inscribirse
        self.add_item(boton_inscribirse)

        boton_baja = discord.ui.Button(
            label="Darme de baja",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            disabled=not abierto,
            custom_id=f"wow_evento:baja:{evento_id}",
        )
        boton_baja.callback = self._darse_de_baja
        self.add_item(boton_baja)

    async def _inscribirse(self, interaction: discord.Interaction):
        evento = storage.obtener_evento(self.evento_id)
        if evento is None or evento["estado"] != "abierto":
            await interaction.response.send_message(
                "❌ Las inscripciones ya no están disponibles para este evento.", ephemeral=True
            )
            return

        if evento["tipo_inscripcion"] == "grupal":
            if evento["num_equipos"] is not None and len(evento["equipos"]) >= evento["num_equipos"]:
                await interaction.response.send_message(
                    f"❌ Ya se alcanzó el cupo máximo de {evento['num_equipos']} equipos.", ephemeral=True
                )
                return
            await interaction.response.send_modal(NombreEquipoModal(self.evento_id))
        else:
            await interaction.response.send_modal(InscripcionModal(self.evento_id))

    async def _darse_de_baja(self, interaction: discord.Interaction):
        evento = storage.obtener_evento(self.evento_id)
        if evento is None or evento["estado"] != "abierto":
            await interaction.response.send_message(
                "❌ Ya no puedes darte de baja de este evento.", ephemeral=True
            )
            return

        if evento["tipo_inscripcion"] == "grupal":
            quitado = storage.quitar_equipo(self.evento_id, interaction.user.id)
            mensaje_ok = "✅ Diste de baja a tu equipo del evento."
            mensaje_error = "❌ No tenías un equipo inscrito en este evento."
        else:
            quitado = storage.quitar_participante(self.evento_id, interaction.user.id)
            mensaje_ok = "✅ Te has dado de baja del evento."
            mensaje_error = "❌ No estabas inscrito en este evento."

        if quitado:
            evento = storage.obtener_evento(self.evento_id)
            await _actualizar_mensaje_evento(interaction.client, evento)
            await interaction.response.send_message(mensaje_ok, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje_error, ephemeral=True)
