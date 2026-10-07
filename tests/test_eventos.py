import unittest

from cogs.eventos import _construir_anuncio_ganador


class AnuncioGanadorTests(unittest.TestCase):
    def test_ganador_individual_aparece_una_sola_vez(self):
        anuncio = _construir_anuncio_ganador("Evento de prueba", "<@123>")

        self.assertEqual(anuncio.count("<@123>"), 1)
        self.assertNotIn("Integrantes", anuncio)

    def test_equipo_incluye_integrantes(self):
        anuncio = _construir_anuncio_ganador(
            "Míticas", "Los Murlocs", "• Tank — Thrall"
        )

        self.assertIn("Los Murlocs", anuncio)
        self.assertIn("**Integrantes**", anuncio)
        self.assertIn("Thrall", anuncio)


if __name__ == "__main__":
    unittest.main()
