import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from utils import permisos


class MiembroFalso:
    def __init__(self, roles):
        self.roles = [SimpleNamespace(id=rol_id) for rol_id in roles]


def predicado_de(decorador):
    async def comando(_interaction):
        return None

    decorado = decorador(comando)
    return decorado.__discord_app_commands_checks__[0]


class PermisosTests(unittest.TestCase):
    def ejecutar(self, predicado, roles):
        interaction = SimpleNamespace(user=MiembroFalso(roles))
        with patch.object(permisos.discord, "Member", MiembroFalso):
            return asyncio.run(predicado(interaction))

    def test_maestro_hereda_comandos_de_oficial(self):
        with patch.object(permisos, "ROL_MAESTRO_ID", 10), patch.object(
            permisos, "ROL_OFICIAL_ID", 20
        ):
            self.assertTrue(self.ejecutar(predicado_de(permisos.es_organizador()), [10]))
            self.assertTrue(self.ejecutar(predicado_de(permisos.es_organizador()), [20]))

    def test_oficial_no_puede_usar_comandos_de_maestro(self):
        with patch.object(permisos, "ROL_MAESTRO_ID", 10), patch.object(
            permisos, "ROL_OFICIAL_ID", 20
        ):
            with self.assertRaises(permisos.RolRequerido):
                self.ejecutar(predicado_de(permisos.es_administrador()), [20])

    def test_avisa_si_falta_configuracion(self):
        with patch.object(permisos, "ROL_MAESTRO_ID", None), patch.object(
            permisos, "ROL_OFICIAL_ID", 20
        ):
            with self.assertRaises(permisos.RolRequerido) as contexto:
                self.ejecutar(predicado_de(permisos.es_administrador()), [10])
            self.assertFalse(contexto.exception.configurado)


if __name__ == "__main__":
    unittest.main()
