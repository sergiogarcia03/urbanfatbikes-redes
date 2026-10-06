"""Monta el reel de detalles de la V8 a partir del vídeo del proveedor.

Coge solo las tomas sin rótulos en inglés, amplía la imagen para que no se vea
la marca de agua del proveedor y añade un gancho y rótulos en español con la
música propia. Crea contenido/v8-detalles.mp4.

Uso: python herramientas/detalles_v8.py
"""

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from tarjetas import BLANCO, TURQUESA, fuente, partir  # noqa: E402

ORIGEN = RAIZ / "contenido" / "proveedor" / "v8-detalles-original.mp4"
DESTINO = RAIZ / "contenido" / "v8-detalles.mp4"
MUSICA = RAIZ / "contenido" / "musica" / "inspira-1.m4a"
ANCHO, ALTO, FPS = 1080, 1920, 30
BANDA_Y, BANDA_ALTO = 470, 1040
GANCHO = "Lo que *no esperas*\nde una fatbike"

# (inicio, fin, rótulo): tomas del vídeo original sin rótulos en inglés
TOMAS = [
    (21.95, 22.45, "Faro LED"),
    (16.0, 18.4, "Faro LED"),
    (2.0, 4.9, "Mandos en el manillar"),
    (5.0, 7.9, "Pantalla con velocidad y batería"),
    (31.5, 32.4, "Doble suspensión"),
]


def fotogramas_de(inicio, fin):
    """Fotogramas de la parte del vídeo con imagen (sin las bandas difuminadas)."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ffmpeg, "-loglevel", "error", "-ss", str(inicio), "-t", str(fin - inicio), "-i", str(ORIGEN),
             "-vf", "crop=1080:608:0:656", "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    datos = subprocess.run(orden, capture_output=True, check=True).stdout
    tam = 1080 * 608 * 3
    for i in range(len(datos) // tam):
        yield Image.frombytes("RGB", (1080, 608), datos[i * tam:(i + 1) * tam])


def texto(lienzo, frase, y, tam, peso="Black", sombra=True):
    letra = fuente(peso, tam)
    d = ImageDraw.Draw(lienzo)
    for linea in partir(frase, letra, ANCHO - 140):
        total = letra.getlength(" ".join(p for p, _ in linea))
        x = (ANCHO - total) / 2
        for palabra, resaltada in linea:
            d.text((x, y), palabra, font=letra, fill=TURQUESA if resaltada else BLANCO,
                   stroke_width=8 if sombra else 0, stroke_fill=(10, 14, 18))
            x += letra.getlength(palabra + " ")
        y += round(tam * 1.12)
    return y


def componer(cuadro, rotulo, n_toma, n):
    escala = BANDA_ALTO / cuadro.height
    grande = cuadro.resize((round(cuadro.width * escala), BANDA_ALTO), Image.BICUBIC)
    x = (grande.width - ANCHO) // 2
    banda = grande.crop((x, 0, x + ANCHO, BANDA_ALTO))
    banda = ImageEnhance.Contrast(banda).enhance(1.05)
    fondo = banda.resize((ANCHO, ALTO)).filter(ImageFilter.GaussianBlur(45))
    fondo = ImageEnhance.Brightness(fondo).enhance(0.35).convert("RGBA")
    fondo.paste(banda, (0, BANDA_Y))
    texto(fondo, GANCHO, 215, 84)
    # rótulo de la toma, que entra con un pequeño fundido
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    texto(capa, rotulo, BANDA_Y + BANDA_ALTO + 40, 64, "ExtraBold")
    alfa = min(1.0, n / 6)
    capa.putalpha(capa.getchannel("A").point(lambda a: round(a * alfa)))
    fondo.alpha_composite(capa)
    return fondo.convert("RGB")


def main():
    total = sum(fin - inicio for inicio, fin, _ in TOMAS)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ffmpeg, "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
             "-i", str(MUSICA),
             "-filter_complex", f"[1:a]atrim=0:{total:.2f},afade=t=out:st={total - 1.2:.2f}:d=1.2[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
             str(DESTINO)]
    proceso = subprocess.Popen(orden, stdin=subprocess.PIPE)
    anterior = None
    for i, (inicio, fin, rotulo) in enumerate(TOMAS):
        n_rotulo = 0 if rotulo != anterior else 99
        for n, cuadro in enumerate(fotogramas_de(inicio, fin)):
            proceso.stdin.write(componer(cuadro, rotulo, i, n_rotulo + n).tobytes())
        anterior = rotulo
    proceso.stdin.close()
    if proceso.wait() != 0:
        sys.exit("❌ ffmpeg falló")
    # portada del reel en el perfil (faro encendido con el gancho)
    portada = RAIZ / "contenido" / "portadas" / f"{DESTINO.stem}.jpg"
    portada.parent.mkdir(exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", "0.3", "-i", str(DESTINO), "-frames:v", "1",
                    "-q:v", "2", str(portada)], check=True)
    print(f"✅ {DESTINO.name} ({total:.1f} s)")


if __name__ == "__main__":
    main()
