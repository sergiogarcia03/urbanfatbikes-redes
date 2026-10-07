"""Reels rápidos: cortes al ritmo de la música, texto que entra palabra a palabra,
tomas de la bici (foto de estudio y vídeo del proveedor sin rótulos) y el avatar
de Sergio reaccionando. Nada de diapositivas: un golpe nuevo cada 2 tiempos.

Lee reels_rapidos.yaml y crea contenido/rapido-<nombre>.mp4 (y su portada en
contenido/portadas/). Solo rehace los que han cambiado.

Uso:
  python reels_rapidos.py               # todos los que falten o hayan cambiado
  python reels_rapidos.py legal         # solo ese
  python reels_rapidos.py --foto legal  # hoja con un fotograma de cada golpe
"""

import hashlib
import json
import math
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from tarjetas import BLANCO, TURQUESA, fuente, partir

RAIZ = Path(__file__).parent
CONTENIDO = RAIZ / "contenido"
DEFINICIONES = RAIZ / "reels_rapidos.yaml"
HUELLAS = CONTENIDO / "reels_rapidos.json"
PORTADAS = CONTENIDO / "portadas"
VIDEO_PROVEEDOR = CONTENIDO / "proveedor" / "v8-detalles-original.mp4"
ANCHO, ALTO, FPS = 1080, 1920, 30
OSCURO = (18, 25, 30)
ROJO = (235, 76, 76)
VERDE = (46, 204, 113)
FM = 44100

# Tempo de cada pista (musica.py): los cortes caen en el ritmo
TEMPO = {"urban-1": 112, "urban-2": 118, "inspira-1": 104, "inspira-2": 96, "tranquila-1": 84}

# Tomas del vídeo del proveedor sin rótulos en inglés (segundos)
TOMAS = {
    "faro": (22.05, 22.45),
    "frontal": (16.0, 18.4),
    "manillar": (2.0, 4.9),
    "pantalla": (5.0, 7.9),
    "suspension": (31.5, 32.4),
}


def suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def rebote(t):
    """Entra pasándose un poco y vuelve (0 → 1)."""
    t = max(0.0, min(1.0, t))
    return 1 - math.cos(t * math.pi * 1.5) * math.exp(-4 * t) if t < 1 else 1.0


def cubrir(img, ancho, alto):
    escala = max(ancho / img.width, alto / img.height)
    img = img.resize((max(ancho, round(img.width * escala)), max(alto, round(img.height * escala))), Image.LANCZOS)
    x, y = (img.width - ancho) // 2, (img.height - alto) // 2
    return img.crop((x, y, x + ancho, y + alto))


# --- Fondos ---------------------------------------------------------------------


_cache = {}


def foto_base(nombre, recorte=None):
    clave = (nombre, tuple(recorte or ()))
    if clave not in _cache:
        img = Image.open(CONTENIDO / nombre).convert("RGBA")
        if recorte:
            img = img.crop(tuple(recorte))
        _cache[clave] = img
    return _cache[clave]


