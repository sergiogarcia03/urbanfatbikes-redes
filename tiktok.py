"""Manda los reels del calendario a la bandeja de entrada de TikTok como borradores.

TikTok solo deja publicar directamente a las aplicaciones auditadas, y no audita
herramientas para publicar en tu propia cuenta. Por eso los vídeos llegan como
borrador a la app de TikTok (con una notificación), y desde ahí se publican
con un toque. Al subir cada borrador se abre un aviso (issue) en GitHub con el
texto listo para copiar y pegar.

Uso:
  python tiktok.py --modo enlace              # enlace para dar permiso a la app
  python tiktok.py --modo conectar --codigo X # guarda el permiso (código de la web)
  python tiktok.py --modo comprobar           # prueba que el permiso funciona
  python tiktok.py --modo simular             # dice qué subiría, sin subir nada
  python tiktok.py --modo subir               # sube los reels cuya fecha ha llegado

Variables de entorno (en GitHub van en los Secrets):
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET  claves de la app de TikTok for Developers
  TIKTOK_REFRESH_TOKEN  el permiso de la cuenta (lo guarda solo el modo conectar)
  GH_PAT                token de GitHub que puede cambiar Secrets (TikTok cambia
                        a veces el permiso al renovarlo y hay que guardarlo)
"""

import argparse
import math
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

from publicar import (MAX_RETRASO, RAIZ, ZONA, archivos_de, cargar_calendario, cargar_publicados,
                      es_video, fecha_de, guardar_publicados, problemas)

API = "https://open.tiktokapis.com/v2"
AUTORIZAR = "https://www.tiktok.com/v2/auth/authorize/"
PERMISOS = "user.info.basic,video.upload"
SECRETO_PERMISO = "TIKTOK_REFRESH_TOKEN"

# Tamaños de trozo que admite TikTok al subir un archivo (de 5 a 64 MB; el último, hasta 128 MB)
TROZO = 10 * 1024 * 1024
MAX_UN_TROZO = 64 * 1024 * 1024


class TikTokError(Exception):
    """Error devuelto por la API de TikTok."""


def direccion_vuelta():
    """Página de la web a la que vuelve TikTok después de dar permiso (docs/tiktok/)."""
    if os.environ.get("TIKTOK_REDIRECT_URI"):
        return os.environ["TIKTOK_REDIRECT_URI"]
    dueno, repo = os.environ.get("GITHUB_REPOSITORY", "sergiogarcia03/urbanfatbikes-redes").split("/")
    return f"https://{dueno.lower()}.github.io/{repo}/tiktok/"


def ocultar(valor):
    """Evita que un token aparezca en los registros de GitHub Actions."""
    if valor and os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{valor}")


def clave(nombre):
    valor = (os.environ.get(nombre) or "").strip()  # sin saltos de línea pegados sin querer
    if not valor:
        sys.exit(f"Falta el secret {nombre} (ver README, sección TikTok).")
    return valor


# --- Permisos (OAuth) -----------------------------------------------------


def pedir_token(**datos):
    datos.update(client_key=clave("TIKTOK_CLIENT_KEY"), client_secret=clave("TIKTOK_CLIENT_SECRET"))
    try:
        respuesta = requests.post(f"{API}/oauth/token/", data=datos, timeout=60).json()
    except (requests.RequestException, ValueError) as error:
        raise TikTokError(f"no se pudo conectar con TikTok ({type(error).__name__})") from None
    if "access_token" not in respuesta:
        raise TikTokError(f"{respuesta.get('error_description') or respuesta.get('error') or respuesta}")
    ocultar(respuesta["access_token"])
    ocultar(respuesta.get("refresh_token"))
    return respuesta


