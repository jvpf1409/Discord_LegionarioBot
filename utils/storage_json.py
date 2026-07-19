"""
Capa de persistencia simple basada en un archivo JSON.
Guarda toda la información de eventos, inscritos, equipos y ganadores.
"""

import json
import os
import threading

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eventos.json")
_lock = threading.Lock()


def _asegurar_archivo():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"next_id": 1, "eventos": {}, "next_raid_id": 1, "raids": {}},
                f, ensure_ascii=False, indent=2,
            )


def cargar_datos() -> dict:
    _asegurar_archivo()
    with _lock:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("raids", {})
    data.setdefault("next_raid_id", 1)
    return data


def guardar_datos(data: dict):
    with _lock:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def crear_evento(
    titulo: str,
    descripcion: str,
    guild_id: int,
    canal_id: int,
    creado_por: int,
    fecha_hora_ts: int,
    tipo_inscripcion: str = "individual",  # individual | grupal
    canal_inscripciones_id: int | None = None,
    imagen_url: str | None = None,
) -> str:
    data = cargar_datos()
    evento_id = str(data["next_id"])
    data["next_id"] += 1
    data["eventos"][evento_id] = {
        "id": evento_id,
        "titulo": titulo,
        "descripcion": descripcion,
        "guild_id": guild_id,
        "canal_id": canal_id,
        "canal_inscripciones_id": canal_inscripciones_id,
        "mensaje_id": None,
        "tipo_inscripcion": tipo_inscripcion,
        "fecha_hora_ts": fecha_hora_ts,
        "imagen_url": imagen_url,
        "estado": "abierto",  # abierto | cerrado | finalizado
        "creado_por": creado_por,
        "participantes": [],   # (tipo individual) lista de dicts: user_id, nombre_discord, personaje
        "equipos": [],         # lista de equipos: {nombre_equipo, user_id, nombre_discord, integrantes: [...]}
        "ganador": None,       # indice de equipo o nombre
        "recordatorio_enviado": False,
    }
    guardar_datos(data)
    return evento_id


def obtener_evento(evento_id: str) -> dict | None:
    data = cargar_datos()
    return data["eventos"].get(str(evento_id))


def listar_eventos(guild_id: int, estado: str | None = None) -> list[dict]:
    data = cargar_datos()
    eventos = [e for e in data["eventos"].values() if e["guild_id"] == guild_id]
    if estado:
        eventos = [e for e in eventos if e["estado"] == estado]
    return sorted(eventos, key=lambda e: int(e["id"]))


def listar_todos_los_eventos() -> list[dict]:
    """Todos los eventos de todos los servidores (para re-registrar vistas al iniciar)."""
    data = cargar_datos()
    return sorted(data["eventos"].values(), key=lambda e: int(e["id"]))


def actualizar_evento(evento_id: str, **cambios):
    data = cargar_datos()
    evento_id = str(evento_id)
    if evento_id not in data["eventos"]:
        return None
    data["eventos"][evento_id].update(cambios)
    guardar_datos(data)
    return data["eventos"][evento_id]


def agregar_participante(evento_id: str, participante: dict) -> tuple[bool, str]:
    """Devuelve (ok, mensaje). Evita inscripciones duplicadas del mismo usuario."""
    data = cargar_datos()
    evento_id = str(evento_id)
    evento = data["eventos"].get(evento_id)
    if evento is None:
        return False, "El evento no existe."
    if evento["estado"] != "abierto":
        return False, "Las inscripciones para este evento están cerradas."
    for p in evento["participantes"]:
        if p["user_id"] == participante["user_id"]:
            return False, "Ya estás inscrito en este evento."
    evento["participantes"].append(participante)
    guardar_datos(data)
    return True, "Inscripción registrada correctamente."


def quitar_participante(evento_id: str, user_id: int) -> bool:
    data = cargar_datos()
    evento_id = str(evento_id)
    evento = data["eventos"].get(evento_id)
    if evento is None:
        return False
    antes = len(evento["participantes"])
    evento["participantes"] = [p for p in evento["participantes"] if p["user_id"] != user_id]
    guardar_datos(data)
    return len(evento["participantes"]) < antes


