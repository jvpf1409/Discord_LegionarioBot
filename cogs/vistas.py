"""
Componentes de UI: botones persistentes e inscripción (individual, por
equipos o individual para equipos armados por la organización).
"""

import discord
from utils import storage
from utils import equipos_armados as armado
from utils.equipos import numero_de_equipo
from utils.wow_data import CLASES, icono_clase, icono_especializacion, rol_de


def _linea_inscrito_armado(p: dict, con_icono: bool = True) -> str:
    icono = ""
    if con_icono:
        icono = (icono_especializacion(p["clase"], p["especializacion"]) or icono_clase(p["clase"]) or "▫️") + " "
    return (
        f"{icono}**{p['personaje']}** — {p['especializacion']} · "
        f"{p['ilvl']} ilvl · {p['io']} IO · <@{p['user_id']}>"
    )


def _campos_armado(evento: dict, con_iconos: bool) -> list[tuple[str, str, bool]]:
    campos = []

    def bloques(nombre: str, inscritos: list[dict]):
        lineas = [_linea_inscrito_armado(p, con_iconos) for p in inscritos]
        for i, bloque in enumerate(armado.dividir_en_campos(lineas)):
            campos.append((nombre if i == 0 else f"{nombre} (cont.)", bloque, False))

    if evento["equipos"]:
        # Con los equipos publicados se muestran ellos en lugar de la lista por rol.
        en_equipo = set()
        for equipo in evento["equipos"]:
            lineas = []
            for i in equipo["integrantes"]:
                en_equipo.add(i["user_id"])
                lineas.append(f"• **{i['rol']}** — {i['personaje']} (<@{i['user_id']}>)")
            nombre = f"🧩 Equipo #{equipo['numero']}"
            prom = armado.promedios(equipo["integrantes"])
            if prom:
                nombre += f" · {prom[0]} ilvl · {prom[1]} IO"
            campos.append((nombre, "\n".join(lineas) or "—", True))
        bloques("Sin equipo", [p for p in evento["participantes"] if p["user_id"] not in en_equipo])
        return campos

    for c, (titulares, suplentes) in armado.repartir(evento).items():
        nombre = f"{armado.EMOJIS_CATEGORIA[c]} {armado.NOMBRES_CATEGORIA[c]}"
        bloques(nombre, titulares)
        bloques(f"{nombre} — suplentes", suplentes)
    return campos


def _agregar_campos_armado(embed: discord.Embed, evento: dict):
    embed.add_field(name="Tipo", value="🧩 Equipos armados", inline=True)
    embed.add_field(name="Equipos", value=str(evento.get("cantidad_equipos", 1)), inline=True)
    embed.add_field(name="Cupos", value=armado.resumen_cupos(evento), inline=False)

    campos = _campos_armado(evento, con_iconos=True)
    # Un embed admite 6000 caracteres en total y cada ícono personalizado ocupa
    # ~50; con muchos inscritos se quitan los íconos para que el mensaje quepa.
    if len(embed) + sum(len(n) + len(v) for n, v, _ in campos) > 5800:
        campos = _campos_armado(evento, con_iconos=False)
    for nombre, valor, inline in campos:
        embed.add_field(name=nombre, value=valor, inline=inline)


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

    if evento.get("creado_por"):
        embed.add_field(name="Creado por", value=f"<@{evento['creado_por']}>", inline=True)

    es_grupal = evento["tipo_inscripcion"] == "grupal"

    if evento["tipo_inscripcion"] == "armado":
        _agregar_campos_armado(embed, evento)
    elif es_grupal:
        embed.add_field(name="Tipo", value="👥 Grupal", inline=True)
        embed.add_field(name="Equipos", value=str(len(evento["equipos"])), inline=True)

        for posicion, equipo in enumerate(evento["equipos"], start=1):
            lineas = "\n".join(f"• **{i['rol']}** — {i['personaje']}" for i in equipo["integrantes"])
            embed.add_field(
                name=(
                    f"🛡️ Equipo #{numero_de_equipo(equipo, posicion)} — {equipo['nombre_equipo']} "
                    f"(por {equipo['nombre_discord']})"
                ),
                value=lineas,
                inline=True,
            )
    else:
        embed.add_field(name="Tipo", value="🙋 Individual", inline=True)
        embed.add_field(name="Inscritos", value=str(len(evento["participantes"])), inline=True)

        if evento["participantes"]:
            lista = "\n".join(f"• <@{p['user_id']}>" for p in evento["participantes"])
            if len(lista) > 1000:
                lista = lista[:1000] + "\n… (lista truncada)"
            embed.add_field(name="Participantes", value=lista, inline=False)

    if evento["estado"] == "finalizado" and evento.get("ganador") is not None:
        embed.add_field(name="🏆 Ganador", value=str(evento["ganador"]), inline=False)

    if evento.get("imagen_url"):
        embed.set_image(url=evento["imagen_url"])

    #embed.set_footer(text=f"ID del evento: {evento['id']}")
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