def guardar_permiso(permiso):
    """Guarda el permiso de TikTok en los Secrets de GitHub (con gh y el GH_PAT)."""
    token_github = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token_github or not repo:
        raise TikTokError("falta el secret GH_PAT para guardar el permiso de TikTok (ver README)")
    resultado = subprocess.run(["gh", "secret", "set", SECRETO_PERMISO, "--repo", repo],
                               input=permiso, text=True, capture_output=True,
                               env={**os.environ, "GH_TOKEN": token_github})
    if resultado.returncode != 0:
        raise TikTokError(f"no se pudo guardar el permiso en GitHub: {resultado.stderr.strip()}")


def token_de_acceso():
    """Renueva el acceso (dura 24 h) con el permiso guardado (dura 1 año)."""
    permiso = clave(SECRETO_PERMISO)
    ocultar(permiso)
    respuesta = pedir_token(grant_type="refresh_token", refresh_token=permiso)
    nuevo = respuesta.get("refresh_token")
    if nuevo and nuevo != permiso:
        guardar_permiso(nuevo)
        print("🔑 TikTok ha renovado el permiso; guardado en los Secrets.")
    return respuesta["access_token"]


# --- API ------------------------------------------------------------------


class TikTok:
    def __init__(self, token):
        self.token = token
        self.ultima_respuesta = ""

    def _llamar(self, metodo, ruta, **opciones):
        cabeceras = {"Authorization": f"Bearer {self.token}"}
        if "json" in opciones:
            cabeceras["Content-Type"] = "application/json; charset=UTF-8"
        try:
            datos = requests.request(metodo, f"{API}/{ruta}", headers=cabeceras, timeout=60, **opciones).json()
        except (requests.RequestException, ValueError) as error:
            raise TikTokError(f"no se pudo conectar con TikTok ({type(error).__name__})") from None
        error = datos.get("error") or {}
        if error.get("code", "ok") != "ok":
            raise TikTokError(f"{error.get('message') or error.get('code')} ({error.get('code')})")
        return datos.get("data") or {}

    def cuenta(self):
        return self._llamar("GET", "user/info/", params={"fields": "open_id,display_name"})["user"]

    def subir_borrador(self, ruta):
        """Sube un vídeo a la bandeja de entrada de TikTok y devuelve su publish_id."""
        tamano = ruta.stat().st_size
        trozo = tamano if tamano <= MAX_UN_TROZO else TROZO
        total = max(1, math.floor(tamano / trozo))  # el último trozo se lleva lo que sobre
        datos = self._llamar("POST", "post/publish/inbox/video/init/", json={"source_info": {
            "source": "FILE_UPLOAD", "video_size": tamano, "chunk_size": trozo, "total_chunk_count": total}})

        with open(ruta, "rb") as archivo:
            for numero in range(total):
                inicio = numero * trozo
                fin = tamano - 1 if numero == total - 1 else inicio + trozo - 1
                archivo.seek(inicio)
                parte = archivo.read(fin - inicio + 1)
                try:
                    respuesta = requests.put(datos["upload_url"], data=parte, timeout=300, headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(parte)),
                        "Content-Range": f"bytes {inicio}-{fin}/{tamano}",
                    })
                except requests.RequestException as error:
                    raise TikTokError(f"falló la subida del vídeo ({type(error).__name__})") from None
                if respuesta.status_code not in (200, 201, 206):
                    raise TikTokError(f"falló la subida del vídeo (HTTP {respuesta.status_code})")
                self.ultima_respuesta = f"HTTP {respuesta.status_code} {respuesta.text[:300]}"
        return datos["publish_id"]

    def esperar(self, publish_id, max_segundos=300, detalle=False):
        """Espera a que TikTok procese el vídeo y lo deje en la bandeja de entrada."""
        limite = time.time() + max_segundos
        while True:
            estado = self._llamar("POST", "post/publish/status/fetch/", json={"publish_id": publish_id})
            situacion = estado.get("status")
            if detalle:
                print(f"   estado: {estado}", flush=True)
            if situacion in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
                return situacion
            if situacion == "FAILED":
                raise TikTokError(f"TikTok no pudo procesar el vídeo: {estado.get('fail_reason')}")
            if time.time() > limite:
                return situacion  # sigue procesándose; llegará a la bandeja igualmente
            time.sleep(10)


