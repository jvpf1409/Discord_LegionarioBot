import unittest

from utils.recordatorios import (
    accion_recordatorio_extra,
    campos_recordatorio_extra,
    formatear_duracion,
    parsear_duracion,
)

HORA = 3600


class ParsearDuracionTests(unittest.TestCase):
    def test_formatos_validos(self):
        self.assertEqual(parsear_duracion("2h"), 120)
        self.assertEqual(parsear_duracion("90m"), 90)
        self.assertEqual(parsear_duracion("1d"), 1440)
        self.assertEqual(parsear_duracion("1d12h"), 2160)
        self.assertEqual(parsear_duracion(" 1H 30M "), 90)
        self.assertEqual(parsear_duracion("0"), 0)

    def test_formatos_invalidos(self):
        for texto in ("", "2", "dos horas", "1h1d", "2m", "31d", "30m", "-1h"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                parsear_duracion(texto)

    def test_formatear(self):
        self.assertEqual(formatear_duracion(2160), "1 día 12 h")
        self.assertEqual(formatear_duracion(90), "1 h 30 min")
        self.assertEqual(formatear_duracion(2 * 1440), "2 días")


class AccionRecordatorioExtraTests(unittest.TestCase):
    def _item(self, **cambios):
        item = {"fecha_hora_ts": 100 * HORA, "mensaje_id": 1, "recordatorio_extra_min": 24 * 60}
        item.update(cambios)
        return item

    def test_envia_dentro_de_la_ventana(self):
        self.assertIsNone(accion_recordatorio_extra(self._item(), 75 * HORA))
        self.assertEqual(accion_recordatorio_extra(self._item(), 76 * HORA), "enviar")

    def test_no_repite_ni_envia_sin_configurar(self):
        self.assertIsNone(accion_recordatorio_extra(self._item(recordatorio_extra_enviado=True), 80 * HORA))
        self.assertIsNone(accion_recordatorio_extra(self._item(recordatorio_extra_min=None), 80 * HORA))
        self.assertIsNone(accion_recordatorio_extra(self._item(mensaje_id=None), 80 * HORA))

    def test_descarta_si_ya_toca_el_de_30_minutos(self):
        self.assertEqual(accion_recordatorio_extra(self._item(), 100 * HORA - 600), "descartar")
        self.assertIsNone(accion_recordatorio_extra(self._item(), 100 * HORA + 1))

    def test_extra_menor_a_30_minutos_es_independiente(self):
        item = self._item(recordatorio_extra_min=10)
        self.assertIsNone(accion_recordatorio_extra(item, 100 * HORA - 1200))
        self.assertEqual(accion_recordatorio_extra(item, 100 * HORA - 300), "enviar")

    def test_campos_omiten_si_la_ventana_ya_paso(self):
        inicio = 100 * HORA
        self.assertEqual(
            campos_recordatorio_extra(24 * 60, inicio, 50 * HORA),
            {"recordatorio_extra_min": 1440, "recordatorio_extra_enviado": False},
        )
        self.assertTrue(campos_recordatorio_extra(24 * 60, inicio, 90 * HORA)["recordatorio_extra_enviado"])
        self.assertIsNone(campos_recordatorio_extra(0, inicio, 50 * HORA)["recordatorio_extra_min"])


if __name__ == "__main__":
    unittest.main()
