"""Copia iconos convertidos por WoW.export a una carpeta local.

WoW.export debe exportar las texturas con la conversión BLP -> PNG activada.
El script busca automáticamente una carpeta ``Interface/Icons`` dentro de la
ruta indicada y también acepta una carpeta que ya contenga directamente los
iconos.

Ejemplos:
    python scripts/extraer_iconos_wow_export.py "D:/wow.export/Export"
    python scripts/extraer_iconos_wow_export.py "D:/wow.export/Export" --filtro "spell_*"
    python scripts/extraer_iconos_wow_export.py "D:/wow.export/Export" --lista iconos.txt
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import shutil
import sys
from pathlib import Path


EXTENSIONES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def encontrar_carpeta_iconos(origen: Path) -> Path:
    """Devuelve Interface/Icons o, si no existe, la propia ruta de origen."""
    if not origen.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de origen: {origen}")

    if origen.name.casefold() == "icons":
        return origen

    candidatas = [
        ruta
        for ruta in origen.rglob("*")
        if ruta.is_dir()
        and ruta.name.casefold() == "icons"
        and ruta.parent.name.casefold() == "interface"
    ]
    if not candidatas:
        return origen
    return min(candidatas, key=lambda ruta: (len(ruta.parts), str(ruta).casefold()))


def cargar_lista(ruta: Path) -> set[str]:
    """Carga nombres o rutas; ignora líneas vacías y comentarios con #."""
    nombres: set[str] = set()
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        valor = linea.strip().replace("\\", "/")
        if not valor or valor.startswith("#"):
            continue
        nombres.add(Path(valor).stem.casefold())
    return nombres


def seleccionar_iconos(
    carpeta: Path, filtros: list[str], nombres: set[str] | None
) -> list[Path]:
    filtros_normalizados = [f.casefold() for f in filtros]
    resultado = []
    for ruta in carpeta.rglob("*"):
        if not ruta.is_file() or ruta.suffix.casefold() not in EXTENSIONES:
            continue
        nombre = ruta.stem.casefold()
        archivo = ruta.name.casefold()
        if nombres is not None and nombre not in nombres:
            continue
        if filtros_normalizados and not any(
            fnmatch.fnmatch(nombre, patron) or fnmatch.fnmatch(archivo, patron)
            for patron in filtros_normalizados
        ):
            continue
        resultado.append(ruta)
    return sorted(resultado, key=lambda ruta: str(ruta).casefold())


def copiar_iconos(
    iconos: list[Path], destino: Path, sobrescribir: bool, simulacion: bool,
    nombres_salida: dict[str, str] | None = None,
) -> tuple[int, int]:
    copiados = omitidos = 0
    if not simulacion:
        destino.mkdir(parents=True, exist_ok=True)

    for origen in iconos:
        nombre_salida = (nombres_salida or {}).get(origen.stem.casefold(), origen.name.lower())
        salida = destino / nombre_salida
        if salida.exists() and not sobrescribir:
            print(f"OMITIDO  {salida.name} (ya existe)")
            omitidos += 1
            continue
        print(f"{'COPIARÍA' if simulacion else 'COPIADO'} {origen} -> {salida}")
        if not simulacion:
            shutil.copy2(origen, salida)
        copiados += 1
    return copiados, omitidos


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extrae imágenes de Interface/Icons exportadas por WoW.export."
    )
    parser.add_argument("origen", type=Path, help="Carpeta Export de WoW.export")
    parser.add_argument(
        "--destino",
        type=Path,
        default=Path("assets/wow-icons"),
        help="Carpeta de salida (predeterminado: assets/wow-icons)",
    )
    parser.add_argument(
        "--filtro",
        action="append",
        default=[],
        metavar="PATRÓN",
        help='Patrón de nombre; se puede repetir (ej.: "spell_*frost*")',
    )
    parser.add_argument(
        "--lista",
        type=Path,
        help="TXT con un nombre o ruta de icono por línea, con o sin extensión",
    )
    parser.add_argument(
        "--mapa", type=Path,
        help="CSV generado por generar_mapa_especializaciones.py",
    )
    parser.add_argument("--sobrescribir", action="store_true")
    parser.add_argument("--simular", action="store_true", help="No escribe archivos")
    return parser


def main() -> int:
    args = crear_parser().parse_args()
    try:
        carpeta = encontrar_carpeta_iconos(args.origen.resolve())
        nombres_salida = None
        if args.mapa:
            with args.mapa.open("r", encoding="utf-8-sig", newline="") as archivo:
                nombres_salida = {
                    fila["file_data_id"].casefold(): fila["archivo"]
                    for fila in csv.DictReader(archivo, delimiter=";")
                }
            nombres = set(nombres_salida)
        else:
            nombres = cargar_lista(args.lista) if args.lista else None
        iconos = seleccionar_iconos(carpeta, args.filtro, nombres)
    except (OSError, UnicodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not iconos:
        print(
            "No se encontraron imágenes. En WoW.export exporta Interface/Icons "
            "con la conversión BLP -> PNG activada.",
            file=sys.stderr,
        )
        return 2

    copiados, omitidos = copiar_iconos(
        iconos, args.destino.resolve(), args.sobrescribir, args.simular, nombres_salida
    )
    print(f"\nEncontrados: {len(iconos)} | Copiados: {copiados} | Omitidos: {omitidos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
