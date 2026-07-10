"""Chequeos de permisos compartidos entre los grupos de comandos del bot."""

from discord import app_commands


def es_organizador():
    """Requiere permiso de 'Gestionar servidor' (ajústalo a tu rol de oficial/raid leader)."""
    return app_commands.checks.has_permissions(manage_guild=True)
