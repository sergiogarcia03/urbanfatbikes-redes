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
AMARILLO = (255, 212, 0)

# Estilos: que no todos los reels tengan la misma base
ESTILOS = {
    "neon": {"fondos": {"oscuro": ((30, 44, 52), OSCURO), "turquesa": ((16, 70, 74), OSCURO), "rojo": ((60, 24, 28), OSCURO)},
             "anillos": TURQUESA, "texto": BLANCO, "resalta": TURQUESA, "borde": (8, 12, 16), "velo": (0, 0, 0, 150)},
    "aviso": {"fondos": {"oscuro": ((34, 34, 34), (8, 8, 8)), "turquesa": ((52, 48, 8), (8, 8, 8)), "rojo": ((80, 12, 12), (12, 4, 4))},
              "rayas": AMARILLO, "texto": BLANCO, "resalta": AMARILLO, "borde": (0, 0, 0), "velo": (0, 0, 0, 160)},
    "claro": {"fondos": {"oscuro": ((232, 241, 242), (255, 255, 255)), "turquesa": ((196, 236, 237), (248, 255, 255)),
                         "rojo": ((252, 220, 220), (255, 248, 248))},
              "anillos": (12, 150, 156), "texto": (18, 25, 30), "resalta": (10, 140, 146), "borde": (255, 255, 255),
              "velo": (255, 255, 255, 110)},
    "caja": {"fondos": {"oscuro": ((22, 30, 36), (10, 14, 18)), "turquesa": ((20, 84, 88), (10, 30, 34)), "rojo": ((90, 30, 34), (20, 10, 12))},
             "puntos": True, "texto": (12, 16, 20), "resalta": (12, 16, 20), "caja": BLANCO, "caja_resalta": TURQUESA,
             "borde": None, "velo": (0, 0, 0, 90)},
}

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
    lienzo = degradado(*ESTILOS["neon"]["fondos"]["oscuro"])
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


def degradado(arriba, abajo):
    lienzo = Image.new("RGBA", (ANCHO, ALTO))
    d = ImageDraw.Draw(lienzo)
    for y in range(0, ALTO, 4):
        f = y / ALTO
        c = tuple(round(a + (b - a) * f) for a, b in zip(arriba, abajo))
        d.rectangle((0, y, ANCHO, y + 4), fill=c)
    return lienzo


_degradados = {}


def fondo_liso(estilo, color, t):
    e = ESTILOS[estilo]
    clave = (estilo, color)
    if clave not in _degradados:
        _degradados[clave] = degradado(*e["fondos"][color])
    lienzo = _degradados[clave].copy()
    d = ImageDraw.Draw(lienzo)
    if e.get("anillos"):  # anillos que se mueven despacio, para que nunca esté quieto
        for k in range(3):
            r = 260 + 120 * k + 30 * math.sin(t * 2 + k)
            cx = ANCHO / 2 + 200 * math.cos(t * 0.8 + k * 2.1)
            cy = ALTO * 0.55 + 300 * math.sin(t * 0.6 + k * 2.1)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=e["anillos"] + (70,), width=5)
    if e.get("rayas"):  # cinta de aviso amarilla y negra que corre
        for y0 in (120, ALTO - 260):
            d.rectangle((0, y0, ANCHO, y0 + 70), fill=e["rayas"])
            for k in range(-2, 16):
                x = k * 90 + (t * 160) % 90
                d.polygon([(x, y0 + 70), (x + 40, y0 + 70), (x + 80, y0), (x + 40, y0)], fill=(0, 0, 0))
    if e.get("puntos"):
        for k in range(40):
            x = (k * 263 + t * 30) % ANCHO
            y = (k * 457) % ALTO
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255, 40))
    return lienzo


def fondo_color(spec, t, dur, estilo="neon"):
    return fondo_liso(estilo, spec.get("color", "oscuro"), t)


# --- Escenas dibujadas (las de «Mi historia») y iconos ---------------------------

_escena = {}


def modulos_avatar():
    if not _escena:
        sys.path.insert(0, str(RAIZ / "herramientas" / "avatar"))
        argv, sys.argv = sys.argv, ["x", "foto"]
        try:
            import cairosvg
            import cuerpo_entero as C
            import historia as H
            import personaje as P
        finally:
            sys.argv = argv
        _escena.update(cairosvg=cairosvg, C=C, H=H, P=P, caras=H.caras(400))
    return _escena


