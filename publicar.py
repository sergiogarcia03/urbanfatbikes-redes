"""Publica en Instagram las publicaciones de calendario.yaml cuya fecha ya ha llegado.

Uso:
  python publicar.py --modo comprobar   # solo comprueba que el token funciona
  python publicar.py --modo simular     # revisa el calendario sin publicar nada
  python publicar.py --modo publicar    # publica lo que toque

Necesita estas variables de entorno:
  IG_ACCESS_TOKEN  el token de Instagram (en GitHub va en los Secrets)
  MEDIA_BASE_URL   dirección web pública donde están los archivos de contenido/
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import yaml

from instagram import Instagram, InstagramError

RAIZ = Path(__file__).parent
CALENDARIO = RAIZ / "calendario.yaml"
PUBLICADOS = RAIZ / "publicados.json"
ZONA = ZoneInfo("Europe/Madrid")

EXT_IMAGEN = {".jpg", ".jpeg"}
EXT_VIDEO = {".mp4", ".mov"}
MAX_TEXTO = 2200
MAX_HASHTAGS = 30
MAX_CARRUSEL = 10


def cargar_calendario():
    datos = yaml.safe_load(CALENDARIO.read_text(encoding="utf-8")) or {}
    return datos.get("publicaciones") or []


def cargar_publicados():
    if PUBLICADOS.exists():
        return json.loads(PUBLICADOS.read_text(encoding="utf-8"))
    return {}


def guardar_publicados(publicados):
    PUBLICADOS.write_text(json.dumps(publicados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fecha_de(publicacion):
    return datetime.strptime(str(publicacion["fecha"]), "%Y-%m-%d %H:%M").replace(tzinfo=ZONA)


def archivos_de(publicacion):
    archivos = publicacion.get("archivos") or publicacion.get("archivo") or []
    return [archivos] if isinstance(archivos, str) else list(archivos)


def problemas(publicacion):
    """Devuelve una lista con los errores de una publicación del calendario."""
    errores = []
    if not publicacion.get("id"):
        errores.append("falta el campo 'id'")
    try:
        fecha_de(publicacion)
    except (KeyError, ValueError):
        errores.append("la fecha debe tener el formato \"2026-10-01 18:30\"")

    archivos = archivos_de(publicacion)
    if not archivos:
        errores.append("no tiene archivos")
    if len(archivos) > MAX_CARRUSEL:
        errores.append(f"un carrusel admite como máximo {MAX_CARRUSEL} archivos")
    for archivo in archivos:
        extension = Path(archivo).suffix.lower()
        if extension not in EXT_IMAGEN | EXT_VIDEO:
            errores.append(f"{archivo}: Instagram solo acepta fotos .jpg y vídeos .mp4/.mov")
        if not archivo.startswith("http") and not (RAIZ / "contenido" / archivo).exists():
            errores.append(f"{archivo}: no existe en la carpeta contenido/")

    texto = publicacion.get("texto") or ""
    if len(texto) > MAX_TEXTO:
        errores.append(f"el texto tiene {len(texto)} caracteres (máximo {MAX_TEXTO})")
    if texto.count("#") > MAX_HASHTAGS:
        errores.append(f"el texto tiene más de {MAX_HASHTAGS} hashtags")
    return errores


def url_publica(archivo):
    if archivo.startswith("http"):
        return archivo
    base = os.environ["MEDIA_BASE_URL"].rstrip("/")
    return f"{base}/contenido/{quote(archivo)}"


def es_video(archivo):
    return Path(archivo).suffix.lower() in EXT_VIDEO


def publicar_en_instagram(ig, publicacion):
    archivos = archivos_de(publicacion)
    texto = publicacion.get("texto")

    if len(archivos) == 1:
        archivo = archivos[0]
        if es_video(archivo):
            contenedor = ig.contenedor_video(url_publica(archivo), texto)
        else:
            contenedor = ig.contenedor_imagen(url_publica(archivo), texto)
    else:
        hijos = []
        for archivo in archivos:
            if es_video(archivo):
                hijo = ig.contenedor_video(url_publica(archivo), en_carrusel=True)
            else:
                hijo = ig.contenedor_imagen(url_publica(archivo), en_carrusel=True)
            ig.esperar(hijo)
            hijos.append(hijo)
        contenedor = ig.contenedor_carrusel(hijos, texto)

    ig.esperar(contenedor)
    return ig.publicar(contenedor)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["comprobar", "simular", "publicar"], default="simular")
    modo = parser.parse_args().modo

    token = os.environ.get("IG_ACCESS_TOKEN")
    if modo != "simular" and not token:
        sys.exit("Falta la variable IG_ACCESS_TOKEN (el token de Instagram).")
    ig = Instagram(token) if token else None

    if modo == "comprobar":
        try:
            cuenta = ig.cuenta()
        except InstagramError as error:
            sys.exit(f"❌ El token no funciona: {error}")
        print(f"✅ Conectado a Instagram como @{cuenta['username']} (ID {cuenta['user_id']})")
        return

    ahora = datetime.now(ZONA)
    publicados = cargar_publicados()
    fallos = 0

    for publicacion in cargar_calendario():
        nombre = publicacion.get("id", "(sin id)")
        errores = problemas(publicacion)
        if errores:
            fallos += 1
            print(f"❌ {nombre}: " + "; ".join(errores))
            continue

        if "instagram" in publicados.get(nombre, {}):
            continue
        if fecha_de(publicacion) > ahora:
            print(f"🕒 {nombre}: programada para el {publicacion['fecha']}")
            continue

        if modo == "simular":
            print(f"👀 {nombre}: se publicaría ahora")
            continue

        print(f"📤 {nombre}: publicando en Instagram...")
        try:
            media_id = publicar_en_instagram(ig, publicacion)
        except InstagramError as error:
            fallos += 1
            print(f"❌ {nombre}: {error}")
            continue
        publicados.setdefault(nombre, {})["instagram"] = {
            "id": media_id,
            "fecha": ahora.isoformat(timespec="minutes"),
        }
        guardar_publicados(publicados)
        print(f"✅ {nombre}: publicada (ID {media_id})")

    if fallos:
        sys.exit(f"Hubo {fallos} publicación(es) con errores.")


if __name__ == "__main__":
    main()
