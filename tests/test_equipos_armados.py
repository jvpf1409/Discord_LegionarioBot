import unittest

from utils import equipos_armados as armado


def _p(user_id, rol, ilvl=640, io=2800):
    return {
        "user_id": user_id,
        "nombre_discord": f"user{user_id}",
        "personaje": f"pj{user_id}",
        "clase": "Clase",
        "especializacion": "Spec",
        "rol": rol,
        "ilvl": ilvl,
        "io": io,
    }


def _evento(participantes, cantidad_equipos=1):
    return {"cantidad_equipos": cantidad_equipos, "participantes": participantes, "equipos": []}


class CuposTests(unittest.TestCase):
    def test_cupos_escalan_con_la_cantidad_de_equipos(self):
        self.assertEqual(armado.cupos(3), {"tank": 3, "healer": 3, "dps": 9})

    def test_melee_y_ranged_cuentan_como_dps(self):
        self.assertEqual(armado.categoria("melee"), "dps")
        self.assertEqual(armado.categoria("ranged"), "dps")
        self.assertEqual(armado.categoria("tank"), "tank")

    def test_rol_lleno_deja_suplentes_en_orden_de_inscripcion(self):
        evento = _evento([_p(1, "tank"), _p(2, "tank"), _p(3, "tank")])

        titulares, suplentes = armado.repartir(evento)["tank"]

        self.assertEqual([p["user_id"] for p in titulares], [1])
        self.assertEqual([p["user_id"] for p in suplentes], [2, 3])
        self.assertEqual(armado.estado_inscrito(evento, 1), ("tank", 1, 1))
        self.assertEqual(armado.estado_inscrito(evento, 3), ("tank", -2, 1))
        self.assertIsNone(armado.estado_inscrito(evento, 99))

    def test_baja_promueve_al_primer_suplente(self):
        antes = _evento([_p(1, "healer"), _p(2, "healer"), _p(3, "healer")])
        despues = _evento([_p(2, "healer"), _p(3, "healer")])

        promovidos = armado.promovidos(antes, despues)

        self.assertEqual([(p["user_id"], c) for p, c in promovidos], [(2, "healer")])

    def test_ampliar_equipos_promueve_suplentes_y_no_reporta_nuevos(self):
        participantes = [_p(1, "tank"), _p(2, "tank"), _p(3, "melee")]
        antes = _evento(participantes, cantidad_equipos=1)
        despues = _evento(participantes, cantidad_equipos=2)

        self.assertEqual([p["user_id"] for p, _ in armado.promovidos(antes, despues)], [2])

        con_nuevo = _evento(participantes + [_p(4, "tank")], cantidad_equipos=1)
        self.assertEqual(armado.promovidos(antes, con_nuevo), [])

    def test_resumen_cupos(self):
        evento = _evento([_p(1, "tank"), _p(2, "tank"), _p(3, "ranged")], cantidad_equipos=1)

        resumen = armado.resumen_cupos(evento)

        self.assertIn("Tank 1/1 (+1 suplentes)", resumen)
        self.assertIn("Healer 0/1", resumen)
        self.assertIn("DPS 1/3", resumen)


class ParsearNumeroTests(unittest.TestCase):
    def test_formatos_validos(self):
        self.assertEqual(armado.parsear_numero("639", 1, 2000), 639)
        self.assertEqual(armado.parsear_numero(" 2,850 ", 0, 10000), 2850)
        self.assertEqual(armado.parsear_numero("2850.6", 0, 10000), 2851)
        self.assertEqual(armado.parsear_numero("2850,4", 0, 10000), 2850)

    def test_formatos_invalidos(self):
        self.assertIsNone(armado.parsear_numero("mucho", 0, 10000))
        self.assertIsNone(armado.parsear_numero("-5", 0, 10000))
        self.assertIsNone(armado.parsear_numero("99999", 0, 10000))


class ArmadoTests(unittest.TestCase):
    def setUp(self):
        self.participantes = [
            _p(1, "tank", 640, 3000), _p(2, "healer", 630, 2000),
            _p(3, "melee", 620, 2500), _p(4, "ranged", 650, 3500), _p(5, "melee", 640, 1000),
        ]
        self.borrador = {"tank": 1, "healer": 2, "dps": [3, 4, 5]}

    def test_faltantes(self):
        self.assertEqual(armado.faltantes(self.borrador), [])
        self.assertEqual(
            armado.faltantes({"tank": None, "healer": 2, "dps": [3]}), ["tank", "2 DPS"]
        )

    def test_construir_equipos_compatible_con_registrar_ganador(self):
        (equipo,) = armado.construir_equipos([self.borrador], self.participantes)

        self.assertEqual(equipo["numero"], 1)
        self.assertEqual(equipo["nombre_equipo"], "Equipo 1")
        self.assertEqual([i["rol"] for i in equipo["integrantes"]], ["Tank", "Healer", "DPS", "DPS", "DPS"])
        self.assertEqual(armado.promedios(equipo["integrantes"]), (636, 2400))

    def test_borradores_ida_y_vuelta_descarta_bajas(self):
        equipos = armado.construir_equipos([self.borrador], self.participantes)

        sin_baja = armado.borradores_desde_equipos(equipos, self.participantes)
        con_baja = armado.borradores_desde_equipos(equipos, self.participantes[:-1])

        self.assertEqual(sin_baja, [self.borrador])
        self.assertEqual(con_baja, [{"tank": 1, "healer": 2, "dps": [3, 4]}])

    def test_exportar_inscritos_para_ia(self):
        participantes = self.participantes + [_p(6, "tank", 600, 500)]
        participantes[0] = dict(participantes[0], personaje='Thrall, "el Jefe"')
        evento = dict(_evento(participantes), titulo="Torneo")

        texto = armado.texto_para_ia(evento)
        filas = armado.inscritos_csv(evento).splitlines()

        self.assertIn("Formato: 1 equipo de 1 Tank, 1 Healer y 3 DPS", texto)
        self.assertIn("Instrucciones:", texto)
        self.assertEqual(filas[0], "Rol,Personaje,Clase,Especialización,Ilvl,IO,Discord,Estado")
        # Las comas y comillas del nombre no rompen el CSV.
        self.assertEqual(filas[1], 'Tank,"Thrall, ""el Jefe""",Clase,Spec,640,3000,user1,Titular')
        self.assertEqual(filas[2], "Tank,pj6,Clase,Spec,600,500,user6,Suplente")
        self.assertEqual(len(filas), 7)

    def test_dividir_en_campos_respeta_limite(self):
        lineas = ["x" * 100] * 25

        bloques = armado.dividir_en_campos(lineas)

        self.assertTrue(all(len(b) <= 1024 for b in bloques))
        self.assertEqual(sum(b.count("x" * 100) for b in bloques), 25)


if __name__ == "__main__":
    unittest.main()
