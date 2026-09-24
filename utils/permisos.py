"""Niveles de acceso compartidos para los comandos del bot."""

import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ROL_MAESTRO = "Legionario Maestro"
ROL_OFICIAL = "Legionario Oficial"


def _leer_id(nombre: str) -> int | None:
    valor = os.getenv(nombre, "").strip()
    try:
        return int(valor) if valor else None
    except ValueError:
        return None


ROL_MAESTRO_ID = _leer_id("ROL_MAESTRO_ID")
ROL_OFICIAL_ID = _leer_id("ROL_OFICIAL_ID")


class RolRequerido(app_commands.CheckFailure):
    def __init__(self, rol: str, configurado: bool = True):
        self.rol = rol
        self.configurado = configurado
        super().__init__(rol)


def _roles_del_usuario(interaction: discord.Interaction) -> set[int]:
    if not isinstance(interaction.user, discord.Member):
        return set()
    return {rol.id for rol in interaction.user.roles}


def es_organizador():
    """Permite a Legionario Oficial y, por jerarquía, Legionario Maestro."""
    async def comprobar(interaction: discord.Interaction) -> bool:
        if ROL_OFICIAL_ID is None or ROL_MAESTRO_ID is None:
            raise RolRequerido(ROL_OFICIAL, configurado=False)
        roles = _roles_del_usuario(interaction)
        if ROL_OFICIAL_ID not in roles and ROL_MAESTRO_ID not in roles:
            raise RolRequerido(ROL_OFICIAL)
        return True

    return app_commands.check(comprobar)


def es_administrador():
    """Permite únicamente al rol Legionario Maestro configurado por ID."""
    async def comprobar(interaction: discord.Interaction) -> bool:
        if ROL_MAESTRO_ID is None:
            raise RolRequerido(ROL_MAESTRO, configurado=False)
        if ROL_MAESTRO_ID not in _roles_del_usuario(interaction):
            raise RolRequerido(ROL_MAESTRO)
        return True

    return app_commands.check(comprobar)


def mensaje_error_permiso(error: app_commands.AppCommandError) -> str | None:
    if not isinstance(error, RolRequerido):
        return None
    if not error.configurado:
        variable = "ROL_MAESTRO_ID" if error.rol == ROL_MAESTRO else "ROL_OFICIAL_ID"
        return f"⚠️ El permiso **{error.rol}** no está configurado. Revisa `{variable}`."
    return f"🚫 Necesitas el rol **{error.rol}** para usar este comando."
