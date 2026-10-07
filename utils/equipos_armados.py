"""
Lógica del tipo de inscripción "armado": las personas se inscriben de forma
individual con su rol y la organización arma después los equipos.

Cada equipo es de 1 tanque, 1 healer y 3 DPS. Los cupos dependen de la
cantidad de equipos; quien se inscribe con el rol lleno queda como suplente.
Titulares y suplentes no se guardan: se calculan por orden de inscripción,
así una baja o una ampliación de equipos promueve sola al primer suplente.
"""

from __future__ import annotations

import csv
import io

CUPOS_POR_EQUIPO = {"tank": 1, "healer": 1, "dps": 3}
CATEGORIAS = ("tank", "healer", "dps")
NOMBRES_CATEGORIA = {"tank": "Tank", "healer": "Healer", "dps": "DPS"}
EMOJIS_CATEGORIA = {"tank": "🛡️", "healer": "➕", "dps": "⚔️"}
MAX_EQUIPOS = 8


def categoria(rol: str) -> str:
    """Agrupa melee y ranged como DPS."""
    return rol if rol in ("tank", "healer") else "dps"


def cupos(cantidad_equipos: int) -> dict[str, int]:
    return {c: n * cantidad_equipos for c, n in CUPOS_POR_EQUIPO.items()}


def repartir(evento: dict) -> dict[str, tuple[list[dict], list[dict]]]:
    """Por categoría: (titulares, suplentes) según el orden de inscripción."""
    limites = cupos(evento.get("cantidad_equipos", 1))
    resultado = {}
    for c in CATEGORIAS:
        inscritos = [p for p in evento["participantes"] if categoria(p["rol"]) == c]
        resultado[c] = (inscritos[: limites[c]], inscritos[limites[c]:])
    return resultado


def promovidos(antes: dict, despues: dict) -> list[tuple[dict, str]]:
    """Suplentes que pasaron a titulares entre dos versiones del evento."""
    titulares_antes = {
        p["user_id"] for titulares, _ in repartir(antes).values() for p in titulares
    }
    return [
        (p, c)
        for c, (titulares, _) in repartir(despues).items()
        for p in titulares
        if p["user_id"] not in titulares_antes
        and any(q["user_id"] == p["user_id"] for q in antes["participantes"])
    ]


def estado_inscrito(evento: dict, user_id: int) -> tuple[str, int, int] | None:
    """
    Devuelve (categoria, posicion, cupo) del usuario. Si es titular, la
    posición va de 1 al cupo; si es suplente, ``posicion`` es negativa
    (-1 = primer suplente). ``None`` si no está inscrito.
    """
    limites = cupos(evento.get("cantidad_equipos", 1))
    for c, (titulares, suplentes) in repartir(evento).items():
        for i, p in enumerate(titulares, start=1):
            if p["user_id"] == user_id:
                return c, i, limites[c]
        for i, p in enumerate(suplentes, start=1):
            if p["user_id"] == user_id:
                return c, -i, limites[c]
    return None


def resumen_cupos(evento: dict) -> str:
    limites = cupos(evento.get("cantidad_equipos", 1))
    partes = []
    for c, (titulares, suplentes) in repartir(evento).items():
        texto = f"{EMOJIS_CATEGORIA[c]} {NOMBRES_CATEGORIA[c]} {len(titulares)}/{limites[c]}"
        if suplentes:
            texto += f" (+{len(suplentes)} suplentes)"
        partes.append(texto)
    return " · ".join(partes)


def parsear_numero(texto: str, minimo: int, maximo: int) -> int | None:
    """Acepta '639', '2850', '2,850' o '2850.4'. Devuelve entero o None si no es válido."""
    limpio = texto.strip().replace(" ", "")
    if "," in limpio and "." not in limpio and len(limpio.split(",")[-1]) == 3:
        limpio = limpio.replace(",", "")  # separador de miles
    limpio = limpio.replace(",", ".")
    try:
        valor = round(float(limpio))
    except ValueError:
        return None
    if not minimo <= valor <= maximo:
        return None
    return valor


def promedios(integrantes: list[dict]) -> tuple[int, int] | None:
    """(ilvl, IO) promedio de un equipo, o None si está vacío."""
    if not integrantes:
        return None
    ilvl = round(sum(i["ilvl"] for i in integrantes) / len(integrantes))
    io = round(sum(i["io"] for i in integrantes) / len(integrantes))
    return ilvl, io


def faltantes(borrador: dict) -> list[str]:
    """Roles que le faltan a un equipo del borrador ({'tank', 'healer', 'dps': [...]})."""
    falta = []
    if borrador.get("tank") is None:
        falta.append("tank")
    if borrador.get("healer") is None:
        falta.append("healer")
    if len(borrador.get("dps", [])) < CUPOS_POR_EQUIPO["dps"]:
        falta.append(f"{CUPOS_POR_EQUIPO['dps'] - len(borrador.get('dps', []))} DPS")
    return falta