async def anunciar_promovidos(client: discord.Client, antes: dict, despues: dict):
    """Avisa en el canal de inscripciones qué suplentes pasaron a titulares."""
    for p, c in armado.promovidos(antes, despues):
        await _anunciar_inscripcion(
            client,
            despues,
            f"⬆️ <@{p['user_id']}> pasa de suplente a titular de "
            f"**{armado.NOMBRES_CATEGORIA[c]}** en **{despues['titulo']}**.",
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
            numero_equipo = equipo["numero"]
            await _actualizar_mensaje_evento(interaction.client, evento)
            lineas = ", ".join(f"{i['rol']}: {i['personaje']}" for i in integrantes)
            await _anunciar_inscripcion(
                interaction.client,
                evento,
                f"👥 Equipo **#{numero_equipo} — {self.nombre_equipo}** "
                f"(por {interaction.user.mention}) se inscribió en "
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


class DatosPersonajeModal(discord.ui.Modal, title="Datos del personaje"):
    """Último paso de la inscripción a equipos armados."""

    personaje = discord.ui.TextInput(label="Nombre del personaje", max_length=32, required=True)
    ilvl = discord.ui.TextInput(label="Item level", placeholder="Ej: 639", max_length=6, required=True)
    io = discord.ui.TextInput(label="Puntuación de Raider.IO", placeholder="Ej: 2850", max_length=8, required=True)

    def __init__(self, evento_id: str, clase: str, especializacion: str):
        super().__init__()
        self.evento_id = evento_id
        self.clase = clase
        self.especializacion = especializacion

    async def on_submit(self, interaction: discord.Interaction):
        ilvl = armado.parsear_numero(self.ilvl.value, 1, 2000)
        io = armado.parsear_numero(self.io.value, 0, 10000)
        if ilvl is None or io is None:
            campo = "Item level" if ilvl is None else "Raider.IO"
            await interaction.response.send_message(
                f"❌ El valor de **{campo}** no es un número válido. Vuelve a inscribirte.",
                ephemeral=True,
            )
            return

        participante = {
            "user_id": interaction.user.id,
            "nombre_discord": interaction.user.display_name,
            "personaje": self.personaje.value.strip(),
            "clase": self.clase,
            "especializacion": self.especializacion,
            "rol": rol_de(self.clase, self.especializacion),
            "ilvl": ilvl,
            "io": io,
        }
        ok, mensaje = storage.agregar_participante(self.evento_id, participante)
        if not ok:
            await interaction.response.send_message("❌ " + mensaje, ephemeral=True)
            return

        evento = storage.obtener_evento(self.evento_id)
        c, posicion, cupo = armado.estado_inscrito(evento, interaction.user.id)
        rol_txt = armado.NOMBRES_CATEGORIA[c]
        if posicion > 0:
            estado = f"titular de **{rol_txt}** ({posicion}/{cupo})"
        else:
            estado = f"**suplente** de **{rol_txt}** (posición {-posicion} en la lista de espera)"
        await interaction.response.send_message(f"✅ Quedaste inscrito como {estado}.", ephemeral=True)

        await _actualizar_mensaje_evento(interaction.client, evento)
        await _anunciar_inscripcion(
            interaction.client,
            evento,
            f"📋 {interaction.user.mention} se inscribió en **{evento['titulo']}** como "
            f"{self.especializacion} {self.clase} ({participante['personaje']}, "
            f"{ilvl} ilvl, {io} IO)" + ("." if posicion > 0 else " — suplente."),
        )


class EspecialidadArmadoSelect(discord.ui.Select):
    def __init__(self, evento_id: str, clase: str):
        opciones = [
            discord.SelectOption(
                label=especializacion,
                value=especializacion,
                emoji=icono_especializacion(clase, especializacion) or None,
            )
            for especializacion, _rol in CLASES[clase]
        ]
        super().__init__(placeholder="Selecciona tu especialización", options=opciones)
        self.evento_id = evento_id
        self.clase = clase

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            DatosPersonajeModal(self.evento_id, self.clase, self.values[0])
        )


class ClaseArmadoSelect(discord.ui.Select):
    def __init__(self, evento_id: str):
        opciones = [
            discord.SelectOption(label=clase, value=clase, emoji=icono_clase(clase) or None)
            for clase in CLASES
        ]
        super().__init__(placeholder="Selecciona tu clase", options=opciones)
        self.evento_id = evento_id

    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View(timeout=300)
        view.add_item(EspecialidadArmadoSelect(self.evento_id, self.values[0]))
        await interaction.response.edit_message(
            content=f"Elige tu especialización de **{self.values[0]}**:", view=view
        )


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
            await interaction.response.send_modal(NombreEquipoModal(self.evento_id))
        elif evento["tipo_inscripcion"] == "armado":
            if any(p["user_id"] == interaction.user.id for p in evento["participantes"]):
                await interaction.response.send_message(
                    "❌ Ya estás inscrito. Si quieres cambiar de personaje o rol, "
                    "date de baja y vuelve a inscribirte.",
                    ephemeral=True,
                )
                return
            view = discord.ui.View(timeout=300)
            view.add_item(ClaseArmadoSelect(self.evento_id))
            await interaction.response.send_message("Elige tu clase:", view=view, ephemeral=True)
        else:
            participante = {"user_id": interaction.user.id, "nombre_discord": str(interaction.user)}
            ok, mensaje = storage.agregar_participante(self.evento_id, participante)
            await interaction.response.send_message(("✅ " if ok else "❌ ") + mensaje, ephemeral=True)

            if ok:
                evento = storage.obtener_evento(self.evento_id)
                await _actualizar_mensaje_evento(interaction.client, evento)
                await _anunciar_inscripcion(
                    interaction.client,
                    evento,
                    f"📋 {interaction.user.mention} se inscribió en **{evento['titulo']}**.",
                )

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
            antes = evento
            evento = storage.obtener_evento(self.evento_id)
            await _actualizar_mensaje_evento(interaction.client, evento)
            await interaction.response.send_message(mensaje_ok, ephemeral=True)
            if evento["tipo_inscripcion"] == "armado":
                await anunciar_promovidos(interaction.client, antes, evento)
        else:
            await interaction.response.send_message(mensaje_error, ephemeral=True)
