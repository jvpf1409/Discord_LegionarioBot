"""
Panel privado para que la organización arme los equipos de un evento de
tipo "armado": un equipo a la vez, con un select por rol que solo ofrece
inscritos de ese rol que no estén ya en otro equipo.
"""

import logging

import discord

from cogs.vistas import _actualizar_mensaje_evento, construir_embed_evento
from utils import storage
from utils import equipos_armados as armado

logger = logging.getLogger(__name__)

# Discord limita los selects a 25 opciones.
MAX_OPCIONES = 25


def _opcion(p: dict, suplente: bool, seleccionado: bool) -> discord.SelectOption:
    descripcion = f"{p['ilvl']} ilvl · {p['io']} IO · {p['nombre_discord']}"
    if suplente:
        descripcion += " · suplente"
    return discord.SelectOption(
        label=f"{p['personaje']} — {p['especializacion']} {p['clase']}"[:100],
        description=descripcion[:100],
        value=str(p["user_id"]),
        default=seleccionado,
    )


class RolSelect(discord.ui.Select):
    def __init__(self, panel: "ArmarEquiposView", categoria: str, row: int):
        self.panel = panel
        self.categoria = categoria
        borrador = panel.borradores[panel.actual]
        actuales = set(borrador["dps"]) if categoria == "dps" else {borrador[categoria]}
        ocupados = panel.ocupados_en_otros_equipos()

        titulares, suplentes = armado.repartir(panel.evento)[categoria]
        opciones = [
            _opcion(p, es_suplente, p["user_id"] in actuales)
            for lista, es_suplente in ((titulares, False), (suplentes, True))
            for p in lista
            if p["user_id"] not in ocupados
        ][:MAX_OPCIONES]

        cupo = armado.CUPOS_POR_EQUIPO[categoria]
        nombre = armado.NOMBRES_CATEGORIA[categoria]
        if opciones:
            super().__init__(
                placeholder=f"{armado.EMOJIS_CATEGORIA[categoria]} Elige {cupo if cupo > 1 else 'el'} {nombre}",
                options=opciones,
                min_values=0,
                max_values=min(cupo, len(opciones)),
                row=row,
            )
        else:
            super().__init__(
                placeholder=f"No hay {nombre} disponibles",
                options=[discord.SelectOption(label="—", value="0")],
                disabled=True,
                row=row,
            )

    async def callback(self, interaction: discord.Interaction):
        ids = [int(v) for v in self.values]
        borrador = self.panel.borradores[self.panel.actual]
        if self.categoria == "dps":
            borrador["dps"] = ids
        else:
            borrador[self.categoria] = ids[0] if ids else None
        await self.panel.refrescar(interaction)


