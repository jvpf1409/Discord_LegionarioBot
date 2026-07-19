"""Chequeos de permisos compartidos entre los grupos de comandos del bot."""

from discord import app_commands

ROL_OFICIAL = "Legionario Oficial"


def es_organizador():
    """Requiere el rol de oficial configurado para administrar actividades."""
    return app_commands.checks.has_role(ROL_OFICIAL)
