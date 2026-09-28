"""Crea las imágenes de las historias de Instagram (verticales, 1080 × 1920).

Dos clases de historias:
  - "Nuevo post": una por cada publicación del calendario, con su portada
    (el primer fotograma del reel o la primera imagen). Se publica sola una
    hora después de la publicación (ver publicar.py).
  - Las de historias.yaml: datos, consejos y avances con el diseño de la marca.

Todas se guardan en contenido/historias/. No usa inteligencia artificial.

Uso:
  python historias.py
"""

import re
import subprocess
from io import BytesIO
from pathlib import Path

import imageio_ffmpeg
import yaml
from PIL import Image, ImageDraw, ImageFilter

from adaptar import ruta_adaptada
from tarjetas import ANCHO, ALTO, BLANCO, FONDO_ABAJO, GRIS, TURQUESA, contenido, fondo, fuente, partir, pie

RAIZ = Path(__file__).parent
CONTENIDO = RAIZ / "contenido"
SALIDA = CONTENIDO / "historias"
CALENDARIO = RAIZ / "calendario.yaml"
DEFINICIONES = RAIZ / "historias.yaml"

ALTO_HISTORIA = 1920
ARRIBA = (ALTO_HISTORIA - ALTO) // 2  # donde va el diseño de 1080 × 1350


def etiqueta(lienzo, texto, y):
    """Pastilla turquesa centrada con texto oscuro."""
    d = ImageDraw.Draw(lienzo)
    letra = fuente("ExtraBold", 40)
    ancho = letra.getlength(texto) + 90
    x = (ANCHO - ancho) / 2
    d.rounded_rectangle((x, y, x + ancho, y + 84), radius=42, fill=TURQUESA)
    d.text((ANCHO / 2, y + 42), texto, font=letra, fill=FONDO_ABAJO, anchor="mm")


def portada(archivo):
    """Primera imagen de una publicación (para un vídeo, un fotograma del principio)."""
    if Path(archivo).suffix.lower() in {".mp4", ".mov"}:
        salida = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-ss", "0.5", "-i", str(CONTENIDO / archivo),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, check=True).stdout
        return Image.open(BytesIO(salida)).convert("RGB")
    with Image.open(ruta_adaptada(archivo)) as imagen:
        return imagen.convert("RGB")


def con_esquinas(imagen, radio=40):
    mascara = Image.new("L", imagen.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, *imagen.size), radius=radio, fill=255)
    resultado = imagen.convert("RGBA")
    resultado.putalpha(mascara)
    return resultado


def nuevo_post(publicacion):
    archivos = publicacion["archivos"]
    archivos = [archivos] if isinstance(archivos, str) else archivos
    if Path(archivos[0]).suffix.lower() in {".mp4", ".mov"}:
        texto_etiqueta = "NUEVO REEL"
    elif len(archivos) > 1:
        texto_etiqueta = "NUEVO CARRUSEL"
    else:
        texto_etiqueta = "NUEVA PUBLICACIÓN"

    lienzo = fondo(0, 1, ALTO_HISTORIA)
    etiqueta(lienzo, texto_etiqueta, 170)

    # Primera línea del texto de la publicación, como titular
    d = ImageDraw.Draw(lienzo)
    titular = (publicacion.get("texto") or "").strip().split("\n")[0]
    titular = "".join(c for c in titular if ord(c) < 0x2000)  # sin emojis (la fuente no los tiene)
    primera_frase = re.match(r"\s*(.+?[.?!])(\s|$)", titular)
    titular = (primera_frase.group(1) if primera_frase else titular).strip()
    letra = fuente("ExtraBold", 50)
    y = 290
    for linea in partir(titular, letra, ANCHO - 160)[:2]:
        texto = " ".join(p for p, _ in linea)
        d.text((ANCHO / 2, y), texto, font=letra, fill=BLANCO, anchor="ma")
        y += 62

    # Portada de la publicación, con esquinas redondeadas y sombra
    imagen = portada(archivos[0])
    alto_max, ancho_max = 1640 - (y + 30), 860
    escala = min(ancho_max / imagen.width, alto_max / imagen.height)
    imagen = imagen.resize((round(imagen.width * escala), round(imagen.height * escala)), Image.LANCZOS)
    x0, y0 = (ANCHO - imagen.width) // 2, y + 30
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((x0 + 10, y0 + 24, x0 + imagen.width + 10, y0 + imagen.height + 24),
                                             radius=40, fill=(0, 0, 0, 150))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(24)))
    lienzo.alpha_composite(con_esquinas(imagen), (x0, y0))

    d = ImageDraw.Draw(lienzo)
    d.text((ANCHO / 2, 1690), "Míralo en nuestro perfil", font=fuente("Bold", 44), fill=BLANCO, anchor="ma")
    d.text((ANCHO / 2, 1750), "@urbanfatbikes", font=fuente("SemiBold", 36), fill=GRIS, anchor="ma")
    return lienzo


def historia_disenada(datos):
    """Historia con el diseño de las tarjetas, centrado en formato vertical."""
    lienzo = fondo(0, 1, ALTO_HISTORIA)
    capa = contenido(datos)
    pie(capa, 0, 1)
    lienzo.alpha_composite(capa, (0, ARRIBA))
    return lienzo


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    creadas = set()

    calendario = yaml.safe_load(CALENDARIO.read_text(encoding="utf-8")) or {}
    for p in calendario.get("publicaciones") or []:
        if p.get("borrador") or p.get("historia") is False or not p.get("archivos"):
            continue
        destino = SALIDA / f"nuevo-{p['id']}.jpg"
        try:
            nuevo_post(p).convert("RGB").save(destino, "JPEG", quality=90, optimize=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"❌ {destino.name}: {error}")
            continue
        creadas.add(destino)
        print(f"✅ historias/{destino.name}")

    if DEFINICIONES.exists():
        definiciones = yaml.safe_load(DEFINICIONES.read_text(encoding="utf-8")) or {}
        for h in definiciones.get("historias") or []:
            destino = SALIDA / f"{h['id']}.jpg"
            historia_disenada(h["diapositiva"]).convert("RGB").save(destino, "JPEG", quality=90, optimize=True)
            creadas.add(destino)
            print(f"✅ historias/{destino.name}")

    # Borra las que ya no corresponden a nada
    for sobrante in SALIDA.glob("*.jpg"):
        if sobrante not in creadas:
            sobrante.unlink()
            print(f"🗑️  historias/{sobrante.name}")


if __name__ == "__main__":
    main()
