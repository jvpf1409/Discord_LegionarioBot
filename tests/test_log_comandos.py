import unittest
from types import SimpleNamespace

from utils.log_comandos import extraer_comando_y_parametros, formatear_invocacion


class LogComandosTests(unittest.TestCase):
    def test_extrae_subcomando_y_parametros(self):
        data = {
            "name": "raid",
            "options": [{
                "name": "crear", "type": 1,
                "options": [
                    {"name": "titulo", "type": 3, "value": "Raid Progress"},
                    {"name": "canal", "type": 7, "value": "12345"},
                ],
            }],
        }
        comando, parametros = extraer_comando_y_parametros(data)
        self.assertEqual(comando, "/raid crear")
        self.assertEqual(parametros, {"titulo": "Raid Progress", "canal": "12345"})

    def test_formato_incluye_contexto(self):
        interaction = SimpleNamespace(
            data={"name": "raid", "options": []},
            user=SimpleNamespace(id=42, __str__=lambda self: "Jen"),
            guild_id=10,
            channel_id=20,
        )
        # SimpleNamespace no personaliza str mediante un atributo; basta validar IDs y comando.
        texto = formatear_invocacion(interaction)
        self.assertIn("usuario_id=42", texto)
        self.assertIn("guild_id=10", texto)
        self.assertIn("canal_id=20", texto)
        self.assertIn("comando=/raid", texto)


if __name__ == "__main__":
    unittest.main()
