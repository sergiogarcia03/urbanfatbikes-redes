"""Cliente mínimo para publicar en Instagram con la API de Instagram
(con inicio de sesión de Instagram).

Publicar en Instagram por API siempre tiene dos pasos:
  1. Crear un "contenedor": le decimos a Instagram la URL pública de la foto
     o vídeo y el texto. Instagram lo descarga y lo prepara.
  2. Publicar ese contenedor cuando está listo.
"""

import time

import requests

API_URL = "https://graph.instagram.com"


class InstagramError(Exception):
    """Error devuelto por la API de Instagram."""


class Instagram:
    def __init__(self, token, version="v23.0"):
        self.token = token
        self.base = f"{API_URL}/{version}"
        self._user_id = None

    def _llamar(self, metodo, ruta, **params):
        params["access_token"] = self.token
        try:
            if metodo == "GET":
                respuesta = requests.get(f"{self.base}/{ruta}", params=params, timeout=60)
            else:
                respuesta = requests.post(f"{self.base}/{ruta}", data=params, timeout=60)
            datos = respuesta.json()
        except (requests.RequestException, ValueError) as error:
            raise InstagramError(f"no se pudo conectar con Instagram ({type(error).__name__})") from None
        if "error" in datos:
            error = datos["error"]
            raise InstagramError(f"{error.get('message')} (código {error.get('code')})")
        return datos

    def cuenta(self):
        """Devuelve el ID y el nombre de usuario de la cuenta del token."""
        return self._llamar("GET", "me", fields="user_id,username")

    @property
    def user_id(self):
        if self._user_id is None:
            self._user_id = self.cuenta()["user_id"]
        return self._user_id

    # --- Paso 1: crear contenedores -------------------------------------

    def contenedor_imagen(self, url, texto=None, en_carrusel=False):
        params = {"image_url": url}
        if en_carrusel:
            params["is_carousel_item"] = "true"
        elif texto:
            params["caption"] = texto
        return self._llamar("POST", f"{self.user_id}/media", **params)["id"]

    def contenedor_video(self, url, texto=None, en_carrusel=False, portada=None):
        params = {"video_url": url}
        if portada and not en_carrusel:
            params["cover_url"] = portada  # portada del reel en la cuadrícula del perfil
        if en_carrusel:
            params["media_type"] = "VIDEO"
            params["is_carousel_item"] = "true"
        else:
            params["media_type"] = "REELS"
            if texto:
                params["caption"] = texto
        return self._llamar("POST", f"{self.user_id}/media", **params)["id"]

    def contenedor_historia(self, url, video=False):
        clave = "video_url" if video else "image_url"
        return self._llamar("POST", f"{self.user_id}/media", media_type="STORIES", **{clave: url})["id"]

    def contenedor_carrusel(self, hijos, texto=None):
        params = {"media_type": "CAROUSEL", "children": ",".join(hijos)}
        if texto:
            params["caption"] = texto
        return self._llamar("POST", f"{self.user_id}/media", **params)["id"]

    def esperar(self, contenedor, max_segundos=600):
        """Espera a que Instagram termine de procesar el contenedor."""
        limite = time.time() + max_segundos
        while True:
            estado = self._llamar("GET", contenedor, fields="status_code,status")
            codigo = estado.get("status_code")
            if codigo == "FINISHED":
                return
            if codigo in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram no pudo procesar el archivo: {estado.get('status')}")
            if time.time() > limite:
                raise InstagramError("Instagram tarda demasiado en procesar el archivo")
            time.sleep(10)

    # --- Paso 2: publicar -----------------------------------------------

    def publicar(self, contenedor):
        """Publica un contenedor ya procesado y devuelve el ID de la publicación."""
        return self._llamar("POST", f"{self.user_id}/media_publish", creation_id=contenedor)["id"]
