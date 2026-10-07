import io
import unittest

from PIL import Image

from utils.banner_ganador import renderizar_banner_ganador


def _imagen(size, color="#113355") -> bytes:
    data = io.BytesIO()
    Image.new("RGB", size, color).save(data, "PNG")
    return data.getvalue()


class BannerGanadorTests(unittest.TestCase):
    def test_banner_ajusta_el_fondo_a_las_dimensiones_esperadas(self):
        output = renderizar_banner_ganador(_imagen((1200, 600)))

        with Image.open(output) as image:
            self.assertEqual(image.size, (900, 500))
            self.assertEqual(image.format, "PNG")
            # Sin avatar ni equipo, el fondo queda limpio: sin texto encima.
            self.assertEqual(image.getpixel((450, 119)), image.getpixel((100, 119)))
            self.assertEqual(image.getpixel((450, 345)), image.getpixel((100, 345)))

    def test_banner_acepta_avatar_no_cuadrado(self):
        output = renderizar_banner_ganador(
            _imagen((900, 500)), avatar_data=_imagen((64, 96), "#ff00aa")
        )

        with Image.open(output) as image:
            self.assertEqual(image.size, (900, 500))
            self.assertEqual(image.mode, "RGB")
            self.assertNotEqual(image.getpixel((450, 119)), image.getpixel((100, 119)))

    def test_banner_grupal_escribe_nombre_en_lugar_del_avatar(self):
        output = renderizar_banner_ganador(_imagen((900, 500)), nombre_equipo="Los Murlocs")

        with Image.open(output) as image:
            zona_nombre = image.crop((300, 50, 600, 190))
            colores = zona_nombre.getcolors(maxcolors=900 * 500)
            self.assertGreater(len(colores), 1)

    def test_fondo_invalido_lanza_error(self):
        with self.assertRaises(OSError):
            renderizar_banner_ganador(b"esto no es una imagen")


if __name__ == "__main__":
    unittest.main()
