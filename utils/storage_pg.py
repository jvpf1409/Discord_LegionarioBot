"""
Capa de persistencia sobre Postgres (para producción en Render, donde el
filesystem no es persistente entre deploys). Cada evento se guarda como un
único registro JSONB, para no tener que mantener un esquema relacional
mientras la forma del evento sigue evolucionando.

Se activa automáticamente cuando existe la variable de entorno DATABASE_URL
(ver utils/storage.py). Requiere el paquete "psycopg[binary]".
"""

import os

import psycopg
from psycopg.types.json import Json

DATABASE_URL = os.environ["DATABASE_URL"]


def _conectar():
    # prepare_threshold=None: el pooler de Supabase en modo "transaction" no
    # soporta prepared statements entre transacciones (cada una puede caer en
    # una conexión física distinta), así que los desactivamos por completo.
    return psycopg.connect(
        DATABASE_URL,
        row_factory=psycopg.rows.dict_row,
        autocommit=True,
        prepare_threshold=None,
    )


def _asegurar_tabla():
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eventos (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                data JSONB NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raids (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                data JSONB NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS formularios (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                data JSONB NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listas_asistencia (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                fecha_hora_ts BIGINT NOT NULL,
                data JSONB NOT NULL
            )
            """
        )


_asegurar_tabla()


def _fila_a_lista_asistencia(fila) -> dict:
    lista = dict(fila["data"])
    lista["id"] = str(fila["id"])
    return lista


def crear_lista_asistencia(guild_id: int, canal_voz_id: int, canal_voz_nombre: str,
                           canal_publicacion_id: int, creado_por: int,
                           fecha_hora_ts: int, miembros: list[dict]) -> str:
    data = {
        "guild_id": guild_id, "canal_voz_id": canal_voz_id,
        "canal_voz_nombre": canal_voz_nombre,
        "canal_publicacion_id": canal_publicacion_id, "creado_por": creado_por,
        "fecha_hora_ts": fecha_hora_ts, "miembros": miembros,
    }
    with _conectar() as conn:
        fila = conn.execute(
            "INSERT INTO listas_asistencia (guild_id, fecha_hora_ts, data) VALUES (%s, %s, %s) RETURNING id",
            (guild_id, fecha_hora_ts, Json(data)),
        ).fetchone()
    return str(fila["id"])


def obtener_lista_asistencia(lista_id: str, guild_id: int) -> dict | None:
    try:
        identificador = int(lista_id)
    except (TypeError, ValueError):
        return None
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT id, data FROM listas_asistencia WHERE id = %s AND guild_id = %s",
            (identificador, guild_id),
        ).fetchone()
    return _fila_a_lista_asistencia(fila) if fila else None


def actualizar_lista_asistencia(lista_id: str, guild_id: int, **cambios) -> dict | None:
    try:
        identificador = int(lista_id)
    except (TypeError, ValueError):
        return None
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM listas_asistencia WHERE id = %s AND guild_id = %s FOR UPDATE",
                (identificador, guild_id),
            ).fetchone()
            if fila is None:
                return None
            data = dict(fila["data"])
            data.update(cambios)
            conn.execute(
                """UPDATE listas_asistencia
                   SET data = %s, fecha_hora_ts = %s
                   WHERE id = %s AND guild_id = %s""",
                (Json(data), data["fecha_hora_ts"], identificador, guild_id),
            )
    return obtener_lista_asistencia(lista_id, guild_id)


def listar_listas_asistencia(guild_id: int, limite: int = 10) -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT id, data FROM listas_asistencia WHERE guild_id = %s ORDER BY fecha_hora_ts DESC, id DESC LIMIT %s",
            (guild_id, limite),
        ).fetchall()
    return [_fila_a_lista_asistencia(fila) for fila in filas]


def _fila_a_evento(fila) -> dict:
    evento = dict(fila["data"])
    evento["id"] = str(fila["id"])
    return evento


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
    data = {
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
    with _conectar() as conn:
        fila = conn.execute(
            "INSERT INTO eventos (guild_id, data) VALUES (%s, %s) RETURNING id",
            (guild_id, Json(data)),
        ).fetchone()
    return str(fila["id"])


def obtener_evento(evento_id: str) -> dict | None:
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT id, data FROM eventos WHERE id = %s", (int(evento_id),)
        ).fetchone()
    return _fila_a_evento(fila) if fila else None


def listar_eventos(guild_id: int, estado: str | None = None) -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT id, data FROM eventos WHERE guild_id = %s ORDER BY id", (guild_id,)
        ).fetchall()
    eventos = [_fila_a_evento(f) for f in filas]
    if estado:
        eventos = [e for e in eventos if e["estado"] == estado]
    return eventos


def listar_todos_los_eventos() -> list[dict]:
    """Todos los eventos de todos los servidores (para re-registrar vistas al iniciar)."""
    with _conectar() as conn:
        filas = conn.execute("SELECT id, data FROM eventos ORDER BY id").fetchall()
    return [_fila_a_evento(f) for f in filas]


def actualizar_evento(evento_id: str, **cambios):
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM eventos WHERE id = %s FOR UPDATE", (int(evento_id),)
            ).fetchone()
            if fila is None:
                return None
            data = dict(fila["data"])
            data.update(cambios)
            conn.execute("UPDATE eventos SET data = %s WHERE id = %s", (Json(data), int(evento_id)))
    return obtener_evento(evento_id)


def eliminar_evento(evento_id: str) -> bool:
    """Borra el evento por completo (irreversible). Devuelve True si existía."""
    with _conectar() as conn:
        cursor = conn.execute("DELETE FROM eventos WHERE id = %s", (int(evento_id),))
    return cursor.rowcount > 0


def agregar_participante(evento_id: str, participante: dict) -> tuple[bool, str]:
    """Devuelve (ok, mensaje). Evita inscripciones duplicadas del mismo usuario."""
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM eventos WHERE id = %s FOR UPDATE", (int(evento_id),)
            ).fetchone()
            if fila is None:
                return False, "El evento no existe."
            data = dict(fila["data"])
            if data["estado"] != "abierto":
                return False, "Las inscripciones para este evento están cerradas."
            for p in data["participantes"]:
                if p["user_id"] == participante["user_id"]:
                    return False, "Ya estás inscrito en este evento."
            data["participantes"].append(participante)
            conn.execute("UPDATE eventos SET data = %s WHERE id = %s", (Json(data), int(evento_id)))
    return True, "Inscripción registrada correctamente."


def quitar_participante(evento_id: str, user_id: int) -> bool:
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM eventos WHERE id = %s FOR UPDATE", (int(evento_id),)
            ).fetchone()
            if fila is None:
                return False
            data = dict(fila["data"])
            antes = len(data["participantes"])
            data["participantes"] = [p for p in data["participantes"] if p["user_id"] != user_id]
            conn.execute("UPDATE eventos SET data = %s WHERE id = %s", (Json(data), int(evento_id)))
    return len(data["participantes"]) < antes


def agregar_equipo(evento_id: str, equipo: dict) -> tuple[bool, str]:
    """Registra un equipo completo (inscripción grupal). Devuelve (ok, mensaje)."""
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM eventos WHERE id = %s FOR UPDATE", (int(evento_id),)
            ).fetchone()
            if fila is None:
                return False, "El evento no existe."
            data = dict(fila["data"])
            if data["estado"] != "abierto":
                return False, "Las inscripciones para este evento están cerradas."
            for e in data["equipos"]:
                if e["user_id"] == equipo["user_id"]:
                    return False, "Ya inscribiste un equipo en este evento."
            data["equipos"].append(equipo)
            conn.execute("UPDATE eventos SET data = %s WHERE id = %s", (Json(data), int(evento_id)))
    return True, "Equipo inscrito correctamente."


def quitar_equipo(evento_id: str, user_id: int) -> bool:
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM eventos WHERE id = %s FOR UPDATE", (int(evento_id),)
            ).fetchone()
            if fila is None:
                return False
            data = dict(fila["data"])
            antes = len(data["equipos"])
            data["equipos"] = [e for e in data["equipos"] if e["user_id"] != user_id]
            conn.execute("UPDATE eventos SET data = %s WHERE id = %s", (Json(data), int(evento_id)))
    return len(data["equipos"]) < antes


def _fila_a_raid(fila) -> dict:
    raid = dict(fila["data"])
    raid["id"] = str(fila["id"])
    return raid


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
    data = {
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
    with _conectar() as conn:
        fila = conn.execute(
            "INSERT INTO raids (guild_id, data) VALUES (%s, %s) RETURNING id",
            (guild_id, Json(data)),
        ).fetchone()
    return str(fila["id"])


def obtener_raid(raid_id: str) -> dict | None:
    with _conectar() as conn:
        fila = conn.execute("SELECT id, data FROM raids WHERE id = %s", (int(raid_id),)).fetchone()
    return _fila_a_raid(fila) if fila else None


def listar_raids(guild_id: int, estado: str | None = None) -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT id, data FROM raids WHERE guild_id = %s ORDER BY id", (guild_id,)
        ).fetchall()
    raids = [_fila_a_raid(f) for f in filas]
    if estado:
        raids = [r for r in raids if r["estado"] == estado]
    return raids


def listar_todas_las_raids() -> list[dict]:
    """Todas las raids de todos los servidores (para re-registrar vistas al iniciar)."""
    with _conectar() as conn:
        filas = conn.execute("SELECT id, data FROM raids ORDER BY id").fetchall()
    return [_fila_a_raid(f) for f in filas]


def actualizar_raid(raid_id: str, **cambios):
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM raids WHERE id = %s FOR UPDATE", (int(raid_id),)
            ).fetchone()
            if fila is None:
                return None
            data = dict(fila["data"])
            data.update(cambios)
            conn.execute("UPDATE raids SET data = %s WHERE id = %s", (Json(data), int(raid_id)))
    return obtener_raid(raid_id)


def eliminar_raid(raid_id: str) -> bool:
    """Borra una raid por completo. Devuelve True si existía."""
    with _conectar() as conn:
        resultado = conn.execute(
            "DELETE FROM raids WHERE id = %s", (int(raid_id),)
        )
    return resultado.rowcount > 0


def inscribir_en_raid(raid_id: str, inscrito: dict) -> tuple[bool, str]:
    """Registra la inscripción; si el usuario ya estaba inscrito, actualiza su clase/spec."""
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM raids WHERE id = %s FOR UPDATE", (int(raid_id),)
            ).fetchone()
            if fila is None:
                return False, "La raid no existe."
            data = dict(fila["data"])
            if data["estado"] != "abierto":
                return False, "Las inscripciones para esta raid están cerradas."
            data["inscritos"] = [i for i in data["inscritos"] if i["user_id"] != inscrito["user_id"]]
            data["inscritos"].append(inscrito)
            conn.execute("UPDATE raids SET data = %s WHERE id = %s", (Json(data), int(raid_id)))
    return True, "Inscripción registrada correctamente."


def quitar_de_raid(raid_id: str, user_id: int) -> bool:
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute(
                "SELECT data FROM raids WHERE id = %s FOR UPDATE", (int(raid_id),)
            ).fetchone()
            if fila is None:
                return False
            data = dict(fila["data"])
            antes = len(data["inscritos"])
            data["inscritos"] = [i for i in data["inscritos"] if i["user_id"] != user_id]
            conn.execute("UPDATE raids SET data = %s WHERE id = %s", (Json(data), int(raid_id)))
    return len(data["inscritos"]) < antes


# Formularios PvP
def _fila_a_formulario(fila) -> dict:
    formulario = dict(fila["data"])
    formulario["id"] = str(fila["id"])
    return formulario


def crear_formulario_pvp(titulo: str, descripcion: str, guild_id: int, canal_id: int, creado_por: int) -> str:
    data = {
        "tipo": "pvp", "titulo": titulo, "descripcion": descripcion,
        "guild_id": guild_id, "canal_id": canal_id, "mensaje_id": None,
        "creado_por": creado_por, "estado": "abierto", "respuestas": [],
    }
    with _conectar() as conn:
        fila = conn.execute(
            "INSERT INTO formularios (guild_id, data) VALUES (%s, %s) RETURNING id",
            (guild_id, Json(data)),
        ).fetchone()
    return str(fila["id"])


def obtener_formulario(formulario_id: str) -> dict | None:
    with _conectar() as conn:
        fila = conn.execute("SELECT id, data FROM formularios WHERE id = %s", (int(formulario_id),)).fetchone()
    return _fila_a_formulario(fila) if fila else None


def listar_todos_los_formularios() -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute("SELECT id, data FROM formularios ORDER BY id").fetchall()
    return [_fila_a_formulario(f) for f in filas]


def actualizar_formulario(formulario_id: str, **cambios):
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute("SELECT data FROM formularios WHERE id = %s FOR UPDATE", (int(formulario_id),)).fetchone()
            if fila is None:
                return None
            data = dict(fila["data"])
            data.update(cambios)
            conn.execute("UPDATE formularios SET data = %s WHERE id = %s", (Json(data), int(formulario_id)))
    return obtener_formulario(formulario_id)


def responder_formulario(formulario_id: str, respuesta: dict) -> tuple[bool, str]:
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute("SELECT data FROM formularios WHERE id = %s FOR UPDATE", (int(formulario_id),)).fetchone()
            if fila is None:
                return False, "El formulario no existe."
            data = dict(fila["data"])
            if data["estado"] != "abierto":
                return False, "El formulario está cerrado."
            personaje = respuesta.get("personaje", "").strip().casefold()
            actualizada = any(
                r["user_id"] == respuesta["user_id"]
                and r.get("personaje", "").strip().casefold() == personaje
                for r in data["respuestas"]
            )
            personajes_del_usuario = sum(
                1 for r in data["respuestas"] if r["user_id"] == respuesta["user_id"]
            )
            if not actualizada and personajes_del_usuario >= 2:
                return False, "Puedes inscribir un máximo de 2 personajes."
            data["respuestas"] = [
                r for r in data["respuestas"]
                if not (
                    r["user_id"] == respuesta["user_id"]
                    and r.get("personaje", "").strip().casefold() == personaje
                )
            ]
            data["respuestas"].append(respuesta)
            conn.execute("UPDATE formularios SET data = %s WHERE id = %s", (Json(data), int(formulario_id)))
    return True, "Personaje actualizado." if actualizada else "Personaje inscrito."


def quitar_respuesta_formulario(formulario_id: str, user_id: int, personaje: str | None = None) -> bool:
    with _conectar() as conn:
        with conn.transaction():
            fila = conn.execute("SELECT data FROM formularios WHERE id = %s FOR UPDATE", (int(formulario_id),)).fetchone()
            if fila is None:
                return False
            data = dict(fila["data"])
            if data["estado"] != "abierto":
                return False
            antes = len(data["respuestas"])
            data["respuestas"] = [
                r for r in data["respuestas"]
                if not (
                    r["user_id"] == user_id
                    and (personaje is None or r.get("personaje", "").casefold() == personaje.casefold())
                )
            ]
            conn.execute("UPDATE formularios SET data = %s WHERE id = %s", (Json(data), int(formulario_id)))
    return len(data["respuestas"]) < antes
