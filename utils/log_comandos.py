"""Formato seguro y compacto para auditar invocaciones de comandos slash."""

import json


TIPOS_SUBCOMANDO = {1, 2}
MAX_VALOR = 160


def _valor_corto(valor) -> str:
    if isinstance(valor, str):
        texto = valor.replace("\n", "\\n")
    else:
        texto = json.dumps(valor, ensure_ascii=False, default=str)
    if len(texto) > MAX_VALOR:
        texto = texto[: MAX_VALOR - 1] + "…"
    return texto


def extraer_comando_y_parametros(data: dict) -> tuple[str, dict[str, str]]:
    """Convierte la estructura anidada de Discord en ruta y parámetros legibles."""
    ruta = [str(data.get("name", "desconocido"))]
    parametros: dict[str, str] = {}

    def recorrer(opciones):
        for opcion in opciones or []:
            if opcion.get("type") in TIPOS_SUBCOMANDO:
                ruta.append(str(opcion.get("name", "desconocido")))
                recorrer(opcion.get("options"))
            elif "value" in opcion:
                parametros[str(opcion.get("name", "parametro"))] = _valor_corto(opcion["value"])

    recorrer(data.get("options"))
    return "/" + " ".join(ruta), parametros


def formatear_invocacion(interaction) -> str:
    comando, parametros = extraer_comando_y_parametros(interaction.data or {})
    usuario = interaction.user
    guild_id = interaction.guild_id or "DM"
    canal_id = interaction.channel_id or "desconocido"
    detalle = " ".join(f"{nombre}={valor!r}" for nombre, valor in parametros.items())
    if detalle:
        detalle = " | " + detalle
    return (
        f"COMANDO usuario={usuario} usuario_id={usuario.id} guild_id={guild_id} "
        f"canal_id={canal_id} comando={comando}{detalle}"
    )
