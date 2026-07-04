"""
Genera equipos balanceados a partir de la lista de participantes,
repartiendo Tanks, Healers y DPS lo más parejo posible entre los equipos.
"""

import random

ROLES_VALIDOS = ["Tank", "Healer", "DPS"]


def normalizar_rol(rol: str) -> str:
    rol = rol.strip().lower()
    if rol.startswith("t"):
        return "Tank"
    if rol.startswith("h"):
        return "Healer"
    return "DPS"


def generar_equipos(participantes: list[dict], num_equipos: int) -> list[list[dict]]:
    if num_equipos < 1:
        raise ValueError("El número de equipos debe ser al menos 1.")

    equipos = [[] for _ in range(num_equipos)]

    # Agrupar por rol para repartir de forma equilibrada
    por_rol = {"Tank": [], "Healer": [], "DPS": []}
    for p in participantes:
        rol = normalizar_rol(p.get("rol", "DPS"))
        por_rol[rol].append(p)

    for rol in ("Tank", "Healer", "DPS"):
        random.shuffle(por_rol[rol])

    # Reparto round-robin: siempre se agrega al equipo con menos integrantes
    orden_llenado = por_rol["Tank"] + por_rol["Healer"] + por_rol["DPS"]
    for jugador in orden_llenado:
        equipo_mas_pequeno = min(range(num_equipos), key=lambda i: len(equipos[i]))
        equipos[equipo_mas_pequeno].append(jugador)

    return equipos