# --- Calendario -----------------------------------------------------------


def video_para_tiktok(publicacion):
    """El vídeo de un reel; si existe una versión <nombre>-tiktok.mp4, esa."""
    archivo = RAIZ / "contenido" / archivos_de(publicacion)[0]
    especial = archivo.with_name(f"{archivo.stem}-tiktok{archivo.suffix}")
    return especial if especial.exists() else archivo


def va_a_tiktok(publicacion):
    archivos = archivos_de(publicacion)
    return (publicacion.get("tipo") != "historia" and publicacion.get("tiktok") is not False
            and len(archivos) == 1 and es_video(archivos[0]) and not archivos[0].startswith("http"))


def fecha_tiktok(publicacion):
    if publicacion.get("fecha_tiktok"):
        return fecha_de({"fecha": publicacion["fecha_tiktok"]})
    return fecha_de(publicacion)


def avisar(publicacion, nombre_video):
    """Abre un aviso en GitHub con el texto para pegar al publicar en TikTok."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        return
    texto = (publicacion.get("texto_tiktok") or publicacion.get("texto") or "").strip()
    cuerpo = (
        f"El vídeo **{nombre_video}** ya está en tu bandeja de entrada de TikTok.\n\n"
        "1. Abre TikTok → **Bandeja de entrada** → notificación del borrador.\n"
        "2. Pega este texto:\n\n"
        f"```\n{texto}\n```\n\n"
        "3. Activa **Contenido comercial → Tu marca** (es obligatorio al hablar de tu marca).\n"
        "4. Publica y cierra este aviso.\n\n"
        "@sergiogarcia03 ⏰ publícalo entre las 19:00 y las 22:00 (hora de España).\n"
    )
    try:
        requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                      json={"title": f"📲 TikTok: publica «{publicacion['id']}»", "body": cuerpo,
                            "assignees": ["sergiogarcia03"]})  # asignado: le llega aviso al móvil (app de GitHub)
    except requests.RequestException:
        print("⚠️  No se pudo abrir el aviso en GitHub (el borrador sí está en TikTok).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["enlace", "conectar", "comprobar", "probar", "estado", "simular", "subir"], default="simular")
    parser.add_argument("--codigo", help="código que muestra la web después de dar permiso (modo conectar)")
    parser.add_argument("--video", default="reel-legal.mp4",
                        help="modo probar: vídeo de contenido/ que se manda a la bandeja (no se registra)")
    parser.add_argument("--publish-id", help="modo estado: identificador de una subida anterior")
    parser.add_argument("--manual", action="store_true", help="lanzado a mano: sube aunque vaya con retraso")
    args = parser.parse_args()

    if args.modo == "enlace":
        enlace = AUTORIZAR + "?" + urlencode({
            "client_key": clave("TIKTOK_CLIENT_KEY"), "scope": PERMISOS, "response_type": "code",
            "redirect_uri": direccion_vuelta(), "state": secrets.token_urlsafe(16)})
        print(f"Abre este enlace en el navegador donde tengas abierta la cuenta de TikTok:\n{enlace}")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumen:
                resumen.write(f"## Conectar TikTok\n\n👉 [Dar permiso a la app en TikTok]({enlace})\n\n"
                              "Después, la web te dará un código: pégalo aquí con el modo **conectar**.\n")
        return

    if args.modo == "conectar":
        codigo = (args.codigo or os.environ.get("TIKTOK_CODIGO") or "").strip()
        if not codigo:
            sys.exit("Falta el código que te dio la web después de dar permiso.")
        ocultar(codigo)
        try:
            respuesta = pedir_token(grant_type="authorization_code", code=codigo, redirect_uri=direccion_vuelta())
            guardar_permiso(respuesta["refresh_token"])
            cuenta = TikTok(respuesta["access_token"]).cuenta()
        except TikTokError as error:
            sys.exit(f"❌ No se pudo conectar: {error}")
        print(f"✅ TikTok conectado: {cuenta.get('display_name')}. Permisos: {respuesta.get('scope')}")
        return

    ahora = datetime.now(ZONA)
    publicados = cargar_publicados()
    pendientes = []
    for publicacion in cargar_calendario():
        nombre = publicacion.get("id", "(sin id)")
        if publicacion.get("borrador") or not va_a_tiktok(publicacion) or problemas(publicacion):
            continue
        if "tiktok" in publicados.get(nombre, {}):
            continue
        cuando = fecha_tiktok(publicacion)
        if cuando > ahora:
            continue
        if ahora - cuando > MAX_RETRASO and not args.manual:
            print(f"⏰ {nombre}: su fecha para TikTok pasó hace más de 24 h; no se sube sola")
            continue
        pendientes.append(publicacion)

    if args.modo == "simular":
        for publicacion in pendientes:
            print(f"👀 {publicacion['id']}: se subiría a TikTok ({video_para_tiktok(publicacion).name})")
        if not pendientes:
            print("Nada que subir a TikTok ahora.")
        return

    if args.modo == "subir" and not pendientes:
        return
    if not os.environ.get(SECRETO_PERMISO):
        if args.modo == "subir":
            print("ℹ️  TikTok todavía no está conectado; no se sube nada.")
            return
        sys.exit(f"Falta el secret {SECRETO_PERMISO}: conecta TikTok primero (modo enlace y conectar).")

    try:
        tiktok = TikTok(token_de_acceso())
        if args.modo == "comprobar":
            print(f"✅ Conectado a TikTok como {tiktok.cuenta().get('display_name')}")
            return
        if args.modo == "estado":
            for publish_id in (args.publish_id or os.environ.get("TIKTOK_PUBLISH_ID", "")).split(","):
                if publish_id.strip():
                    estado = tiktok._llamar("POST", "post/publish/status/fetch/", json={"publish_id": publish_id.strip()})
                    print(f"{publish_id.strip()}: {estado}")
            return
        if args.modo == "probar":
            video = RAIZ / "contenido" / args.video
            print(f"📤 Prueba: subiendo {video.name} ({video.stat().st_size} bytes) a la bandeja de TikTok...", flush=True)
            publish_id = tiktok.subir_borrador(video)
            print(f"   subida: {tiktok.ultima_respuesta} · publish_id {publish_id}", flush=True)
            situacion = tiktok.esperar(publish_id, max_segundos=180, detalle=True)
            print(f"✅ Borrador enviado ({situacion}). Míralo en la app de TikTok (bandeja de entrada).")
            return
    except TikTokError as error:
        sys.exit(f"❌ TikTok: {error}")

    fallos = 0
    for publicacion in pendientes:
        nombre = publicacion["id"]
        video = video_para_tiktok(publicacion)
        print(f"📤 {nombre}: subiendo {video.name} a la bandeja de TikTok...")
        try:
            publish_id = tiktok.subir_borrador(video)
            situacion = tiktok.esperar(publish_id)
        except TikTokError as error:
            fallos += 1
            print(f"❌ {nombre}: {error}")
            continue
        publicados.setdefault(nombre, {})["tiktok"] = {
            "publish_id": publish_id,
            "estado": situacion,
            "fecha": ahora.isoformat(timespec="minutes"),
        }
        guardar_publicados(publicados)
        avisar(publicacion, video.name)
        print(f"✅ {nombre}: borrador en TikTok ({situacion})")

    if fallos:
        sys.exit(f"Hubo {fallos} vídeo(s) con errores en TikTok.")


if __name__ == "__main__":
    main()
