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
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import yaml

from adaptar import EXT_FOTO, ruta_adaptada
from instagram import Instagram, InstagramError

RAIZ = Path(__file__).parent
CALENDARIO = RAIZ / "calendario.yaml"
HISTORIAS = RAIZ / "historias.yaml"
# La historia "nuevo post" de cada publicación sale este tiempo después
RETRASO_HISTORIA = timedelta(hours=1)
PUBLICADOS = RAIZ / "publicados.json"
ZONA = ZoneInfo("Europe/Madrid")

EXT_VIDEO = {".mp4", ".mov"}
MAX_TEXTO = 2200
MAX_HASHTAGS = 5  # Instagram ignora los que pasen de 5 (desde dic. 2025)
MAX_CARRUSEL = 10
# Si una publicación lleva más de esto sin salir (por ejemplo porque el
# calendario se aprobó tarde), no se publica sola: hay que cambiarle la fecha.
MAX_RETRASO = timedelta(hours=24)


def cargar_calendario():
    """Publicaciones del calendario más todas las historias.

    Cada publicación (que no sea borrador) lleva su historia "nuevo post" una hora
    después, salvo que tenga "historia: no". Las demás historias están en
    historias.yaml. Las imágenes de las historias las crea historias.py.
    """
    datos = yaml.safe_load(CALENDARIO.read_text(encoding="utf-8")) or {}
    publicaciones = list(datos.get("publicaciones") or [])
    lista = list(publicaciones)
    for p in publicaciones:
        if p.get("borrador") or p.get("historia") is False or not p.get("id"):
            continue
        try:
            cuando = fecha_de(p) + RETRASO_HISTORIA
        except (KeyError, ValueError):
            continue
        lista.append({"id": f"{p['id']}-historia", "tipo": "historia",
                      "fecha": cuando.strftime("%Y-%m-%d %H:%M"),
                      "archivos": [f"historias/nuevo-{p['id']}.jpg"]})
    if HISTORIAS.exists():
        extra = yaml.safe_load(HISTORIAS.read_text(encoding="utf-8")) or {}
        for h in extra.get("historias") or []:
            lista.append({"id": f"historia-{h.get('id')}", "tipo": "historia", "fecha": h.get("fecha"),
                          "borrador": h.get("borrador"), "archivos": [f"historias/{h.get('id')}.jpg"]})
    return sorted(lista, key=lambda p: str(p.get("fecha")))


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
    if publicacion.get("tipo") == "historia":
        # Las historias ya se crean en formato vertical listas para Instagram
        if len(archivos) != 1:
            errores.append("una historia lleva un solo archivo")
        for archivo in archivos:
            if not (RAIZ / "contenido" / archivo).exists():
                errores.append(f"{archivo}: no existe (python historias.py)")
        return errores
    if len(archivos) > MAX_CARRUSEL:
        errores.append(f"un carrusel admite como máximo {MAX_CARRUSEL} archivos")
    for archivo in archivos:
        extension = Path(archivo).suffix.lower()
        if extension not in EXT_FOTO | EXT_VIDEO:
            errores.append(f"{archivo}: solo se admiten fotos (.jpg, .png, .heic...) y vídeos (.mp4, .mov)")
        elif archivo.startswith("http"):
            continue
        elif not (RAIZ / "contenido" / archivo).exists():
            errores.append(f"{archivo}: no existe en la carpeta contenido/")
        elif extension in EXT_FOTO and not ruta_adaptada(archivo).exists():
            errores.append(f"{archivo}: falta adaptarla (python adaptar.py)")

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
    if es_video(archivo) or archivo.startswith("historias/"):
        return f"{base}/contenido/{quote(archivo)}"
    # Las fotos se publican desde su copia adaptada (ver adaptar.py).
    return f"{base}/{quote(ruta_adaptada(archivo).relative_to(RAIZ).as_posix())}"


def portada_reel(archivo):
    """URL de contenido/portadas/<vídeo>.jpg si existe: la portada del reel en el perfil."""
    portada = RAIZ / "contenido" / "portadas" / f"{Path(archivo).stem}.jpg"
    if archivo.startswith("http") or not portada.exists():
        return None
    base = os.environ["MEDIA_BASE_URL"].rstrip("/")
    return f"{base}/contenido/portadas/{quote(portada.name)}"


def es_video(archivo):
    return Path(archivo).suffix.lower() in EXT_VIDEO


def publicar_en_instagram(ig, publicacion):
    archivos = archivos_de(publicacion)
    texto = publicacion.get("texto")

    if publicacion.get("tipo") == "historia":
        contenedor = ig.contenedor_historia(url_publica(archivos[0]), video=es_video(archivos[0]))
        ig.esperar(contenedor)
        return ig.publicar(contenedor)

    if len(archivos) == 1:
        archivo = archivos[0]
        if es_video(archivo):
            try:
                contenedor = ig.contenedor_video(url_publica(archivo), texto, portada=portada_reel(archivo))
            except InstagramError as error:  # si la portada da problemas, el reel sale igual sin ella
                print(f"⚠️  portada no aceptada ({error}); se publica sin portada")
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
    parser.add_argument("--manual", action="store_true", help="lanzado a mano: publica aunque vaya con retraso")
    args = parser.parse_args()
    modo = args.modo

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
        if publicacion.get("borrador"):
            print(f"📝 {nombre}: borrador, no se publica")
            continue
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
        if ahora - fecha_de(publicacion) > MAX_RETRASO and not args.manual:
            print(f"⏰ {nombre}: su fecha ({publicacion['fecha']}) pasó hace más de 24 h; cámbiala para publicarla")
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
