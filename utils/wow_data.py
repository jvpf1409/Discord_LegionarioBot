"""
Clases y especializaciones de WoW, con su categoría de rol para los
contadores de /raid. Si tu comunidad usa otros nombres, ajusta esta lista.
"""

import unicodedata

from utils.iconos import icono

# Emoji unicode de reserva (se usa si no hay un ícono personalizado subido
# en assets/icons/ con ese mismo nombre — ver utils/iconos.py).
ROLES = {
    "tank": "🛡️ Tank    ",
    "healer": "➕ Healer    ",
    "melee": "⚔️ Melee    ",
    "ranged": "🏹 Ranged    ",
}

ROLES_TEXTO = {
    "tank": "Tank",
    "healer": "Healer",
    "melee": "Melee",
    "ranged": "Ranged",
}


def etiqueta_rol(rol: str) -> str:
    """Ícono personalizado + nombre si existe (assets/icons/{rol}.png), si no el emoji de reserva."""
    personalizado = icono(rol, "")
    if personalizado:
        return f"{personalizado} {ROLES_TEXTO[rol]}    "
    return ROLES[rol]

CLASES = {
    "Guerrero": [("Armas", "melee"), ("Furia", "melee"), ("Protección", "tank")],
    "Paladín": [("Sagrado", "healer"), ("Protección", "tank"), ("Reprensión", "melee")],
    "Cazador": [("Bestias", "ranged"), ("Puntería", "ranged"), ("Supervivencia", "melee")],
    "Pícaro": [("Asesinato", "melee"), ("Fuera de la Ley", "melee"), ("Sutileza", "melee")],
    "Sacerdote": [("Disciplina", "healer"), ("Sagrado", "healer"), ("Sombras", "ranged")],
    "Caballero de la Muerte": [("Sangre", "tank"), ("Escarcha", "melee"), ("Profano", "melee")],
    "Chamán": [("Elemental", "ranged"), ("Mejora", "melee"), ("Restauración", "healer")],
    "Mago": [("Arcano", "ranged"), ("Fuego", "ranged"), ("Escarcha", "ranged")],
    "Brujo": [("Aflicción", "ranged"), ("Demonología", "ranged"), ("Destrucción", "ranged")],
    "Monje": [("Maestro Cervecero", "tank"), ("Viajero del Viento", "melee"), ("Tejedor de Niebla", "healer")],
    "Druida": [("Equilibrio", "ranged"), ("Feral", "melee"), ("Guardián", "tank"), ("Restauración", "healer")],
    "Cazador de Demonios": [("Asolamiento", "melee"), ("Venganza", "tank")],
    "Evocador": [("Devastación", "ranged"), ("Preservación", "healer"), ("Aumento", "ranged")],
}


def rol_de(clase: str, especializacion: str) -> str:
    for nombre, rol in CLASES.get(clase, []):
        if nombre == especializacion:
            return rol
    return "melee"


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.lower().replace(" ", "_").replace("-", "_")


def nombre_icono_especializacion(clase: str, especializacion: str) -> str:
    """Nombre de archivo/emoji esperado en assets/icons/ para esta clase+especialización."""
    return f"{_slug(clase)}_{_slug(especializacion)}"


def icono_clase(clase: str) -> str:
    """Icono de clase; usa la primera especialización como reserva temporal."""
    personalizado = icono(f"clase_{_slug(clase)}", "")
    if personalizado:
        return personalizado
    especializaciones = CLASES.get(clase, [])
    if especializaciones:
        return icono_especializacion(clase, especializaciones[0][0])
    return ""


def icono_especializacion(clase: str, especializacion: str) -> str:
    """Ícono personalizado de la especialización si existe, si no cadena vacía."""
    return icono(nombre_icono_especializacion(clase, especializacion), "")