def fondo_escena(spec, t, dur):
    """Escena animada dibujada con código: calle de Holanda, Sergio en fatbike, legal o trucada..."""
    m = modulos_avatar()
    H, P, C = m["H"], m["P"], m["C"]
    nombre = spec["escena"]
    largo = dict((a, b) for a, b, _ in H.ESCENAS)[nombre]
    te = spec.get("desde", 0.0) + t
    cara = m["caras"][min(int(te * FPS), len(m["caras"]) - 1)]
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'
           + P.defs() + C.defs_extra() + H.defs_escenas() + H.FUNCIONES[nombre](min(te, largo), largo, cara) + '</svg>')
    img = Image.open(BytesIO(m["cairosvg"].svg2png(bytestring=svg.encode()))).convert("RGBA")
    if nombre == "comparar":  # más pequeño y abajo: el texto no lo pisa y se ve entero
        esc = 0.8
        peque = img.resize((int(img.width * esc), int(img.height * esc)), Image.LANCZOS)
        lienzo = img.filter(ImageFilter.GaussianBlur(30))  # el mismo dibujo desenfocado de fondo, sin marco
        lienzo.alpha_composite(peque, ((img.width - peque.width) // 2, img.height - peque.height - 40))
        img = lienzo
    return img


def svg_icono(nombre, t, valor):
    """Iconos dibujados (vectores propios), centrados en 540, 1250."""
    p = suave(t / 0.6)
    prohibido = ('<circle cx="540" cy="1250" r="330" fill="none" stroke="#eb4c4c" stroke-width="44"/>'
                 '<line x1="307" y1="1017" x2="773" y2="1483" stroke="#eb4c4c" stroke-width="44"/>')
    if nombre == "velocimetro":
        maximo, v = 45.0, float(valor or 25) * p
        arco = []
        for k in range(0, 46, 5):
            a = math.radians(210 - 240 * k / maximo)
            x1, y1 = 540 + 300 * math.cos(a), 1300 - 300 * math.sin(a)
            x2, y2 = 540 + 340 * math.cos(a), 1300 - 340 * math.sin(a)
            color = "#eb4c4c" if k > 25 else "#ffffff"
            arco.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="14" stroke-linecap="round"/>')
        a = math.radians(210 - 240 * v / maximo)
        return (f'<circle cx="540" cy="1300" r="380" fill="#10181d" stroke="#32c6ca" stroke-width="16"/>' + "".join(arco)
                + f'<line x1="540" y1="1300" x2="{540 + 280 * math.cos(a):.0f}" y2="{1300 - 280 * math.sin(a):.0f}" '
                f'stroke="#ffd400" stroke-width="22" stroke-linecap="round"/><circle cx="540" cy="1300" r="40" fill="#ffd400"/>'
                f'<text x="540" y="1520" font-family="Montserrat" font-weight="900" font-size="120" fill="#ffffff" '
                f'text-anchor="middle">{v:.0f} km/h</text>')
    if nombre == "multa":
        giro = -8 + 6 * (1 - p)
        y = 1250 + 500 * (1 - p)
        return (f'<g transform="translate(540 {y:.0f}) rotate({giro:.1f})">'
                '<rect x="-300" y="-380" width="600" height="760" rx="24" fill="#fffdf4" stroke="#222" stroke-width="6"/>'
                '<rect x="-300" y="-380" width="600" height="150" rx="24" fill="#eb4c4c"/>'
                '<text x="0" y="-270" font-family="Montserrat" font-weight="900" font-size="96" fill="#fff" text-anchor="middle">MULTA</text>'
                + "".join(f'<rect x="-240" y="{-180 + k * 70}" width="{480 - (k % 2) * 140}" height="22" rx="11" fill="#c9cfd3"/>' for k in range(5))
                + f'<text x="0" y="300" font-family="Montserrat" font-weight="900" font-size="{150 if len(str(valor or "")) <= 5 else 110}" fill="#eb4c4c" text-anchor="middle">{valor or ""}</text></g>')
    if nombre == "auriculares":
        return ('<path d="M330 1300 Q330 980 540 980 Q750 980 750 1300" fill="none" stroke="#ffffff" stroke-width="40"/>'
                '<rect x="280" y="1260" width="120" height="200" rx="40" fill="#32c6ca"/>'
                '<rect x="680" y="1260" width="120" height="200" rx="40" fill="#32c6ca"/>' + (prohibido if p > 0.5 else ""))
    if nombre == "movil":
        return ('<rect x="420" y="1000" width="240" height="460" rx="40" fill="#1d262c" stroke="#ffffff" stroke-width="16"/>'
                '<rect x="450" y="1050" width="180" height="340" rx="10" fill="#32c6ca"/>' + (prohibido if p > 0.5 else ""))
    if nombre == "cerveza":
        nivel = 1150 + 200 * (1 - p)
        return ('<rect x="390" y="1060" width="280" height="420" rx="30" fill="#ffffff" fill-opacity=".25" stroke="#ffffff" stroke-width="14"/>'
                f'<rect x="404" y="{nivel:.0f}" width="252" height="{1466 - nivel:.0f}" fill="#f5b400"/>'
                '<path d="M670 1150 h70 q40 0 40 40 v120 q0 40 -40 40 h-70" fill="none" stroke="#ffffff" stroke-width="14"/>'
                '<ellipse cx="530" cy="1070" rx="150" ry="50" fill="#ffffff"/>' + (prohibido if p > 0.8 else ""))
    if nombre == "luces":
        haz = 0.35 + 0.65 * p
        return (f'<polygon points="600,1250 1080,1000 1080,1500" fill="#fff6c8" fill-opacity="{0.5 * haz:.2f}"/>'
                '<circle cx="520" cy="1250" r="120" fill="#ffffff" stroke="#32c6ca" stroke-width="20"/>'
                f'<circle cx="160" cy="1250" r="70" fill="#eb4c4c" fill-opacity="{haz:.2f}"/>'
                '<rect x="150" y="1360" width="400" height="20" rx="10" fill="#ffffff" fill-opacity=".4"/>')
    if nombre == "matricula":
        x = -1040 + 1040 * p
        return (f'<g transform="translate({x:.0f} 0)"><rect x="40" y="1150" width="1000" height="230" rx="24" fill="#ffffff" stroke="#111" stroke-width="10"/>'
                '<rect x="40" y="1150" width="120" height="230" rx="24" fill="#1a49a8"/>'
                '<text x="100" y="1340" font-family="Montserrat" font-weight="900" font-size="60" fill="#fff" text-anchor="middle">E</text>'
                '<text x="600" y="1330" font-family="Montserrat" font-weight="900" font-size="150" fill="#111" text-anchor="middle">1234 ABC</text></g>')
    if nombre == "bateria":
        nivel = 0.5 if valor == "media" else p
        color = "#2ecc71" if nivel > 0.3 else "#eb4c4c"
        return ('<rect x="320" y="1060" width="440" height="420" rx="40" fill="none" stroke="#ffffff" stroke-width="22"/>'
                '<rect x="470" y="1010" width="140" height="60" rx="14" fill="#ffffff"/>'
                f'<rect x="350" y="{1450 - 360 * nivel:.0f}" width="380" height="{360 * nivel:.0f}" rx="20" fill="{color}"/>')
    if nombre == "enchufe":
        return ('<rect x="440" y="1050" width="200" height="260" rx="40" fill="#ffffff"/>'
                '<rect x="480" y="980" width="30" height="90" fill="#ffffff"/><rect x="570" y="980" width="30" height="90" fill="#ffffff"/>'
                '<path d="M540 1310 v120 q0 80 -80 80 h-200" fill="none" stroke="#ffffff" stroke-width="26"/>'
                f'<polygon points="560,1100 500,1200 545,1200 520,1280 590,1170 545,1170" fill="#ffd400" fill-opacity="{p:.2f}"/>')
    if nombre == "cebra":
        return ("".join(f'<rect x="{120 + k * 170}" y="1080" width="110" height="420" fill="#ffffff" fill-opacity="{0.4 + 0.6 * p:.2f}"/>' for k in range(5))
                + '<circle cx="540" cy="1000" r="70" fill="#32c6ca"/>')
    if nombre == "ruedas":
        fina = 30 + 0 * p
        gorda = 30 + 70 * p
        return (f'<circle cx="300" cy="1300" r="200" fill="none" stroke="#ffffff" stroke-width="{fina:.0f}"/>'
                f'<circle cx="780" cy="1300" r="200" fill="none" stroke="#32c6ca" stroke-width="{gorda:.0f}"/>'
                '<text x="300" y="1600" font-family="Montserrat" font-weight="800" font-size="56" fill="#ffffff" text-anchor="middle">normal</text>'
                '<text x="780" y="1600" font-family="Montserrat" font-weight="800" font-size="56" fill="#32c6ca" text-anchor="middle">fatbike</text>')
    if nombre == "silla":
        return ('<rect x="380" y="1100" width="320" height="300" rx="60" fill="#32c6ca"/>'
                '<rect x="420" y="1000" width="240" height="140" rx="50" fill="#32c6ca" fill-opacity=".8"/>'
                '<circle cx="540" cy="930" r="80" fill="#f2c7a5"/>'
                f'<path d="M420 1250 h240" stroke="#ffffff" stroke-width="20" stroke-dasharray="{600 * p:.0f} 600"/>')
    raise SystemExit(f"❌ icono desconocido: {nombre}")


def fondo_icono(spec, t, dur, estilo="neon"):
    lienzo = fondo_liso(estilo, spec.get("color", "oscuro"), t)
    if estilo == "claro":  # los iconos son claros: van sobre una tarjeta oscura
        d = ImageDraw.Draw(lienzo)
        d.rounded_rectangle((110, 850, 970, 1650), radius=60, fill=(22, 32, 38, 255))
    m = modulos_avatar()
    bote = 1 + 0.03 * math.sin(t * 7)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'
           f'<g transform="translate(540 1250) scale({bote:.3f}) translate(-540 -1250)">'
           + svg_icono(spec["icono"], t, spec.get("valor")) + '</g></svg>')
    capa = Image.open(BytesIO(m["cairosvg"].svg2png(bytestring=svg.encode()))).convert("RGBA")
    lienzo.alpha_composite(capa)
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
        m = modulos_avatar()
        cairosvg, C, H, P = m["cairosvg"], m["C"], m["H"], m["P"]
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


def texto_cinetico(lienzo, frase, t, y, tam=112, palabra_cada=0.07, estilo="neon"):
    """Palabras que entran una a una con un pequeño salto (como los subtítulos de TikTok)."""
    e = ESTILOS[estilo]
    letra = fuente("Black", tam)
    lineas = partir(frase, letra, ANCHO - 140)
    alto_linea = round(tam * (1.3 if e.get("caja") else 1.12))
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
            capa = Image.new("RGBA", (int(ancho_p + 60), int(tam * 1.6)), (0, 0, 0, 0))
            dc = ImageDraw.Draw(capa)
            if e.get("caja"):
                fondo = e["caja_resalta"] if resaltada else e["caja"]
                dc.rounded_rectangle((6, 14, ancho_p + 54, tam * 1.38), radius=18, fill=fondo)
                dc.text((30, 10), palabra, font=letra, fill=e["texto"])
            else:
                dc.text((30, 10), palabra, font=letra, fill=e["resalta"] if resaltada else e["texto"],
                        stroke_width=10, stroke_fill=e["borde"])
            if escala != 1:
                capa = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.LANCZOS)
            cx, cy = x + ancho_p / 2, y + k * alto_linea + tam * 0.75
            lienzo.alpha_composite(capa, (int(cx - capa.width / 2), int(cy - capa.height / 2)))
            x += letra.getlength(palabra + " ")
    return y + len(lineas) * alto_linea


