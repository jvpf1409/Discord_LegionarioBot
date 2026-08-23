"""Control de silencio por canal de voz mediante un boton persistente."""

from __future__ import annotations

import asyncio
import os

import discord
from discord import app_commands
from discord.ext import commands


def _ids_env(nombre: str) -> set[int]:
    resultado: set[int] = set()
    for valor in os.getenv(nombre, "").split(","):
        valor = valor.strip()
        if valor:
            try:
                resultado.add(int(valor))
            except ValueError:
                pass
    return resultado


CANALES_PERMITIDOS = _ids_env("VOZ_CANALES_ID")
ROLES_CONTROLADORES = _ids_env("VOZ_ROLES_CONTROLADORES_ID")
ROLES_AFECTADOS = _ids_env("VOZ_ROLES_AFECTADOS_ID")
ROLES_EXENTOS = _ids_env("VOZ_ROLES_EXENTOS_ID")
ROL_LIMITE_ID = int(os.getenv("VOZ_ROL_LIMITE_ID", "0") or 0)


class PanelSilencio(discord.ui.View):
    def __init__(self, cog: "ControlVoz", canal_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.canal_id = canal_id
        self._actualizar_boton()

    def _actualizar_boton(self) -> None:
        activo = self.canal_id in self.cog.canales_activos
        boton = discord.ui.Button(
            label="Permitir hablar" if activo else "Silenciar grupo",
            style=discord.ButtonStyle.success if activo else discord.ButtonStyle.danger,
            emoji="🔊" if activo else "🔇",
            custom_id=f"control_voz:alternar:{self.canal_id}",
        )
        boton.callback = self._alternar
        self.clear_items()
        self.add_item(boton)

    async def _alternar(self, interaction: discord.Interaction) -> None:
        miembro = interaction.user
        if not isinstance(miembro, discord.Member) or not self.cog.puede_controlar(miembro):
            await interaction.response.send_message(
                "No tienes uno de los roles autorizados para usar este control.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        activo, modificados, errores = await self.cog.alternar(self.canal_id)
        self._actualizar_boton()
        try:
            await interaction.message.edit(view=self)
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass
        accion = "silenciado" if activo else "habilitado para hablar"
        mensaje = f"Control actualizado: grupo **{accion}**. Miembros modificados: **{modificados}**."
        if errores:
            mensaje += f" No pude modificar a **{errores}** miembro(s); revisa permisos y jerarquia."
        await interaction.followup.send(mensaje, ephemeral=True)


class ControlVoz(commands.Cog):
    voz = app_commands.Group(name="voz", description="Control de los canales de voz configurados")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.canales_activos: set[int] = set()
        self.silenciados_por_bot: dict[int, set[int]] = {}
        self.locks: dict[int, asyncio.Lock] = {}

    async def cog_load(self) -> None:
        for canal_id in CANALES_PERMITIDOS:
            self.bot.add_view(PanelSilencio(self, canal_id))

    @staticmethod
    def puede_controlar(miembro: discord.Member) -> bool:
        return any(rol.id in ROLES_CONTROLADORES for rol in miembro.roles)

    @staticmethod
    def debe_ser_silenciado(miembro: discord.Member) -> bool:
        roles = {rol.id for rol in miembro.roles}
        if not roles.intersection(ROLES_AFECTADOS) or roles.intersection(ROLES_EXENTOS):
            return False
        if ROL_LIMITE_ID:
            limite = miembro.guild.get_role(ROL_LIMITE_ID)
            if limite is not None and miembro.top_role >= limite:
                return False
        return not miembro.bot

    async def _silenciar(self, miembro: discord.Member, canal_id: int) -> tuple[bool, bool]:
        if miembro.voice is None or miembro.voice.channel is None:
            return False, False
        if miembro.voice.channel.id != canal_id or not self.debe_ser_silenciado(miembro):
            return False, False
        if miembro.voice.mute:
            return False, False
        try:
            await miembro.edit(mute=True, reason="Control de silencio del canal activado")
            self.silenciados_por_bot.setdefault(canal_id, set()).add(miembro.id)
            return True, False
        except (discord.Forbidden, discord.HTTPException):
            return False, True

    async def _desilenciar(self, miembro: discord.Member, canal_id: int) -> tuple[bool, bool]:
        registrados = self.silenciados_por_bot.setdefault(canal_id, set())
        if miembro.id not in registrados:
            return False, False
        try:
            if miembro.voice is not None and miembro.voice.mute:
                await miembro.edit(mute=False, reason="Control de silencio del canal desactivado")
            registrados.discard(miembro.id)
            return True, False
        except (discord.Forbidden, discord.HTTPException):
            return False, True

    @staticmethod
    async def _obtener_miembro_actualizado(miembro: discord.Member) -> discord.Member:
        """Consulta los roles actuales sin depender de la cache de miembros."""
        try:
            return await miembro.guild.fetch_member(miembro.id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return miembro

    async def alternar(self, canal_id: int) -> tuple[bool, int, int]:
        lock = self.locks.setdefault(canal_id, asyncio.Lock())
        async with lock:
            canal = self.bot.get_channel(canal_id)
            if not isinstance(canal, discord.VoiceChannel):
                return False, 0, 1
            activar = canal_id not in self.canales_activos
            if activar:
                self.canales_activos.add(canal_id)
                resultados = []
                for miembro in canal.members:
                    miembro_actualizado = await self._obtener_miembro_actualizado(miembro)
                    resultados.append(await self._silenciar(miembro_actualizado, canal_id))
            else:
                self.canales_activos.discard(canal_id)
                ids = set(self.silenciados_por_bot.get(canal_id, set()))
                miembros = [canal.guild.get_member(miembro_id) for miembro_id in ids]
                resultados = [await self._desilenciar(m, canal_id) for m in miembros if m is not None]
                self.silenciados_por_bot.pop(canal_id, None)
            return activar, sum(ok for ok, _ in resultados), sum(error for _, error in resultados)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, miembro: discord.Member, antes: discord.VoiceState, despues: discord.VoiceState
    ) -> None:
        canal_anterior = antes.channel.id if antes.channel else None
        canal_nuevo = despues.channel.id if despues.channel else None
        if canal_anterior and canal_anterior != canal_nuevo:
            await self._desilenciar(miembro, canal_anterior)
        if canal_nuevo in self.canales_activos:
            await self._silenciar(miembro, canal_nuevo)

    @voz.command(name="panel", description="Publica el boton de silencio para un canal configurado")
    @app_commands.describe(canal="Canal de voz que controlara este boton")
    async def publicar_panel(self, interaction: discord.Interaction, canal: discord.VoiceChannel) -> None:
        miembro = interaction.user
        if not isinstance(miembro, discord.Member) or not self.puede_controlar(miembro):
            await interaction.response.send_message("No tienes permiso para publicar este panel.", ephemeral=True)
            return
        if canal.id not in CANALES_PERMITIDOS:
            await interaction.response.send_message("Ese canal no esta incluido en VOZ_CANALES_ID.", ephemeral=True)
            return
        embed = discord.Embed(
            title="Control de voz",
            description=(f"Este panel controla solamente {canal.mention}.\n"
                         "Los usuarios afectados pueden seguir escuchando mientras estan silenciados."),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=PanelSilencio(self, canal.id))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ControlVoz(bot))
