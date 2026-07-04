"""
Capa de persistencia: usa Postgres si hay DATABASE_URL configurada
(producción en Render, donde el filesystem no sobrevive a los deploys),
o un archivo JSON local si no la hay (para correr y probar el bot en tu
máquina sin depender de una base de datos externa).
"""

import os

if os.getenv("DATABASE_URL"):
    from utils.storage_pg import (
        crear_evento,
        obtener_evento,
        listar_eventos,
        listar_todos_los_eventos,
        actualizar_evento,
        agregar_participante,
        quitar_participante,
        agregar_equipo,
        quitar_equipo,
    )
else:
    from utils.storage_json import (
        crear_evento,
        obtener_evento,
        listar_eventos,
        listar_todos_los_eventos,
        actualizar_evento,
        agregar_participante,
        quitar_participante,
        agregar_equipo,
        quitar_equipo,
    )
