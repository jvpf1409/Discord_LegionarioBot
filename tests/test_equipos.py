import unittest

from utils.equipos import buscar_equipo, numerar_equipo, numero_de_equipo


def _inscribir(evento, nombre):
    equipo = {"nombre_equipo": nombre}
    numerar_equipo(evento, equipo)
    evento["equipos"].append(equipo)
    return equipo


class NumeracionEquiposTests(unittest.TestCase):
    def test_numeros_consecutivos(self):
        evento = {"equipos": []}

        numeros = [_inscribir(evento, n)["numero"] for n in ("A", "B", "C")]

        self.assertEqual(numeros, [1, 2, 3])

    def test_baja_no_recorre_ni_reutiliza_numeros(self):
        evento = {"equipos": []}
        for nombre in ("A", "B", "C"):
            _inscribir(evento, nombre)

        evento["equipos"] = [e for e in evento["equipos"] if e["nombre_equipo"] != "C"]
        nuevo = _inscribir(evento, "D")

        self.assertEqual(nuevo["numero"], 4)
        self.assertEqual(buscar_equipo(evento, 2)["nombre_equipo"], "B")
        self.assertIsNone(buscar_equipo(evento, 3))

    def test_equipos_antiguos_sin_numero_usan_su_posicion(self):
        evento = {"equipos": [{"nombre_equipo": "A"}, {"nombre_equipo": "B"}]}

        self.assertEqual(numero_de_equipo(evento["equipos"][1], 2), 2)
        self.assertEqual(buscar_equipo(evento, 2)["nombre_equipo"], "B")
        self.assertEqual(_inscribir(evento, "C")["numero"], 3)


if __name__ == "__main__":
    unittest.main()