def fondo_foto(spec, t, dur):
    """Foto (de producto sin fondo o normal) a pantalla completa con un empuje lento."""
    img = foto_base(spec["foto"], spec.get("recorte"))
    recortada = img.getchannel("A").getextrema()[0] < 255
    lienzo = degradado(spec.get("tono", 0))
    zoom = 1.0 + 0.10 * (t / max(dur, 0.01)) if spec.get("zoom", "in") == "in" else 1.10 - 0.10 * (t / max(dur, 0.01))
    if recortada:
        # producto sin fondo: grande y centrado en la mitad de abajo
        ancho = int(ANCHO * spec.get("tam", 1.05) * zoom)
        alto = int(img.height * ancho / img.width)
        p = img.resize((ancho, alto), Image.LANCZOS)
        y = int(ALTO * spec.get("y", 0.62) - alto / 2)
        lienzo.alpha_composite(p, ((ANCHO - ancho) // 2, y))
        return lienzo
    base = cubrir(img.convert("RGB"), int(ANCHO * zoom), int(ALTO * zoom))
    x, y = (base.width - ANCHO) // 2, (base.height - ALTO) // 2
    return base.crop((x, y, x + ANCHO, y + ALTO)).convert("RGBA")


_fotogramas = {}


def fotogramas_toma(nombre):
    if nombre not in _fotogramas:
        inicio, fin = TOMAS[nombre]
        orden = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-ss", str(inicio), "-t", str(fin - inicio),
                 "-i", str(VIDEO_PROVEEDOR), "-vf", "crop=1080:608:0:656", "-r", str(FPS),
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        datos = subprocess.run(orden, capture_output=True, check=True).stdout
        tam = 1080 * 608 * 3
        _fotogramas[nombre] = [Image.frombytes("RGB", (1080, 608), datos[i * tam:(i + 1) * tam])
                               for i in range(len(datos) // tam)]
    return _fotogramas[nombre]


def fondo_video(spec, t, dur):
    """Toma del vídeo del proveedor: recorte 3:4 ampliado (fuera la marca de agua) sobre su propio desenfoque."""
    cuadros = fotogramas_toma(spec["video"])
    i = min(int(t * FPS * spec.get("velocidad", 1.0)), len(cuadros) - 1)
    cuadro = cuadros[i]
    ancho = int(608 * 3 / 4)
    x = (1080 - ancho) // 2 + spec.get("desplaza", 0)
    trozo = cuadro.crop((x, 0, x + ancho, 608))
    zoom = 1.0 + 0.06 * (t / max(dur, 0.01))
    alto = int(1500 * zoom)
    trozo = trozo.resize((int(alto * 3 / 4), alto), Image.BICUBIC)
    trozo = ImageEnhance.Contrast(trozo).enhance(1.08)
    fondo = cubrir(cuadro, ANCHO, ALTO).filter(ImageFilter.GaussianBlur(40))
    fondo = ImageEnhance.Brightness(fondo).enhance(0.4).convert("RGBA")
    fondo.paste(trozo, ((ANCHO - trozo.width) // 2, (ALTO - trozo.height) // 2 + 120))
    return fondo


def degradado(tono=0):
    arriba = [(30, 44, 52), (16, 70, 74), (60, 24, 28)][tono]
    lienzo = Image.new("RGBA", (ANCHO, ALTO))
    d = ImageDraw.Draw(lienzo)
    for y in range(0, ALTO, 4):
        f = y / ALTO
        c = tuple(round(a + (b - a) * f) for a, b in zip(arriba, OSCURO))
        d.rectangle((0, y, ANCHO, y + 4), fill=c)
    return lienzo


_degradados = {}


def fondo_color(spec, t, dur):
    tono = {"oscuro": 0, "turquesa": 1, "rojo": 2}[spec.get("color", "oscuro")]
    if tono not in _degradados:
        _degradados[tono] = degradado(tono)
    lienzo = _degradados[tono].copy()
    d = ImageDraw.Draw(lienzo)
    # anillos que giran despacio, para que nunca esté quieto
    for k in range(3):
        r = 260 + 120 * k + 30 * math.sin(t * 2 + k)
        cx = ANCHO / 2 + 200 * math.cos(t * 0.8 + k * 2.1)
        cy = ALTO * 0.55 + 300 * math.sin(t * 0.6 + k * 2.1)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=TURQUESA + (60,), width=5)
    return lienzo


# --- Avatar ---------------------------------------------------------------------

_avatares = {}

POSES = {
    "pie": {},
    "senala": {"brazo_d": -120, "codo_d": -10, "mano_d_tipo": "abierta"},
    "brazos": {"brazo_d": -150, "codo_d": -30, "brazo_i": 150, "codo_i": 30,
               "mano_d_tipo": "abierta", "mano_i_tipo": "abierta"},
    "duda": {"brazo_d": -60, "codo_d": -120, "mano_d_tipo": "cerrada", "cabeza": 8},
    "niega": {"brazo_d": -95, "codo_d": -60, "brazo_i": 95, "codo_i": 60,
           "mano_d_tipo": "abierta", "mano_i_tipo": "abierta"},
}
CARAS = {
    "normal": {},
    "sorpresa": {"boca": 0.9, "cejas": 14, "sonrisa": 0.0},
    "sonrie": {"boca": 0.25, "sonrisa": 1.0},
    "serio": {"boca": 0.0, "cejas": -6, "sonrisa": -0.3},
}


def avatar(pose, cara):
    """El avatar de Sergio (dibujado con código, no realista) con fondo transparente."""
    clave = (pose, cara)
    if clave not in _avatares:
        sys.path.insert(0, str(RAIZ / "herramientas" / "avatar"))
        argv, sys.argv = sys.argv, ["x", "foto"]
        try:
            import cairosvg
            import cuerpo_entero as C
            import historia as H
            import personaje as P
        finally:
            sys.argv = argv
        base = H.caras(40)[20]
        c = dict(base, **CARAS[cara])
        p = dict(C.POSTURA_PIE, **POSES[pose], x=540, y=1150, esc=1.0, sombra=False)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'
               + P.defs() + C.defs_extra() + H.defs_escenas() + C.dibujar(p, c) + '</svg>')
        img = Image.open(BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert("RGBA")
        _avatares[clave] = img.crop(img.getbbox())
    return _avatares[clave]


def poner_avatar(lienzo, spec, t):
    img = avatar(spec.get("pose", "pie"), spec.get("cara", "normal"))
    alto = int(ALTO * spec.get("tam", 0.42))
    img = img.resize((int(img.width * alto / img.height), alto), Image.LANCZOS)
    lado = spec.get("lado", "derecha")
    entra = rebote(t / 0.35)
    x_final = ANCHO - img.width - 40 if lado == "derecha" else 40
    x_fuera = ANCHO if lado == "derecha" else -img.width
    x = int(x_fuera + (x_final - x_fuera) * entra)
    bote = int(10 * math.sin(t * 9))  # se mueve al ritmo
    y = ALTO - alto - 170 + bote
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse((x + img.width * .15, y + alto - 18, x + img.width * .85, y + alto + 18), fill=(0, 0, 0, 90))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(8)))
    lienzo.alpha_composite(img, (x, y))


# --- Texto y pegatinas ----------------------------------------------------------


def texto_cinetico(lienzo, frase, t, y, tam=112, palabra_cada=0.07):
    """Palabras que entran una a una con un pequeño salto (como los subtítulos de TikTok)."""
    letra = fuente("Black", tam)
    lineas = partir(frase, letra, ANCHO - 140)
    alto_linea = round(tam * 1.12)
    d_total = ImageDraw.Draw(lienzo)
    n = 0
    for k, linea in enumerate(lineas):
        total = letra.getlength(" ".join(p for p, _ in linea))
        x = (ANCHO - total) / 2
        for palabra, resaltada in linea:
            aparece = (t - n * palabra_cada) / 0.18
            n += 1
            if aparece <= 0:
                x += letra.getlength(palabra + " ")
                continue
            escala = 0.6 + 0.4 * rebote(aparece)
            ancho_p = letra.getlength(palabra)
            capa = Image.new("RGBA", (int(ancho_p + 40), int(tam * 1.5)), (0, 0, 0, 0))
            ImageDraw.Draw(capa).text((20, 10), palabra, font=letra, fill=TURQUESA if resaltada else BLANCO,
                                      stroke_width=10, stroke_fill=(8, 12, 16))
            if escala != 1:
                capa = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.LANCZOS)
            cx, cy = x + ancho_p / 2, y + k * alto_linea + tam * 0.75
            lienzo.alpha_composite(capa, (int(cx - capa.width / 2), int(cy - capa.height / 2)))
            x += letra.getlength(palabra + " ")
    del d_total
    return y + len(lineas) * alto_linea


def numero_grande(lienzo, texto, t, y, tam=330):
    letra = fuente("Black", tam)
    escala = 0.5 + 0.5 * rebote(t / 0.3)
    ancho = letra.getlength(texto)
    capa = Image.new("RGBA", (int(ancho + 60), int(tam * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((30, 0), texto, font=letra, fill=TURQUESA, stroke_width=14, stroke_fill=(8, 12, 16))
    capa = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.LANCZOS)
    lienzo.alpha_composite(capa, ((ANCHO - capa.width) // 2, int(y + tam * 0.7 - capa.height / 2)))


def pegatina(lienzo, tipo, t, x, y, r=95):
    """✅ o ❌ dibujados (la letra no tiene emojis)."""
    escala = rebote(t / 0.3)
    if escala <= 0.02:
        return
    rr = r * escala
    capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    color = VERDE if tipo == "si" else ROJO
    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=color + (255,), outline=(255, 255, 255, 255), width=8)
    w = max(4, int(18 * escala))
    if tipo == "si":
        d.line((x - rr * .45, y, x - rr * .1, y + rr * .38, x + rr * .5, y - rr * .38), fill="white", width=w, joint="curve")
    else:
        d.line((x - rr * .4, y - rr * .4, x + rr * .4, y + rr * .4), fill="white", width=w)
        d.line((x - rr * .4, y + rr * .4, x + rr * .4, y - rr * .4), fill="white", width=w)
    lienzo.alpha_composite(capa)


# --- Montaje --------------------------------------------------------------------


def golpe_en(golpes, duraciones, t):
    acumulado = 0.0
    for i, d in enumerate(duraciones):
        if t < acumulado + d or i == len(duraciones) - 1:
            return i, t - acumulado
        acumulado += d


def fotograma(reel, i, t, dur):
    g = reel["golpes"][i]
    fondo = g.get("fondo", {"color": "oscuro"})
    if "foto" in fondo:
        lienzo = fondo_foto(fondo, t, dur)
    elif "video" in fondo:
        lienzo = fondo_video(fondo, t, dur)
    else:
        lienzo = fondo_color(fondo, t, dur)
    # velo arriba para que el texto se lea siempre
    velo = Image.new("RGBA", (ANCHO, 900), (0, 0, 0, 0))
    dv = ImageDraw.Draw(velo)
    for y in range(900):
        dv.line((0, y, ANCHO, y), fill=(0, 0, 0, int(150 * (1 - y / 900))))
    lienzo.alpha_composite(velo)
    if g.get("avatar"):
        poner_avatar(lienzo, g["avatar"], t)
    y = g.get("y", 330)
    if g.get("numero"):
        numero_grande(lienzo, str(g["numero"]), t, y, 330 if len(str(g["numero"])) <= 3 else 240)
        y += 420
    if g.get("texto"):
        y = texto_cinetico(lienzo, g["texto"], t, y, g.get("tam", 112))
    if g.get("pegatina"):
        pegatina(lienzo, g["pegatina"], t - 0.15, ANCHO // 2, y + 120)
    # golpe de cámara al cortar: zoom que se recoge y un destello corto
    golpe = 1.0 + 0.08 * (1 - suave(t / 0.22))
    img = lienzo.convert("RGB")
    if golpe > 1.001:
        w, h = int(ANCHO * golpe), int(ALTO * golpe)
        img = img.resize((w, h), Image.BILINEAR)
        img = img.crop(((w - ANCHO) // 2, (h - ALTO) // 2, (w - ANCHO) // 2 + ANCHO, (h - ALTO) // 2 + ALTO))
    if t < 0.07 and i > 0:
        img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.35 * (1 - t / 0.07))
    return img


def duraciones_de(reel):
    pulso = 60 / TEMPO[reel["musica"]]
    return [g.get("tiempos", 2) * pulso for g in reel["golpes"]]


def silbido(n, semilla):
    """«Whoosh» de transición hecho con ruido filtrado (sin muestras de terceros)."""
    rng = np.random.default_rng(semilla)
    ruido = rng.standard_normal(n)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    suave_ = np.convolve(ruido, np.ones(9) / 9, mode="same")
    return (suave_ * env * 0.35).astype(np.float32)


def audio(reel, duraciones, destino):
    total = sum(duraciones)
    pista = CONTENIDO / "musica" / f"{reel['musica']}.m4a"
    datos = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", str(pista), "-ac", "2",
                            "-ar", str(FM), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    musica = np.frombuffer(datos, np.float32).reshape(-1, 2).copy()
    n = int(total * FM)
    while len(musica) < n:
        musica = np.concatenate([musica, musica])
    mezcla = musica[:n] * 0.9
    t = 0.0
    for i, d in enumerate(duraciones[:-1]):
        t += d
        m = int(0.28 * FM)
        a = max(0, int((t - 0.18) * FM))
        s = silbido(min(m, n - a), i)
        mezcla[a:a + len(s)] += s[:, None]
    caida = int(0.8 * FM)
    mezcla[-caida:] *= np.linspace(1, 0, caida)[:, None]
    mezcla = np.clip(mezcla, -1, 1)
    destino.write_bytes(mezcla.astype(np.float32).tobytes())


def generar(nombre, reel):
    duraciones = duraciones_de(reel)
    total = sum(duraciones)
    destino = CONTENIDO / f"rapido-{nombre}.mp4"
    crudo = CONTENIDO / f".rapido-{nombre}.f32"
    audio(reel, duraciones, crudo)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ff, "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
             "-f", "f32le", "-ar", str(FM), "-ac", "2", "-i", str(crudo),
             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(destino)]
    proceso = subprocess.Popen(orden, stdin=subprocess.PIPE)
    PORTADAS.mkdir(exist_ok=True)
    for k in range(int(total * FPS)):
        t = k / FPS
        i, tl = golpe_en(reel["golpes"], duraciones, t)
        img = fotograma(reel, i, tl, duraciones[i])
        if k == int(min(0.75, duraciones[0] - 0.05) * FPS):
            img.save(PORTADAS / f"{destino.stem}.jpg", quality=90)
        proceso.stdin.write(img.tobytes())
    proceso.stdin.close()
    ok = proceso.wait() == 0
    crudo.unlink()
    if not ok:
        sys.exit(f"❌ {nombre}: ffmpeg falló")
    print(f"✅ {destino.name} ({total:.1f} s, {len(duraciones)} golpes)")


def hoja(nombre, reel):
    duraciones = duraciones_de(reel)
    cuadros = [fotograma(reel, i, min(0.6, d - 0.05), d).resize((216, 384)) for i, d in enumerate(duraciones)]
    h = Image.new("RGB", (216 * min(6, len(cuadros)), 384 * math.ceil(len(cuadros) / 6)), (255, 255, 255))
    for k, c in enumerate(cuadros):
        h.paste(c, ((k % 6) * 216, (k // 6) * 384))
    h.save(f"hoja-{nombre}.jpg", quality=85)
    print(f"🖼  hoja-{nombre}.jpg ({sum(duraciones):.1f} s)")


def huella(reel):
    h = hashlib.sha256(json.dumps(reel, sort_keys=True, ensure_ascii=False).encode())
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()


def main():
    args = sys.argv[1:]
    reels = yaml.safe_load(DEFINICIONES.read_text(encoding="utf-8"))["reels"]
    if args and args[0] == "--foto":
        for nombre in args[1:]:
            hoja(nombre, reels[nombre])
        return
    huellas = json.loads(HUELLAS.read_text()) if HUELLAS.exists() else {}
    for nombre, reel in reels.items():
        if args and nombre not in args:
            continue
        nueva = huella(reel)
        if huellas.get(nombre) == nueva and (CONTENIDO / f"rapido-{nombre}.mp4").exists():
            print(f"= rapido-{nombre}.mp4 ya está al día")
            continue
        generar(nombre, reel)
        huellas[nombre] = nueva
        HUELLAS.write_text(json.dumps(huellas, indent=1) + "\n")


if __name__ == "__main__":
    main()
