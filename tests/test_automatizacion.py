import os
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ.pop("DATABASE_URL", None)

from cogs.automatizacion import UN_DIA, toca_publicar, vencido
from utils import tiempo


class AutomatizacionTests(unittest.TestCase):
    def test_cierra_solo_abiertos_un_dia_despues(self):
        self.assertFalse(vencido({"estado": "abierto", "fecha_hora_ts": 100}, 100 + UN_DIA - 1))
        self.assertTrue(vencido({"estado": "abierto", "fecha_hora_ts": 100}, 100 + UN_DIA))
        self.assertFalse(vencido({"estado": "cerrado", "fecha_hora_ts": 100}, 100 + UN_DIA))

    def test_publica_segun_anticipacion_y_estado(self):
        item = {"activa": True, "siguiente_publicacion_ts": 500_000}
        self.assertFalse(toca_publicar(item, 499_999))
        self.assertTrue(toca_publicar(item, 500_000))
        item["activa"] = False
        self.assertFalse(toca_publicar(item, 500_000))

    def test_siguiente_ocurrencia_semanal(self):
        anterior = tiempo.ZONA_HORARIA
        tiempo.ZONA_HORARIA = "America/Santiago"
        try:
            zona = ZoneInfo("America/Santiago")
            lunes_10 = int(datetime(2026, 9, 21, 10, 0, tzinfo=zona).timestamp())
            esperado = int(datetime(2026, 9, 21, 22, 0, tzinfo=zona).timestamp())
            self.assertEqual(tiempo.siguiente_ocurrencia_semanal(0, "22:00", lunes_10), esperado)
            siguiente = int(datetime(2026, 9, 28, 22, 0, tzinfo=zona).timestamp())
            self.assertEqual(tiempo.siguiente_ocurrencia_semanal(0, "22:00", esperado), siguiente)
        finally:
            tiempo.ZONA_HORARIA = anterior

    def test_raid_del_martes_avanza_a_la_semana_siguiente(self):
        anterior = tiempo.ZONA_HORARIA
        tiempo.ZONA_HORARIA = "America/Santiago"
        try:
            zona = ZoneInfo("America/Santiago")
            publicacion_viernes = int(
                datetime(2026, 9, 25, 12, 0, tzinfo=zona).timestamp()
            )
            martes_siguiente = int(
                datetime(2026, 9, 29, 23, 0, tzinfo=zona).timestamp()
            )
            self.assertEqual(
                tiempo.siguiente_ocurrencia_semanal(1, "23:00", publicacion_viernes),
                martes_siguiente,
            )
        finally:
            tiempo.ZONA_HORARIA = anterior

    def test_plantilla_y_publicacion_mismo_dia_no_reutilizan_fecha(self):
        anterior = tiempo.ZONA_HORARIA
        tiempo.ZONA_HORARIA = "America/Santiago"
        try:
            zona = ZoneInfo("America/Santiago")
            plantilla = int(datetime(2026, 9, 24, 23, 0, tzinfo=zona).timestamp())
            esperado = int(datetime(2026, 10, 1, 23, 0, tzinfo=zona).timestamp())
            self.assertEqual(
                tiempo.siguiente_ocurrencia_semanal(3, "23:00", plantilla + 60),
                esperado,
            )
        finally:
            tiempo.ZONA_HORARIA = anterior


if __name__ == "__main__":
    unittest.main()