class ArmarEquiposView(discord.ui.View):
    def __init__(self, evento: dict, autor_id: int):
        # El token de una interacción dura 15 minutos; se cierra antes para
        # poder avisar en el propio panel que expiró.
        super().__init__(timeout=14 * 60)
        self.evento = evento
        self.autor_id = autor_id
        self.actual = 0
        self.interaccion_inicial: discord.Interaction | None = None

        cantidad = evento.get("cantidad_equipos", 1)
        self.borradores = armado.borradores_desde_equipos(evento["equipos"], evento["participantes"])
        self.borradores = self.borradores[:cantidad]
        while len(self.borradores) < cantidad:
            self.borradores.append({"tank": None, "healer": None, "dps": []})
        self._construir()

    # ---------------- estado ----------------
    def ocupados_en_otros_equipos(self) -> set[int]:
        return {
            user_id
            for i, b in enumerate(self.borradores)
            if i != self.actual
            for user_id in (b["tank"], b["healer"], *b["dps"])
            if user_id is not None
        }

    def _recargar_evento(self):
        """Toma las inscripciones actuales y descarta a quien se haya dado de baja."""
        evento = storage.obtener_evento(self.evento["id"])
        if evento is None:
            return
        self.evento = evento
        vigentes = {p["user_id"] for p in evento["participantes"]}
        for b in self.borradores:
            if b["tank"] not in vigentes:
                b["tank"] = None
            if b["healer"] not in vigentes:
                b["healer"] = None
            b["dps"] = [u for u in b["dps"] if u in vigentes]

    def contenido(self) -> str:
        por_id = {p["user_id"]: p for p in self.evento["participantes"]}

        def nombre(user_id):
            return por_id[user_id]["personaje"] if user_id in por_id else "—"

        lineas = [
            f"**Armando equipos — {self.evento['titulo']}**",
            f"Editando el **Equipo {self.actual + 1}** de {len(self.borradores)}. "
            "Los promedios te ayudan a dejarlos parejos.",
            "",
        ]
        for i, b in enumerate(self.borradores):
            integrantes = [por_id[u] for u in (b["tank"], b["healer"], *b["dps"]) if u in por_id]
            prom = armado.promedios(integrantes)
            prom_txt = f" · {prom[0]} ilvl · {prom[1]} IO" if prom else ""
            marca = "▶" if i == self.actual else "•"
            dps = ", ".join(nombre(u) for u in b["dps"]) or "—"
            lineas.append(
                f"{marca} **Equipo {i + 1}**{prom_txt}\n"
                f"   🛡️ {nombre(b['tank'])} · ➕ {nombre(b['healer'])} · ⚔️ {dps}"
            )

        asignados = {
            u for b in self.borradores for u in (b["tank"], b["healer"], *b["dps"]) if u is not None
        }
        sin_asignar = [p for p in self.evento["participantes"] if p["user_id"] not in asignados]
        lineas.append("")
        lineas.append(f"Inscritos sin equipo: **{len(sin_asignar)}**")
        texto = "\n".join(lineas)
        return texto if len(texto) <= 2000 else texto[:1990] + "…"

    # ---------------- componentes ----------------
    def _construir(self):
        self.clear_items()
        self.add_item(RolSelect(self, "tank", row=0))
        self.add_item(RolSelect(self, "healer", row=1))
        self.add_item(RolSelect(self, "dps", row=2))

        anterior = discord.ui.Button(label="Anterior", emoji="◀️", row=3, disabled=self.actual == 0)
        anterior.callback = self._anterior
        siguiente = discord.ui.Button(
            label="Siguiente", emoji="▶️", row=3, disabled=self.actual == len(self.borradores) - 1
        )
        siguiente.callback = self._siguiente
        publicar = discord.ui.Button(label="Publicar equipos", emoji="📣", style=discord.ButtonStyle.success, row=3)
        publicar.callback = self._publicar
        cancelar = discord.ui.Button(label="Cancelar", style=discord.ButtonStyle.secondary, row=3)
        cancelar.callback = self._cancelar
        for boton in (anterior, siguiente, publicar, cancelar):
            self.add_item(boton)

    async def refrescar(self, interaction: discord.Interaction):
        self._recargar_evento()
        self._construir()
        await interaction.response.edit_message(content=self.contenido(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "❌ Solo quien abrió el panel puede usarlo.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.interaccion_inicial is not None:
            try:
                await self.interaccion_inicial.edit_original_response(
                    content="⌛ El panel expiró sin publicar. Vuelve a usar `/evento armar_equipos`.",
                    view=None,
                )
            except discord.HTTPException:
                pass

    async def _anterior(self, interaction: discord.Interaction):
        self.actual -= 1
        await self.refrescar(interaction)

    async def _siguiente(self, interaction: discord.Interaction):
        self.actual += 1
        await self.refrescar(interaction)

    async def _cancelar(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(content="Armado cancelado, no se publicó nada.", view=None)

    async def _publicar(self, interaction: discord.Interaction):
        self._recargar_evento()
        incompletos = [
            f"Equipo {i + 1}: falta {', '.join(falta)}"
            for i, b in enumerate(self.borradores)
            if (falta := armado.faltantes(b))
        ]
        if incompletos:
            self._construir()
            await interaction.response.edit_message(content=self.contenido(), view=self)
            await interaction.followup.send(
                "❌ Todos los equipos deben estar completos (1 Tank, 1 Healer, 3 DPS):\n"
                + "\n".join(incompletos)
                + "\nSi no hay gente suficiente, reduce la cantidad con `/evento editar`.",
                ephemeral=True,
            )
            return

        equipos = armado.construir_equipos(self.borradores, self.evento["participantes"])
        evento = storage.actualizar_evento(self.evento["id"], equipos=equipos)
        await _actualizar_mensaje_evento(interaction.client, evento)

        embed = discord.Embed(title=f"🧩 Equipos — {evento['titulo']}", color=discord.Color.gold())
        for equipo in equipos:
            ilvl, io = armado.promedios(equipo["integrantes"])
            embed.add_field(
                name=f"Equipo #{equipo['numero']} · {ilvl} ilvl · {io} IO",
                value="\n".join(
                    f"• **{i['rol']}** — {i['personaje']} (<@{i['user_id']}>)"
                    for i in equipo["integrantes"]
                ),
                inline=True,
            )
        menciones = " ".join(
            f"<@{i['user_id']}>" for equipo in equipos for i in equipo["integrantes"]
        )
        aviso = ""
        try:
            canal = interaction.client.get_channel(evento["canal_id"])
            if canal is None:
                canal = await interaction.client.fetch_channel(evento["canal_id"])
            await canal.send(
                content=f"📣 ¡Ya están los equipos de **{evento['titulo']}**! {menciones}",
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            logger.exception("No se pudieron anunciar los equipos del evento %s", evento["id"])
            aviso = "\n⚠️ Se guardaron, pero no pude publicar el anuncio en el canal del evento."

        self.stop()
        await interaction.response.edit_message(
            content=f"✅ Equipos publicados para **{evento['titulo']}**.{aviso}",
            embed=construir_embed_evento(evento),
            view=None,
        )
