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


_asegurar_tabla()


def _fila_a_evento(fila) -> dict:
    evento = dict(fila["data"])
    evento["id"] = str(fila["id"])
    return evento


def crear_evento(
    titulo: str,
    descripcion: str,
    guild_id: int,
    canal_id: int,
    num_equipos: int,
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
        "num_equipos": num_equipos,
        "fecha_hora_ts": fecha_hora_ts,
        "imagen_url": imagen_url,
        "estado": "abierto",  # abierto | cerrado | finalizado
        "creado_por": creado_por,
        "participantes": [],   # (tipo individual) lista de dicts: user_id, nombre_discord, personaje
        "equipos": [],         # lista de equipos: {nombre_equipo, user_id, nombre_discord, integrantes: [...]}
        "ganador": None,       # indice de equipo o nombre
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
            if data["num_equipos"] is not None and len(data["equipos"]) >= data["num_equipos"]:
                return False, f"Ya se alcanzó el cupo máximo de {data['num_equipos']} equipos."
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