def agregar_equipo(evento_id: str, equipo: dict) -> tuple[bool, str]:
    """Registra un equipo completo (inscripción grupal). Devuelve (ok, mensaje)."""
    data = cargar_datos()
    evento_id = str(evento_id)
    evento = data["eventos"].get(evento_id)
    if evento is None:
        return False, "El evento no existe."
    if evento["estado"] != "abierto":
        return False, "Las inscripciones para este evento están cerradas."
    for e in evento["equipos"]:
        if e["user_id"] == equipo["user_id"]:
            return False, "Ya inscribiste un equipo en este evento."
    evento["equipos"].append(equipo)
    guardar_datos(data)
    return True, "Equipo inscrito correctamente."


def quitar_equipo(evento_id: str, user_id: int) -> bool:
    data = cargar_datos()
    evento_id = str(evento_id)
    evento = data["eventos"].get(evento_id)
    if evento is None:
        return False
    antes = len(evento["equipos"])
    evento["equipos"] = [e for e in evento["equipos"] if e["user_id"] != user_id]
    guardar_datos(data)
    return len(evento["equipos"]) < antes


def crear_raid(
    titulo: str,
    descripcion: str,
    guild_id: int,
    canal_id: int,
    fecha_hora_ts: int,
    creado_por: int,
    canal_inscripciones_id: int | None = None,
    imagen_url: str | None = None,
) -> str:
    data = cargar_datos()
    raid_id = str(data["next_raid_id"])
    data["next_raid_id"] += 1
    data["raids"][raid_id] = {
        "id": raid_id,
        "titulo": titulo,
        "descripcion": descripcion,
        "guild_id": guild_id,
        "canal_id": canal_id,
        "canal_inscripciones_id": canal_inscripciones_id,
        "mensaje_id": None,
        "fecha_hora_ts": fecha_hora_ts,
        "imagen_url": imagen_url,
        "estado": "abierto",  # abierto | cerrado | cancelado
        "creado_por": creado_por,
        "inscritos": [],  # {user_id, nombre_discord, clase, especializacion, rol}
        "recordatorio_enviado": False,
    }
    guardar_datos(data)
    return raid_id


def obtener_raid(raid_id: str) -> dict | None:
    data = cargar_datos()
    return data["raids"].get(str(raid_id))


def listar_raids(guild_id: int, estado: str | None = None) -> list[dict]:
    data = cargar_datos()
    raids = [r for r in data["raids"].values() if r["guild_id"] == guild_id]
    if estado:
        raids = [r for r in raids if r["estado"] == estado]
    return sorted(raids, key=lambda r: int(r["id"]))


def listar_todas_las_raids() -> list[dict]:
    """Todas las raids de todos los servidores (para re-registrar vistas al iniciar)."""
    data = cargar_datos()
    return sorted(data["raids"].values(), key=lambda r: int(r["id"]))


def actualizar_raid(raid_id: str, **cambios):
    data = cargar_datos()
    raid_id = str(raid_id)
    if raid_id not in data["raids"]:
        return None
    data["raids"][raid_id].update(cambios)
    guardar_datos(data)
    return data["raids"][raid_id]


def inscribir_en_raid(raid_id: str, inscrito: dict) -> tuple[bool, str]:
    """Registra la inscripción; si el usuario ya estaba inscrito, actualiza su clase/spec."""
    data = cargar_datos()
    raid_id = str(raid_id)
    raid = data["raids"].get(raid_id)
    if raid is None:
        return False, "La raid no existe."
    if raid["estado"] != "abierto":
        return False, "Las inscripciones para esta raid están cerradas."
    raid["inscritos"] = [i for i in raid["inscritos"] if i["user_id"] != inscrito["user_id"]]
    raid["inscritos"].append(inscrito)
    guardar_datos(data)
    return True, "Inscripción registrada correctamente."


def quitar_de_raid(raid_id: str, user_id: int) -> bool:
    data = cargar_datos()
    raid_id = str(raid_id)
    raid = data["raids"].get(raid_id)
    if raid is None:
        return False
    antes = len(raid["inscritos"])
    raid["inscritos"] = [i for i in raid["inscritos"] if i["user_id"] != user_id]
    guardar_datos(data)
    return len(raid["inscritos"]) < antes
