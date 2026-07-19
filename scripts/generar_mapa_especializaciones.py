"""Genera FileDataID y nombres de icono desde ChrSpecialization.csv."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

NOMBRES = {
    62:"mago_arcano",63:"mago_fuego",64:"mago_escarcha",65:"paladin_sagrado",66:"paladin_proteccion",70:"paladin_reprension",
    71:"guerrero_armas",72:"guerrero_furia",73:"guerrero_proteccion",102:"druida_equilibrio",103:"druida_feral",104:"druida_guardian",105:"druida_restauracion",
    250:"caballero_de_la_muerte_sangre",251:"caballero_de_la_muerte_escarcha",252:"caballero_de_la_muerte_profano",
    253:"cazador_bestias",254:"cazador_punteria",255:"cazador_supervivencia",256:"sacerdote_disciplina",257:"sacerdote_sagrado",258:"sacerdote_sombras",
    259:"picaro_asesinato",260:"picaro_fuera_de_la_ley",261:"picaro_sutileza",262:"chaman_elemental",263:"chaman_mejora",264:"chaman_restauracion",
    265:"brujo_afliccion",266:"brujo_demonologia",267:"brujo_destruccion",268:"monje_maestro_cervecero",269:"monje_viajero_del_viento",270:"monje_tejedor_de_niebla",
    577:"cazador_de_demonios_asolamiento",581:"cazador_de_demonios_venganza",1467:"evocador_devastacion",1468:"evocador_preservacion",1473:"evocador_aumento",
}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--mapa", type=Path, default=Path("data/iconos_especializaciones.csv"))
    parser.add_argument("--ids", type=Path, default=Path("data/iconos_filedataids.txt"))
    parser.add_argument("--listfile", type=Path, help="listfile.txt de la caché de WoW.export")
    parser.add_argument("--seleccion", type=Path, default=Path("data/iconos_seleccion_wow_export.txt"))
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8-sig", newline="") as archivo:
        origen = csv.DictReader(archivo, delimiter=";")
        filas = [{"file_data_id": f["SpellIconFileID"], "archivo": NOMBRES[int(f["ID"])] + ".png", "spec_id": f["ID"], "nombre": f["Name_lang"]}
                 for f in origen if int(f["ID"]) in NOMBRES]
    if len(filas) != len(NOMBRES):
        raise SystemExit(f"Se esperaban {len(NOMBRES)} especializaciones y se encontraron {len(filas)}")
    filas.sort(key=lambda f: f["archivo"])
    args.mapa.parent.mkdir(parents=True, exist_ok=True)
    with args.mapa.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=filas[0], delimiter=";")
        escritor.writeheader(); escritor.writerows(filas)
    args.ids.parent.mkdir(parents=True, exist_ok=True)
    args.ids.write_text("\n".join(f["file_data_id"] for f in filas) + "\n", encoding="utf-8")
    if args.listfile:
        ids = {f["file_data_id"] for f in filas}
        rutas = {}
        with args.listfile.open(encoding="utf-8", errors="replace") as archivo:
            for linea in archivo:
                file_id, separador, ruta = linea.rstrip().partition(";")
                if separador and file_id in ids:
                    rutas[file_id] = ruta.replace("\\", "/").lower()
        faltantes = ids - rutas.keys()
        if faltantes:
            raise SystemExit(f"No se encontraron {len(faltantes)} IDs en la listfile: {sorted(faltantes)}")
        args.seleccion.parent.mkdir(parents=True, exist_ok=True)
        args.seleccion.write_text(
            "\n".join(f"{rutas[f['file_data_id']]} [{f['file_data_id']}]" for f in filas) + "\n",
            encoding="utf-8",
        )
        print(f"Selección pegable guardada en {args.seleccion}")
    print(f"Generados {len(filas)} iconos en {args.mapa} y {args.ids}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
