"""Ejecuta el bot y reinicia el proceso cuando cambia el código fuente.

Uso desde la raíz del proyecto:
    python scripts/dev.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
IGNORAR = {".git", ".claude", "venv", "__pycache__"}


def archivos_vigilados() -> list[Path]:
    archivos = [ruta for ruta in RAIZ.rglob("*.py") if not IGNORAR.intersection(ruta.parts)]
    env = RAIZ / ".env"
    if env.exists():
        archivos.append(env)
    return archivos


def estado() -> dict[Path, int]:
    resultado = {}
    for ruta in archivos_vigilados():
        try:
            resultado[ruta] = ruta.stat().st_mtime_ns
        except FileNotFoundError:
            pass
    return resultado


def iniciar_bot() -> subprocess.Popen[bytes]:
    entorno = os.environ.copy()
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    print("\n▶ Iniciando el bot...", flush=True)
    return subprocess.Popen([sys.executable, "main.py"], cwd=RAIZ, env=entorno)


def detener_bot(proceso: subprocess.Popen[bytes]) -> None:
    if proceso.poll() is not None:
        return
    proceso.terminate()
    try:
        proceso.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proceso.kill()
        proceso.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot de Discord con recarga automática")
    parser.add_argument("--intervalo", type=float, default=0.75, help="Segundos entre revisiones")
    args = parser.parse_args()
    if args.intervalo <= 0:
        parser.error("--intervalo debe ser mayor que cero")

    anterior = estado()
    proceso = iniciar_bot()
    print("👀 Vigilando archivos .py y .env. Pulsa Ctrl+C para salir.", flush=True)

    try:
        while True:
            time.sleep(args.intervalo)
            actual = estado()
            if actual == anterior:
                continue
            cambiados = sorted(
                ruta.relative_to(RAIZ)
                for ruta in set(anterior) | set(actual)
                if anterior.get(ruta) != actual.get(ruta)
            )
            print("\n↻ Cambio detectado: " + ", ".join(map(str, cambiados)), flush=True)
            detener_bot(proceso)
            anterior = actual
            proceso = iniciar_bot()
    except KeyboardInterrupt:
        print("\n■ Deteniendo el modo de desarrollo...", flush=True)
    finally:
        detener_bot(proceso)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
