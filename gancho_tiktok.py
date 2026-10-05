"""Crea la versión de TikTok de cada reel: los 3 primeros segundos con fotos reales
de la bici y una frase gancho grande, y después el reel de siempre.

Lee ganchos_tiktok.yaml y crea contenido/reel-<nombre>-tiktok.mp4 (tiktok.py
manda esa versión en lugar del reel normal). El audio es el del reel original.

Uso:
  python gancho_tiktok.py             # crea las que falten o hayan cambiado
  python gancho_tiktok.py legal       # solo esa
  python gancho_tiktok.py --foto legal  # guarda una imagen de prueba del gancho
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from tarjetas import BLANCO, TURQUESA, fuente, partir

RAIZ = Path(__file__).parent
CONTENIDO = RAIZ / "contenido"
DEFINICIONES = RAIZ / "ganchos_tiktok.yaml"
HUELLAS = CONTENIDO / "ganchos_tiktok.json"
ANCHO, ALTO, FPS = 1080, 1920, 30
MARGEN = 80
Y_TEXTO = 330  # por debajo de la barra de arriba de TikTok


def suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def cubrir(imagen, ancho, alto):
    escala = max(ancho / imagen.width, alto / imagen.height)
    imagen = imagen.resize((round(imagen.width * escala), round(imagen.height * escala)), Image.LANCZOS)
    x, y = (imagen.width - ancho) // 2, (imagen.height - alto) // 2
    return imagen.crop((x, y, x + ancho, y + alto))


def cargar_plano(plano):
    foto = Image.open(CONTENIDO / plano["foto"]).convert("RGB")
    if plano.get("recorte"):
        foto = foto.crop(tuple(plano["recorte"]))
    foto = foto.resize((ANCHO, round(ANCHO * foto.height / foto.width)), Image.LANCZOS)
    fondo = cubrir(foto, ANCHO, ALTO).filter(ImageFilter.GaussianBlur(40))
    fondo = ImageEnhance.Brightness(fondo).enhance(0.45)
    return foto, fondo


def texto_gancho(lienzo, texto, aparicion):
    """Escribe el gancho centrado, con borde oscuro y entrada con un pequeño salto."""
    letra = fuente("Black", 104)
    lineas = partir(texto, letra, ANCHO - 2 * MARGEN)
    alto_linea = round(letra.size * 1.12)
    capa = Image.new("RGBA", (ANCHO, alto_linea * len(lineas) + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    y = 20
    for linea in lineas:
        total = letra.getlength(" ".join(p for p, _ in linea))
        x = (ANCHO - total) / 2
        for palabra, resaltada in linea:
            d.text((x, y), palabra, font=letra, fill=TURQUESA if resaltada else BLANCO,
                   stroke_width=10, stroke_fill=(10, 14, 18))
            x += letra.getlength(palabra + " ")
        y += alto_linea
    escala = 0.8 + 0.2 * suave(aparicion) + 0.06 * (1 - abs(2 * suave(aparicion) - 1)) * (aparicion < 1)
    if escala != 1:
        capa = capa.resize((round(capa.width * escala), round(capa.height * escala)), Image.LANCZOS)
    alfa = capa.getchannel("A").point(lambda a: round(a * min(1.0, aparicion * 3)))
    capa.putalpha(alfa)
    lienzo.alpha_composite(capa, ((ANCHO - capa.width) // 2, Y_TEXTO + round((1 - suave(aparicion)) * 40)))


def fotogramas(gancho, planos):
    total = round(gancho["duracion"] * FPS)
    por_plano = total / len(planos)
    marca = fuente("Bold", 40)
    for n in range(total):
        indice = min(int(n / por_plano), len(planos) - 1)
        t = (n - indice * por_plano) / por_plano  # 0..1 dentro del plano
        foto, fondo = planos[indice]
        lienzo = fondo.convert("RGBA")
        # entra con un golpe de zoom y luego se acerca despacio
        zoom = 1.0 + 0.12 * (1 - suave(t * 4)) + 0.06 * t
        w, h = round(foto.width * zoom), round(foto.height * zoom)
        grande = foto.resize((w, h), Image.BILINEAR)
        y = 780 - (h - foto.height) // 4
        lienzo.paste(grande, ((ANCHO - w) // 2, y))
        texto_gancho(lienzo, gancho["texto"], min(1.0, n / 9))
        d = ImageDraw.Draw(lienzo)
        d.text((ANCHO / 2, ALTO - 250), "urbanfatbikes", font=marca, fill=(255, 255, 255, 200), anchor="mm")
        yield lienzo.convert("RGB")


def huella(nombre, gancho):
    h = hashlib.sha256(json.dumps(gancho, sort_keys=True, ensure_ascii=False).encode())
    h.update((CONTENIDO / f"reel-{nombre}.mp4").read_bytes())
    for plano in gancho["planos"]:
        h.update((CONTENIDO / plano["foto"]).read_bytes())
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()


def generar(nombre, gancho):
    planos = [cargar_plano(p) for p in gancho["planos"]]
    original = CONTENIDO / f"reel-{nombre}.mp4"
    destino = CONTENIDO / f"reel-{nombre}-tiktok.mp4"
    orden = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
             "-i", str(original),
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
             "-filter_complex", "[0:v][1:v]overlay=eof_action=pass[v]",
             "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(destino)]
    proceso = subprocess.Popen(orden, stdin=subprocess.PIPE)
    for imagen in fotogramas(gancho, planos):
        proceso.stdin.write(imagen.tobytes())
    proceso.stdin.close()
    if proceso.wait() != 0:
        sys.exit(f"❌ {nombre}: ffmpeg falló")
    print(f"✅ {destino.name}")


def main():
    args = sys.argv[1:]
    ganchos = yaml.safe_load(DEFINICIONES.read_text(encoding="utf-8"))["ganchos"]
    if args and args[0] == "--foto":
        nombre = args[1]
        gancho = ganchos[nombre]
        planos = [cargar_plano(p) for p in gancho["planos"]]
        cuadros = list(fotogramas(gancho, planos))
        for i in (len(cuadros) // 4, 3 * len(cuadros) // 4):
            cuadros[i].save(f"gancho-{nombre}-{i}.jpg", quality=85)
            print(f"🖼  gancho-{nombre}-{i}.jpg")
        return
    huellas = json.loads(HUELLAS.read_text()) if HUELLAS.exists() else {}
    # Borra las versiones de TikTok que ya no tienen gancho.
    for sobrante in CONTENIDO.glob("reel-*-tiktok.mp4"):
        if sobrante.stem[5:-7] not in ganchos and not args:
            sobrante.unlink()
            huellas.pop(sobrante.stem[5:-7], None)
            print(f"🗑️  {sobrante.name}")
    for nombre, gancho in ganchos.items():
        if args and nombre not in args:
            continue
        nueva = huella(nombre, gancho)
        if huellas.get(nombre) == nueva and (CONTENIDO / f"reel-{nombre}-tiktok.mp4").exists():
            print(f"= reel-{nombre}-tiktok.mp4 ya está al día")
            continue
        generar(nombre, gancho)
        huellas[nombre] = nueva
    HUELLAS.write_text(json.dumps(huellas, indent=1) + "\n")


if __name__ == "__main__":
    main()