def construir_equipos(borradores: list[dict], participantes: list[dict]) -> list[dict]:
    """
    Convierte los borradores del panel (ids de usuario por rol) en equipos
    con el mismo formato que los grupales, para que ``registrar_ganador`` y
    el banner del ganador funcionen igual.
    """
    por_id = {p["user_id"]: p for p in participantes}
    equipos = []
    for numero, borrador in enumerate(borradores, start=1):
        ids = [borrador["tank"], borrador["healer"], *borrador["dps"]]
        integrantes = []
        for user_id in ids:
            p = por_id[user_id]
            integrantes.append({
                "rol": NOMBRES_CATEGORIA[categoria(p["rol"])],
                "personaje": p["personaje"],
                "user_id": p["user_id"],
                "clase": p["clase"],
                "especializacion": p["especializacion"],
                "ilvl": p["ilvl"],
                "io": p["io"],
            })
        equipos.append({
            "numero": numero,
            "nombre_equipo": f"Equipo {numero}",
            "integrantes": integrantes,
        })
    return equipos


def borradores_desde_equipos(equipos: list[dict], participantes: list[dict]) -> list[dict]:
    """Inverso de ``construir_equipos``: carga en el panel los equipos ya publicados."""
    vigentes = {p["user_id"] for p in participantes}
    borradores = []
    for equipo in equipos:
        borrador = {"tank": None, "healer": None, "dps": []}
        for i in equipo["integrantes"]:
            if i.get("user_id") not in vigentes:
                continue  # se dio de baja después de publicar
            if i["rol"] == "Tank":
                borrador["tank"] = i["user_id"]
            elif i["rol"] == "Healer":
                borrador["healer"] = i["user_id"]
            else:
                borrador["dps"].append(i["user_id"])
        borradores.append(borrador)
    return borradores


def inscritos_csv(evento: dict) -> str:
    """Inscritos ordenados por rol (titulares primero) en formato CSV."""
    salida = io.StringIO()
    writer = csv.writer(salida, lineterminator="\n")
    writer.writerow(["Rol", "Personaje", "Clase", "Especialización", "Ilvl", "IO", "Discord", "Estado"])
    for c, (titulares, suplentes) in repartir(evento).items():
        for lista, estado in ((titulares, "Titular"), (suplentes, "Suplente")):
            for p in lista:
                writer.writerow([
                    NOMBRES_CATEGORIA[c], p["personaje"], p["clase"], p["especializacion"],
                    p["ilvl"], p["io"], p["nombre_discord"], estado,
                ])
    return salida.getvalue()


def texto_para_ia(evento: dict) -> str:
    """Inscritos + instrucción lista para pegar en una IA que arme los equipos."""
    cantidad = evento.get("cantidad_equipos", 1)
    equipos = f"{cantidad} equipo" if cantidad == 1 else f"{cantidad} equipos"
    return (
        f"Evento: {evento['titulo']}\n"
        f"Formato: {equipos} de 1 Tank, 1 Healer y 3 DPS\n"
        "\n"
        "Inscritos (CSV):\n"
        f"{inscritos_csv(evento)}"
        "\n"
        "Instrucciones:\n"
        f"Forma {equipos} de exactamente 1 Tank, 1 Healer y 3 DPS con las "
        "personas de la lista anterior.\n"
        "- Cada persona juega el rol con el que se inscribió y puede estar en un solo equipo.\n"
        "- Usa solo a quienes tienen Estado \"Titular\". Recurre a un \"Suplente\" únicamente "
        "si falta gente de un rol, y dilo explícitamente.\n"
        "- El objetivo es que los equipos queden lo más parejos posible: primero, que el "
        "promedio de IO de cada equipo sea similar; después, que el promedio de item "
        "level también lo sea.\n"
        "- No inventes personas ni cambies sus datos.\n"
        "\n"
        "Responde con:\n"
        "1. Una tabla por equipo (Equipo 1, Equipo 2, …) con las columnas Rol, Personaje, "
        "Discord, Ilvl e IO, y debajo el promedio de IO e item level del equipo.\n"
        "2. La diferencia de IO promedio entre el equipo más alto y el más bajo.\n"
        "3. Los suplentes que quedaron fuera, si los hay.\n"
    )


def dividir_en_campos(lineas: list[str], limite: int = 1024) -> list[str]:
    """Agrupa líneas en bloques que respetan el límite de un campo de embed."""
    bloques, actual = [], ""
    for linea in lineas:
        candidato = f"{actual}\n{linea}" if actual else linea
        if len(candidato) > limite:
            bloques.append(actual)
            actual = linea[:limite]
        else:
            actual = candidato
    if actual:
        bloques.append(actual)
    return bloques
