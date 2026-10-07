"""Numeración estable de los equipos inscritos en un evento grupal."""


def numero_de_equipo(equipo: dict, posicion: int) -> int:
    """Número visible del equipo; los equipos antiguos sin número usan su posición."""
    return equipo.get("numero", posicion)


def numerar_equipo(evento: dict, equipo: dict) -> None:
    """
    Asigna a ``equipo`` el siguiente número del evento. El contador nunca
    retrocede, así que si un equipo se da de baja su número no se reutiliza
    y los demás conservan el suyo.
    """
    for posicion, existente in enumerate(evento["equipos"], start=1):
        existente.setdefault("numero", posicion)
    ultimo = max((e["numero"] for e in evento["equipos"]), default=0)
    siguiente = max(evento.get("siguiente_numero_equipo", 1), ultimo + 1)
    equipo["numero"] = siguiente
    evento["siguiente_numero_equipo"] = siguiente + 1


def buscar_equipo(evento: dict, numero: int) -> dict | None:
    return next(
        (
            e
            for posicion, e in enumerate(evento["equipos"], start=1)
            if numero_de_equipo(e, posicion) == numero
        ),
        None,
    )