def numero_grande(lienzo, texto, t, y, tam=330, estilo="neon"):
    e = ESTILOS[estilo]
    letra = fuente("Black", tam)
    escala = 0.5 + 0.5 * rebote(t / 0.3)
    ancho = letra.getlength(texto)
    capa = Image.new("RGBA", (int(ancho + 60), int(tam * 1.4)), (0, 0, 0, 0))
    color = e.get("caja_resalta", e["resalta"])
    ImageDraw.Draw(capa).text((30, 0), texto, font=letra, fill=color, stroke_width=14, stroke_fill=e["borde"] or (8, 12, 16))
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
    estilo = g.get("estilo", reel.get("estilo", "neon"))
    fondo = g.get("fondo", {"color": "oscuro"})
    if estilo == "claro" and ("foto" in fondo or "video" in fondo or fondo.get("escena") in ("comparar", "mapa", "final")):
        estilo = "neon"  # sobre fotos y vídeos oscuros, letra blanca con borde: se lee mejor
    if "foto" in fondo:
        lienzo = fondo_foto(fondo, t, dur)
    elif "video" in fondo:
        lienzo = fondo_video(fondo, t, dur)
    elif "escena" in fondo:
        lienzo = fondo_escena(fondo, t, dur)
    elif "icono" in fondo:
        lienzo = fondo_icono(fondo, t, dur, estilo)
    else:
        lienzo = fondo_color(fondo, t, dur, estilo)
    # velo arriba para que el texto se lea siempre
    color_velo = ESTILOS[estilo]["velo"]
    velo = Image.new("RGBA", (ANCHO, 900), (0, 0, 0, 0))
    dv = ImageDraw.Draw(velo)
    for y in range(900):
        dv.line((0, y, ANCHO, y), fill=color_velo[:3] + (int(color_velo[3] * (1 - y / 900)),))
    lienzo.alpha_composite(velo)
    if g.get("avatar"):
        poner_avatar(lienzo, g["avatar"], t)
    y = g.get("y", reel.get("texto_y", 330))
    if g.get("numero"):
        numero_grande(lienzo, str(g["numero"]), t, y, 330 if len(str(g["numero"])) <= 3 else 240, estilo)
        y += 420
    if g.get("texto"):
        y = texto_cinetico(lienzo, g["texto"], t, y, g.get("tam", 112), estilo=estilo)
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
    tiempos = [g.get("tiempos", reel.get("tiempos", 2)) for g in reel["golpes"]]
    if "tiempos" not in reel["golpes"][-1]:
        tiempos[-1] += 1  # el cierre se queda un poco más para que dé tiempo a leer la petición
    return [n * pulso for n in tiempos]


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
