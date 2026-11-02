"""Vigila el calendario para que nada salga tarde aunque GitHub se salte ejecuciones.

GitHub a veces pasa 5-8 horas sin lanzar las tareas programadas. Este script se
queda esperando (hasta 5 h 20 min), lanza «Publicar en redes» justo a la hora de lo
próximo del calendario y, al terminar, se vuelve a lanzar a sí mismo: siempre hay
una ejecución vigilando. Lo lanza el workflow «Vigilar el calendario».
"""

import json
import os
import subprocess
import time
from datetime import datetime, timedelta

import publicar
from publicar import MAX_RETRASO, ZONA, cargar_calendario, fecha_de, problemas

TURNO = timedelta(hours=5, minutes=20)  # lo que dura una ejecución (GitHub corta a las 6 h)
ANTES = timedelta(minutes=2)            # lanza «Publicar» un poco antes; publicar.py espera a la hora exacta
HORIZONTE = timedelta(days=14)          # sin nada en 14 días, deja de vigilar


def actualizar():
    subprocess.run(["git", "pull", "-q", "--ff-only"], check=False)


def publicados():
    ruta = publicar.PUBLICADOS
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def proxima(ahora):
    hechos = publicados()
    fechas = []
    for p in cargar_calendario():
        if p.get("borrador") or "instagram" in hechos.get(p.get("id"), {}) or problemas(p):
            continue
        try:
            cuando = fecha_de(p)
        except (KeyError, ValueError):
            continue
        if ahora - cuando <= MAX_RETRASO:
            fechas.append(cuando)
    return min(fechas) if fechas else None


def lanzar(workflow, *campos):
    orden = ["gh", "workflow", "run", workflow, "--ref", "main"]
    for campo in campos:
        orden += ["-f", campo]
    subprocess.run(orden, check=True)
    print(f"🚀 lanzado {workflow} {' '.join(campos)}", flush=True)


def main():
    inicio = datetime.now(ZONA)
    seguir, avisado = True, None
    while True:
        actualizar()
        ahora = datetime.now(ZONA)
        siguiente = proxima(ahora)
        if siguiente is None or siguiente - ahora > HORIZONTE:
            print("Nada en el calendario para los próximos 14 días: dejo de vigilar.")
            seguir = False
            break
        if siguiente - ahora <= ANTES:
            print(f"⏰ Toca lo de las {siguiente:%d/%m %H:%M}", flush=True)
            lanzar("publicar.yml", "modo=automatico")
            time.sleep(15 * 60)  # deja que lo publique antes de mirar lo siguiente
            break
        limite = inicio + TURNO
        if ahora >= limite:
            break
        espera = min(siguiente - ANTES, limite) - ahora
        if avisado != siguiente:
            print(f"⏳ Lo próximo sale el {siguiente:%d/%m a las %H:%M}: vigilo hasta entonces", flush=True)
            avisado = siguiente
        time.sleep(max(30, min(espera, timedelta(minutes=10)).total_seconds()))
    if seguir and os.environ.get("GITHUB_ACTIONS"):
        lanzar("vigilar.yml")  # el relevo: siempre queda una ejecución vigilando


if __name__ == "__main__":
    main()
