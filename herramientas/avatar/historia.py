"""Vídeo animado «Mi historia»: Sergio de cuerpo entero en 6 escenas, con su voz.

Escenas: sofá en Valencia → aeropuerto y avión → Holanda (fatbikes por la calle)
→ en fatbike → de Holanda a España → saludo final con el logo.
Todo dibujado con código (vectores), sin imágenes hechas con IA.
"""

import math
import random
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import cairosvg
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cuerpo_entero as C
import personaje as P

ANCHO, ALTO = 1080, 1920
FPS = int(sys.argv[4]) if len(sys.argv) > 4 else 30
RAIZ = Path(__file__).resolve().parents[2]
FUENTE = RAIZ / "fuentes" / "Montserrat.ttf"
LOGO = RAIZ / "contenido" / "logo-urbanfatbikes.png"

GANCHO = "¿Legal o trucada? En Holanda aprendí a verlo"
ESCENAS = [  # (nombre, duración en segundos, subtítulo)
    ("sofa", 2.2, "De aburrirme en el sofá, en Valencia…"),
    ("aeropuerto", 2.4, "…a descubrir las fatbikes en Holanda."),
    ("holanda", 3.8, "Me fui a trabajar allí, y estaban por todas partes."),
    ("comparar", 3.6, "Vi de todo: las legales… y las trucadas que dan problemas."),
    ("bici", 2.8, "Me enganché, y aprendí a distinguirlas."),
    ("mapa", 4.6, "Ahora quiero llevar a España las buenas: de 250 W y ensayadas según la norma europea EN 15194."),
    ("final", 3.8, "Soy Sergio, de urbanfatbikes. En el próximo vídeo te enseño a distinguirlas."),
]


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def entre(t, a, b):
    return suave((t - a) / (b - a)) if b > a else float(t >= a)


# --- Objetos ---------------------------------------------------------------------------

def fatbike(x, y, esc=1.0, giro_ruedas=0.0, color="#1f2226", acento=P.TURQ, voltea=1):
    """Fatbike de perfil mirando a la derecha. (x, y) = suelo bajo el centro de la bici."""
    def rueda(cx):
        marcas = "".join(
            f'<rect x="-6" y="-84" width="12" height="16" rx="3" fill="#2c2f33" transform="rotate({giro_ruedas + k * 30:.1f})"/>'
            for k in range(12))
        return (f'<g transform="translate({cx} -82)"><circle r="82" fill="#121416"/>{marcas}'
                f'<circle r="56" fill="none" stroke="#3b4046" stroke-width="10"/>'
                f'<circle r="50" fill="none" stroke="#6c737b" stroke-width="3"/>'
                f'<circle r="12" fill="#8a929a"/></g>')
    return f'''<g transform="translate({x:.1f} {y:.1f}) scale({esc * voltea:.3f} {esc:.3f})">
<ellipse cx="0" cy="4" rx="260" ry="16" fill="#000" opacity=".22"/>
{rueda(-175)}{rueda(175)}
<path d="M-260 -150 Q-175 -190 -95 -150" stroke="{color}" stroke-width="14" fill="none" stroke-linecap="round"/>
<path d="M95 -150 Q175 -190 255 -150" stroke="{color}" stroke-width="14" fill="none" stroke-linecap="round"/>
<path d="M-175 -82 L-20 -95 L130 -235 M-175 -82 L-100 -215 M-20 -95 L-60 -215" stroke="{color}" stroke-width="16" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="-110" y="-238" width="230" height="44" rx="14" fill="{color}"/>
<rect x="-96" y="-222" width="150" height="8" rx="4" fill="{acento}"/>
<path d="M175 -82 L132 -250" stroke="#2d3136" stroke-width="18" stroke-linecap="round"/>
<path d="M132 -250 L118 -330 L80 -336" stroke="{color}" stroke-width="12" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="60" y="-344" width="34" height="16" rx="8" fill="#111"/>
<circle cx="160" cy="-268" r="24" fill="#2d3136"/><circle cx="166" cy="-268" r="15" fill="#fff6d8"/>
<rect x="-168" y="-266" width="210" height="34" rx="16" fill="#3a2a22"/>
<path d="M-160 -258 Q-60 -268 34 -258" stroke="#5a463a" stroke-width="5" fill="none"/>
<circle cx="-20" cy="-95" r="16" fill="#3b4046"/>
</g>'''


def maleta(x, y, esc=1.0, ang=0.0):
    return f'''<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.2f}) scale({esc:.3f})">
<path d="M-6 0 L-6 -150 L6 -150 L6 0" stroke="#9aa1a8" stroke-width="8" fill="none"/>
<rect x="-30" y="-158" width="60" height="14" rx="6" fill="#2c3036"/>
<rect x="-70" y="0" width="140" height="190" rx="22" fill="{P.TURQ}"/>
<rect x="-70" y="0" width="140" height="190" rx="22" fill="url(#brilloMaleta)"/>
<path d="M-40 20 L-40 170 M0 20 L0 170 M40 20 L40 170" stroke="#2aa3a3" stroke-width="6"/>
<circle cx="-46" cy="198" r="12" fill="#222"/><circle cx="46" cy="198" r="12" fill="#222"/>
</g>'''


def movil(x, y, ang, brillo):
    return (f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.1f})">'
            f'<rect x="-24" y="-10" width="48" height="84" rx="9" fill="#15171a"/>'
            f'<rect x="-19" y="-4" width="38" height="70" rx="5" fill="#7fd6ff" opacity="{brillo:.2f}"/></g>')


def avion(x, y, esc, ang=0):
    return f'''<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.1f}) scale({esc:.3f})">
<path d="M-180 0 Q-170 -34 -100 -36 L150 -36 Q210 -34 230 0 Q210 30 150 32 L-100 32 Q-170 30 -180 0Z" fill="#f4f6f8"/>
<path d="M-30 -10 L-110 -150 L-60 -150 L60 -10Z" fill="#d9dee3"/>
<path d="M-30 14 L-80 110 L-40 110 L40 14Z" fill="#c9cfd6"/>
<path d="M-160 -10 L-200 -110 L-160 -110 L-110 -20Z" fill="{P.TURQ}"/>
<path d="M180 -14 Q205 -10 214 0 L180 0Z" fill="#2a3840"/>
{"".join(f'<circle cx="{k}" cy="-8" r="7" fill="#2a3840"/>' for k in range(-80, 150, 26))}
</g>'''


def nube(x, y, esc, op=0.9):
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({esc:.3f})" opacity="{op}">'
            f'<ellipse cx="0" cy="0" rx="120" ry="44" fill="#fff"/><circle cx="-40" cy="-24" r="46" fill="#fff"/>'
            f'<circle cx="30" cy="-36" r="58" fill="#fff"/></g>')


def bandera(x, y, colores, esc=1.0, t=0.0):
    franjas = ""
    alto = 120 / len(colores)
    for k, c in enumerate(colores):
        franjas += (f'<path d="M0 {k * alto:.1f} Q45 {k * alto + 8 * math.sin(t * 4):.1f} 90 {k * alto:.1f} L90 {(k + 1) * alto:.1f} '
                    f'Q45 {(k + 1) * alto + 8 * math.sin(t * 4):.1f} 0 {(k + 1) * alto:.1f}Z" fill="{c}"/>')
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({esc:.3f})"><rect x="-8" y="0" width="8" height="300" fill="#ddd"/>'
            f'<g transform="translate(0 0) scale(1.6)">{franjas}</g></g>')


def defs_escenas():
    return f'''<defs>
<linearGradient id="pared" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6dfc2"/><stop offset="1" stop-color="#e9c49c"/></linearGradient>
<linearGradient id="suelo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b98457"/><stop offset="1" stop-color="#8c5c38"/></linearGradient>
<linearGradient id="cieloV" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5fb4f0"/><stop offset="1" stop-color="#bfe6ff"/></linearGradient>
<linearGradient id="cieloH" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9fb7c9"/><stop offset="1" stop-color="#dfe8ee"/></linearGradient>
<linearGradient id="sofa" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e07a4b"/><stop offset="1" stop-color="#b9552c"/></linearGradient>
<linearGradient id="terminal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9edf0"/><stop offset="1" stop-color="#c5ccd2"/></linearGradient>
<linearGradient id="agua" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f7a8f"/><stop offset="1" stop-color="#2f5566"/></linearGradient>
<linearGradient id="brilloMaleta" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".25"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>
<radialGradient id="luzLampara" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff3c4" stop-opacity=".55"/><stop offset="1" stop-color="#fff3c4" stop-opacity="0"/></radialGradient>
<radialGradient id="luzMovil" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#7fd6ff" stop-opacity=".35"/><stop offset="1" stop-color="#7fd6ff" stop-opacity="0"/></radialGradient>
</defs>'''


# --- Escenas ---------------------------------------------------------------------------
# Cada una devuelve el SVG (sin el <svg> de fuera) para el tiempo t dentro de la escena.

def casas_canal(desp, y, esc=1.0, semilla=1):
    rng = random.Random(semilla)
    colores = ["#8c3b2e", "#2f4f45", "#22374a", "#b5823c", "#5a2f2a", "#3e5b6b", "#7d4b2d"]
    svg = ""
    x = -desp % 220 - 220
    k = int(desp // 220)
    while x < 1080 / esc + 220:
        r = random.Random(semilla * 1000 + k)
        c = colores[r.randrange(len(colores))]
        alto = r.randint(430, 560)
        top = y - alto
        tipo = r.randrange(3)
        if tipo == 0:
            tejado = f"M{x} {top} L{x + 30} {top} L{x + 30} {top - 40} L{x + 70} {top - 40} L{x + 70} {top - 90} L{x + 150} {top - 90} L{x + 150} {top - 40} L{x + 190} {top - 40} L{x + 190} {top} L{x + 220} {top}"
        elif tipo == 1:
            tejado = f"M{x} {top} L{x + 110} {top - 110} L{x + 220} {top}"
        else:
            tejado = f"M{x} {top} Q{x + 110} {top - 140} {x + 220} {top}"
        ventanas = ""
        for fila in range(4):
            for col in range(3):
                wy = top + 30 + fila * (alto - 60) / 4
                if wy > y - 60:
                    continue
                ventanas += f'<rect x="{x + 30 + col * 62}" y="{wy:.0f}" width="40" height="66" rx="4" fill="#f4efe6"/><rect x="{x + 34 + col * 62}" y="{wy + 4:.0f}" width="32" height="58" fill="#3b4a55"/>'
        svg += f'<path d="{tejado} L{x + 220} {y} L{x} {y}Z" fill="{c}"/>' + ventanas
        svg += f'<path d="{tejado}" stroke="#f4efe6" stroke-width="6" fill="none"/>'
        x += 220
        k += 1
    return f'<g transform="scale({esc})">{svg}</g>'


def rebote(x):
    """Sube con un pequeño impulso: se pasa un poco y vuelve (animación con «overshoot»)."""
    x = max(0.0, min(1.0, x))
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def sentado(t):
    # hundido en el sofá: rodillas abiertas, un brazo sobre la pierna y el móvil en la otra mano
    return dict(C.POSTURA_PIE, muslo_i=34, rodilla_i=-36, muslo_d=-34, rodilla_d=36, escorzo=0.45,
                brazo_i=14, codo_i=-48, brazo_d=-16, codo_d=-112, cabeza=-6, inclina=-3)


def escena_sofa(t, dur, cara):
    # Corto y con gestos: desliza el dedo por el móvil, suspira, se hunde... y se levanta de golpe.
    reloj = t * 120
    suspiro = math.sin(math.pi * entre(t, 0.45 * dur, 0.75 * dur))  # hombros arriba y abajo
    antic = entre(t, dur - 0.55, dur - 0.42) * (1 - entre(t, dur - 0.42, dur - 0.3))  # se encoge antes de levantarse
    levanta = rebote(entre(t, dur - 0.42, dur - 0.05))
    cara = dict(cara, parpadeo=max(cara["parpadeo"], 0.45 * (1 - levanta)), gy=cara["gy"] + 5 * (1 - levanta),
                cejas=cara["cejas"] - 6 * (1 - levanta) + 10 * levanta)
    p = sentado(t)
    p.update(x=540, y=1310 + 10 * suspiro + 14 * antic, esc=1.05, suelo=270)
    p["codo_d"] += 6 * math.sin(t * 14) * (1 - levanta)          # el pulgar desliza
    p["inclina"] += -3 * suspiro
    p = C.mezcla(p, dict(C.POSTURA_PIE, x=540, y=1190, esc=1.05, suelo=420), levanta)
    p["cabeza"] = (1 - levanta) * (-5 - 4 * suspiro)
    p["sombra"] = False
    brillo = 0.75 + 0.2 * math.sin(t * 9) * math.sin(t * 2.3)
    zoom = 1.0 + 0.05 * t / dur

    def objetos(lado, x, y):
        if lado > 0 and levanta < 0.5:
            return movil(x + 4, y - 30, 8, brillo)
    personaje = C.dibujar(p, cara, objetos)
    luz = f'<ellipse cx="540" cy="1000" rx="170" ry="140" fill="url(#luzMovil)" opacity="{(1 - levanta) * brillo:.2f}"/>'
    return f'''<g transform="translate(540 1100) scale({zoom:.4f}) translate(-540 -1100)">
<rect width="1080" height="1920" fill="url(#pared)"/>
<rect y="1480" width="1080" height="440" fill="url(#suelo)"/>
{"".join(f'<path d="M0 {1480 + k * 64} L1080 {1480 + k * 64}" stroke="#7a4f30" stroke-width="3" opacity=".4"/>' for k in range(1, 8))}
<rect x="90" y="560" width="380" height="420" rx="10" fill="#fff"/>
<rect x="110" y="580" width="340" height="380" fill="url(#cieloV)"/>
<circle cx="380" cy="650" r="42" fill="#ffd45a"/>
<path d="M110 960 L110 880 L170 880 L170 840 L230 840 L230 900 L300 900 L300 860 L350 860 L350 960Z" fill="#e8d8c0"/>
<path d="M350 960 L350 890 L450 890 L450 960Z" fill="#f2e4cf"/>
<path d="M260 960 Q270 860 300 790" stroke="#7a5a3a" stroke-width="12" fill="none"/>
<path d="M300 790 Q250 770 220 810 M300 790 Q340 750 380 780 M300 790 Q300 740 270 720 M300 790 Q350 795 370 840 M300 790 Q250 810 240 860"
      stroke="#3f8a4a" stroke-width="14" fill="none" stroke-linecap="round"/>
<path d="M280 580 L280 960 M110 770 L450 770" stroke="#fff" stroke-width="10"/>
<circle cx="820" cy="700" r="70" fill="#fff" stroke="#3a2a22" stroke-width="10"/>
<path d="M820 700 L{820 + 44 * math.sin(math.radians(reloj)):.1f} {700 - 44 * math.cos(math.radians(reloj)):.1f}" stroke="#3a2a22" stroke-width="6" stroke-linecap="round"/>
<path d="M820 700 L{820 + 30 * math.sin(math.radians(reloj / 12 + 100)):.1f} {700 - 30 * math.cos(math.radians(reloj / 12 + 100)):.1f}" stroke="#3a2a22" stroke-width="9" stroke-linecap="round"/>
<path d="M960 1480 L960 900" stroke="#3a3a3a" stroke-width="10"/><path d="M900 910 L1020 910 L990 820 L930 820Z" fill="#f1e2c0"/>
<ellipse cx="960" cy="980" rx="200" ry="180" fill="url(#luzLampara)"/>
<path d="M70 1480 L90 1360 L170 1360 L190 1480Z" fill="#c46a3c"/>
<path d="M130 1360 Q80 1250 40 1220 M130 1360 Q130 1220 150 1160 M130 1360 Q190 1260 230 1240 M130 1360 Q100 1280 110 1210" stroke="#4f9a5a" stroke-width="18" fill="none" stroke-linecap="round"/>
<rect x="190" y="1040" width="700" height="300" rx="50" fill="url(#sofa)"/>
<rect x="250" y="1290" width="580" height="120" rx="30" fill="#d8693a"/>
<rect x="160" y="1200" width="110" height="250" rx="40" fill="#c9602f"/><rect x="810" y="1200" width="110" height="250" rx="40" fill="#c9602f"/>
<rect x="200" y="1440" width="22" height="40" fill="#5a3a26"/><rect x="858" y="1440" width="22" height="40" fill="#5a3a26"/>
{luz}{personaje}
<rect x="230" y="1400" width="620" height="30" rx="10" fill="#7a5236"/>
<rect x="250" y="1430" width="580" height="240" rx="8" fill="#8f6242"/>
<path d="M270 1470 L810 1470 M270 1530 L810 1530" stroke="#7a5236" stroke-width="4"/>
<path d="M660 1360 L700 1360 L696 1400 L664 1400Z" fill="#f4efe6"/><path d="M700 1370 Q716 1378 700 1392" stroke="#f4efe6" stroke-width="6" fill="none"/>
<rect x="330" y="1384" width="90" height="18" rx="8" fill="#2a2a2e"/>
<ellipse cx="540" cy="1690" rx="300" ry="26" fill="#000" opacity=".18"/>
</g>'''


def andar(t, f=1.7, amplitud=1.0):
    fase = 2 * math.pi * f * t
    s = math.sin(fase)
    return {
        "muslo_i": 18 * s * amplitud, "rodilla_i": -24 * max(0, -math.sin(fase - 0.9)) * amplitud,
        "muslo_d": -18 * s * amplitud, "rodilla_d": -24 * max(0, math.sin(fase - 0.9)) * amplitud,
        "brazo_i": 8 - 16 * s * amplitud, "codo_i": -14, "brazo_d": -8 + 16 * s * amplitud, "codo_d": 14,
        "inclina": 2.5 * s * amplitud,  # los hombros giran al contrario que las caderas
        "bote": -8 * abs(math.cos(fase)) * amplitud,
        "pelo_dy": 3 * abs(math.cos(fase)) * amplitud, "pelo_dx": -2 * s * amplitud,
    }


def postura_andando(a, **extra):
    p = dict(C.POSTURA_PIE, **{k: v for k, v in a.items() if k not in ("bote", "pelo_dx", "pelo_dy")})
    p.update(extra)
    return p


def escena_aeropuerto(t, dur, cara):
    # Camina hacia la cámara tirando de la maleta; corte al avión que despega.
    corte = dur * 0.5
    if t < corte:
        f = t / corte
        esc = 0.7 + 0.36 * suave(f)
        a = andar(t, 1.8)
        p = postura_andando(a, x=600 - 50 * f, y=1180 + 230 * suave(f) + a["bote"], esc=esc, brazo_d=-4, codo_d=-30, suelo=420)
        cara = dict(cara, pelo_dx=a["pelo_dx"], pelo_dy=a["pelo_dy"])
        vaiven = 7 * math.sin(2 * math.pi * 1.8 * t - 0.8)  # la maleta se balancea con retraso

        def objetos(lado, x, y):
            if lado > 0:
                return maleta(x + 10, y - 6, 0.95, vaiven)
        tablero = "".join(
            f'<text x="190" y="{620 + k * 62}" font-family="Montserrat" font-weight="700" font-size="40" fill="{c}">{txt}</text>'
            for k, (txt, c) in enumerate([("SALIDAS", "#ffffff"), ("AMSTERDAM   10:45", "#ffd24a" if int(t * 4) % 2 else "#ffe9a8"),
                                          ("PARÍS          11:10", "#c9d3da"), ("LONDRES       11:35", "#c9d3da")]))
        return f'''<rect width="1080" height="1920" fill="url(#terminal)"/>
<rect x="0" y="880" width="1080" height="320" fill="url(#cieloV)"/>
{"".join(f'<rect x="{k}" y="880" width="14" height="320" fill="#9aa4ad"/>' for k in range(0, 1081, 216))}
{avion(780 + 40 * f, 1080, 0.7)}
<rect x="0" y="1200" width="1080" height="720" fill="#d5dadf"/>
{"".join(f'<path d="M{540 + (k - 5) * 60} 1200 L{540 + (k - 5) * 260} 1920" stroke="#c3c9cf" stroke-width="3"/>' for k in range(11))}
<rect x="150" y="530" width="780" height="300" rx="16" fill="#1d2a31"/>
{tablero}
{C.dibujar(p, dict(cara), objetos)}'''
    f = (t - corte) / (dur - corte)
    x = -300 + 1700 * f
    y = 1450 - 650 * f
    nubes = "".join(nube((k * 420 - f * 500) % 1500 - 200, 700 + k * 260, 1.0 + 0.3 * (k % 2)) for k in range(4))
    rayas = "".join(f'<path d="M{x - 260 - k * 60:.0f} {y + 40 + k * 22:.0f} l-180 {50 + k * 6}" stroke="#fff" stroke-width="5" opacity=".5"/>' for k in range(3))
    return f'''<rect width="1080" height="1920" fill="url(#cieloV)"/>
{nubes}{rayas}{avion(x, y, 1.4, -18)}
<text x="540" y="1640" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="76" fill="#fff" opacity="{entre(f, .05, .25):.2f}">Valencia → Holanda</text>'''


def ciclista(x, y, esc, t, color_chaq, color_pelo, voltea=1, fase=0.0, color_bici="#1f2226"):
    """Persona en fatbike, pedaleando y con casco (para el fondo)."""
    giro = (t * 300 + fase * 100) % 360
    pedal = math.radians(t * 300 + fase * 100)
    piernas = ""
    for k, (desfase, col) in enumerate(((math.pi, "#1c1e23"), (0, "#2b2e35"))):
        px, py = -20 + 40 * math.cos(pedal + desfase), -95 + 40 * math.sin(pedal + desfase)
        m, r = C.ik(-60, -268, px, py - 10, 120, 118, doblar=-1)
        kx, ky = C.punta(-60, -268, m, 120)
        piernas += (C.miembro(-60, -268, m, 120, 46, 40, col) + C.miembro(kx, ky, r, 118, 40, 34, col)
                    + C.zapato(px, py + 4, 0, 1).replace("url(#zapa)", "#f0f0f0"))
    return f'''<g transform="translate({x:.1f} {y:.1f}) scale({esc * voltea:.3f} {esc:.3f})">
{fatbike(0, 0, 1, giro, color_bici)}
{piernas}
{C.miembro(-62, -272, 200, 190, 74, 66, color_chaq)}
{C.miembro(4, -440, -46, 140, 30, 26, color_chaq)}
<circle cx="40" cy="-520" r="48" fill="#e9b99a"/>
<path d="M-12 -530 Q-6 -590 48 -584 Q96 -578 94 -528Z" fill="#23272c"/>
<path d="M-6 -548 Q40 -600 92 -540" stroke="{P.TURQ}" stroke-width="7" fill="none"/>
<ellipse cx="0" cy="-505" rx="10" ry="14" fill="{color_pelo}"/>
<circle cx="66" cy="-516" r="5" fill="#2a1a10"/><path d="M84 -506 l10 8 l-10 2" fill="#d9a585"/>
<path d="M56 -488 q10 6 20 0" stroke="#a0604e" stroke-width="3" fill="none"/>
</g>'''


def escena_holanda(t, dur, cara):
    # Va al trabajo andando por el canal; fatbikes de tamaño real pasan delante y detrás.
    llega = entre(t, 0, 1.8)
    a = andar(t, 1.8, 1 - llega)
    p = postura_andando(a, x=-80 + 520 * llega, y=1260 + a["bote"], esc=1.0, suelo=420)
    cara = dict(cara, pelo_dx=a["pelo_dx"], pelo_dy=a["pelo_dy"])
    mira = entre(t, 1.9, 2.4)
    cara["cejas"] = cara["cejas"] + 14 * mira
    cara["gx"] = cara["gx"] + 9 * mira * math.sin(t * 2.2)
    p["cabeza"] = 7 * mira * math.sin(t * 2.2)
    if mira > 0:
        señala = rebote(entre(t, 2.0, 2.45))
        p.update(brazo_d=-8 + (-70) * señala, codo_d=14 + (-38) * señala)
    fondo_bicis, frente_bicis = "", ""
    for k, (v, carril, chaq, pelo, vol, inicio) in enumerate([
            (560, "detras", "#c0392b", "#2b1d16", 1, 0.2), (600, "delante", "#2e86c1", "#c49a5a", -1, 1.2),
            (520, "detras", "#7d3c98", "#1b1b1b", -1, 2.0), (640, "delante", "#27ae60", "#6b4a2e", 1, 2.8),
            (560, "detras", "#e67e22", "#3b2a20", 1, 3.4)]):
        if t < inicio:
            continue
        d = (t - inicio) * v
        x = -500 + d if vol > 0 else 1580 - d
        if not -600 < x < 1700:
            continue
        if carril == "detras":
            fondo_bicis += ciclista(x, 1380, 1.0, t, chaq, pelo, vol, k)
        else:
            frente_bicis += ciclista(x, 1880, 1.45, t, chaq, pelo, vol, k)
    return f'''<rect width="1080" height="1920" fill="url(#cieloH)"/>
{nube(200 - t * 12, 560, 1.2, .8)}{nube(820 - t * 8, 680, 1.0, .7)}
{casas_canal(t * 10, 1000, 1.0, 3)}
<rect x="0" y="1000" width="1080" height="130" fill="url(#agua)"/>
{"".join(f'<path d="M{(k * 140 - t * 30) % 1200 - 100} {1030 + (k % 3) * 34} l70 0" stroke="#9cc3d3" stroke-width="5" opacity=".6"/>' for k in range(10))}
<rect x="0" y="1130" width="1080" height="34" fill="#8f8f8f"/>
<rect x="0" y="1164" width="1080" height="756" fill="#b9b2a6"/>
<rect x="0" y="1250" width="1080" height="180" fill="#a8473b"/>
<path d="M0 1340 L1080 1340" stroke="#fff" stroke-width="5" stroke-dasharray="40 30"/>
{fondo_bicis}
{C.dibujar(p, cara)}
<rect x="0" y="1760" width="1080" height="160" fill="#a8473b"/>
{frente_bicis}'''


def chip(x, y, texto, color, escala=1.0):
    ancho = 26 * len(texto) + 40
    return (f'<g transform="translate({x:.0f} {y:.0f}) scale({escala:.3f})"><rect x="{-ancho / 2}" y="-34" width="{ancho}" height="68" rx="34" fill="{color}"/>'
            f'<text x="0" y="13" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="40" fill="#fff">{texto}</text></g>')


def escena_comparar(t, dur, cara):
    # «Vi de todo»: la legal, tranquila; la trucada, con rayas de velocidad y una X.
    e1 = rebote(entre(t, 0.1, 0.6))
    e2 = rebote(entre(t, 0.9 * dur / 2, 0.9 * dur / 2 + 0.5))
    tiembla = 6 * math.sin(t * 40) * entre(t, 0.9 * dur / 2, dur)
    giro = t * 300
    legal = f'''<g transform="translate({-700 + 1240 * e1:.0f} 0)">
{fatbike(0, 980, 1.0, giro)}
{chip(-160, 610, "250 W", "#2a8f6a", e1)}{chip(150, 610, "25 km/h", "#2a8f6a", e1)}
<circle cx="230" cy="470" r="62" fill="#2fb47e"/><path d="M200 470 L222 494 L262 444" stroke="#fff" stroke-width="16" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<text x="-260" y="490" font-family="Montserrat" font-weight="800" font-size="70" fill="#fff">Legal</text></g>'''
    rayas = "".join(f'<path d="M{-330 - k * 30} {1440 + k * 40} l-{160 + k * 40} 0" stroke="#ff8a7a" stroke-width="8" stroke-linecap="round" opacity=".8"/>' for k in range(4))
    trucada = f'''<g transform="translate({1780 - 1240 * e2 + tiembla:.0f} 0)">
{rayas}{fatbike(0, 1560, 1.0, giro * 2.2, "#3a1d1d", "#ff5a4a")}
{chip(-120, 1190, "+25 km/h", "#c0392b", e2)}
<circle cx="230" cy="1050" r="62" fill="#e74c3c"/><path d="M204 1024 L256 1076 M256 1024 L204 1076" stroke="#fff" stroke-width="16" stroke-linecap="round"/>
<text x="-300" y="1070" font-family="Montserrat" font-weight="800" font-size="70" fill="#fff">Trucada</text></g>'''
    return f'''<rect width="1080" height="1920" fill="url(#fondo)"/>
<circle cx="540" cy="1000" r="640" fill="url(#brillo)"/>
<g transform="translate(0 150)"><path d="M120 1230 L960 1230" stroke="#fff" stroke-opacity=".15" stroke-width="4" stroke-dasharray="16 14"/>
{legal}{trucada}</g>'''


def sergio_en_bici(t, cara, pedal, giro):
    """Sergio de perfil en la fatbike (mirando a la derecha), con casco, pedaleando."""
    cadera = (-62, -276)
    inclina = 22  # el tronco va hacia delante
    hombro = C.punta(cadera[0], cadera[1], 180 + inclina, 196)
    hombro = (cadera[0] + 196 * math.sin(math.radians(inclina)), cadera[1] - 196 * math.cos(math.radians(inclina)))
    agarre = (80, -336)
    bote = 2.5 * math.sin(pedal * 2)

    def pierna(desfase, color, sombra):
        px, py = -20 + 40 * math.cos(pedal + desfase), -95 + 40 * math.sin(pedal + desfase)
        m, r = C.ik(cadera[0], cadera[1] + bote, px, py - 14, 150, 146, doblar=-1)
        kx, ky = C.punta(cadera[0], cadera[1] + bote, m, 150)
        return (C.miembro(cadera[0], cadera[1] + bote, m, 150, 74, 62, color)
                + C.miembro(kx, ky, r, 146, 62, 52, color,
                            f'<rect x="-27" y="112" width="54" height="20" rx="8" fill="{sombra}"/>')
                + C.zapato(px, py + 2, 0, 1))

    def brazo(desf, color):
        sx, sy = hombro[0] + desf, hombro[1] + 14 + bote
        sup, inf = C.ik(sx, sy, agarre[0] + desf, agarre[1], 118, 112, doblar=1)
        ex, ey = C.punta(sx, sy, sup, 118)
        wx, wy = C.punta(ex, ey, inf, 112)
        return (C.miembro(sx, sy, sup, 118, 56, 50, color) + C.miembro(ex, ey, inf, 100, 50, 44, color,
                f'<rect x="-22" y="80" width="44" height="20" rx="8" fill="#17171a"/>') + C.mano_cerrada(wx, wy - 18, inf))

    torso = (f'<g transform="translate({cadera[0]} {cadera[1] + bote:.1f}) rotate({inclina})">'
             f'<path d="M-50 20 Q-60 -120 -46 -200 Q-20 -232 24 -224 Q60 -210 58 -150 Q62 -60 52 20 Q0 34 -50 20Z" fill="url(#torso)"/>'
             f'<path d="M-46 -200 Q-80 -214 -74 -168 Q-70 -140 -48 -150" fill="#141417"/>'
             f'<path d="M30 -200 Q40 -110 36 10" stroke="#b9bcc0" stroke-width="4" fill="none"/>'
             f'<path d="M-52 4 Q0 18 54 4 L54 28 Q0 40 -52 28Z" fill="#17171a"/></g>')
    cuello = (hombro[0] + 14, hombro[1] - 4 + bote)
    cabeza = (f'<g transform="translate({cuello[0]:.1f} {cuello[1]:.1f}) rotate({4 + cara["giro"] * .5:.2f}) scale(0.36) translate(-540 -1000)">'
              + P.cabeza(dict(cara, casco=True)) + '</g>')
    return (pierna(math.pi, "#a8916c", "#9a845f") + brazo(-10, "#0d0d10")
            + fatbike(0, 0, 1, giro)
            + torso + pierna(0, "url(#pantalon)", "#c9b38c") + cabeza + brazo(0, "url(#manga)"))


def escena_bici(t, dur, cara):
    # Se ha enganchado: va en fatbike por el carril bici, con casco y sonriendo.
    pedal = math.radians(t * 330)
    giro = t * 330
    bx, by, esc = 520, 1560, 1.15
    cara = dict(cara, sonrisa=1.5)
    lejos, medio, cerca = t * 40, t * 180, t * 900
    molino = f'''<g transform="translate({(900 - lejos) % 1500 - 200:.0f} 1000)">
<path d="M-50 260 L-30 0 L30 0 L50 260Z" fill="#7d4b2d"/><path d="M-40 0 L0 -50 L40 0Z" fill="#3e2a20"/>
<g transform="translate(0 -10) rotate({t * 50:.1f})">{"".join(f'<rect x="-14" y="-230" width="28" height="220" fill="#f4efe6" transform="rotate({k * 90})"/>' for k in range(4))}</g></g>'''
    postes = "".join(f'<rect x="{(k * 260 - cerca) % 1560 - 240:.0f}" y="1700" width="22" height="220" fill="#6b4a2e"/>' for k in range(7))
    rayas = "".join(f'<path d="M{bx - 380 * esc - k * 40:.0f} {by - 260 - k * 90} l-{140 + 30 * k} 0" stroke="#fff" stroke-width="6" stroke-linecap="round" opacity=".55"/>' for k in range(4))
    return f'''<rect width="1080" height="1920" fill="url(#cieloV)"/>
{nube((300 - lejos) % 1400 - 200, 700, 1.2)}{nube((900 - lejos) % 1400 - 200, 820, .9)}
<rect x="0" y="1180" width="1080" height="200" fill="#8fbf6a"/>
{molino}
<g transform="translate(0 {1240 - 1100 * 0.6:.0f})">{casas_canal(medio, 1100, 0.6, 9)}</g>
<rect x="0" y="1240" width="1080" height="680" fill="#7fb35d"/>
<rect x="0" y="1470" width="1080" height="200" fill="#a8473b"/>
{"".join(f'<path d="M{(k * 220 - cerca) % 1320 - 110:.0f} 1570 l120 0" stroke="#fff" stroke-width="6"/>' for k in range(7))}
<ellipse cx="{bx}" cy="{by + 6}" rx="320" ry="22" fill="#000" opacity=".25"/>
{rayas}
<g transform="translate({bx} {by}) scale({esc})">{sergio_en_bici(t, cara, pedal, giro)}</g>
{postes}'''


def escena_mapa(t, dur, cara):
    f = entre(t, 0.3, dur - 0.6)
    x0, y0, x1, y1 = 780, 960, 300, 1580
    cx, cy = 1060, 1380
    bx = (1 - f) ** 2 * x0 + 2 * (1 - f) * f * cx + f * f * x1
    by = (1 - f) ** 2 * y0 + 2 * (1 - f) * f * cy + f * f * y1
    camino = f'M{x0} {y0} Q{cx} {cy} {x1} {y1}'
    longitud = 1300
    llega = rebote(entre(f, .85, 1))
    return f'''<rect width="1080" height="1920" fill="url(#fondo)"/>
<circle cx="540" cy="1100" r="640" fill="url(#brillo)"/>
<path d="{camino}" stroke="#ffffff" stroke-opacity=".25" stroke-width="8" stroke-dasharray="20 20" fill="none"/>
<path d="{camino}" stroke="{P.TURQ}" stroke-width="10" fill="none" stroke-linecap="round" stroke-dasharray="{longitud * f:.0f} {longitud}"/>
{bandera(x0 - 20, y0 - 300, ["#ae1c28", "#ffffff", "#21468b"], 1.0, t)}
<text x="{x0 - 300}" y="{y0 - 120}" font-family="Montserrat" font-weight="800" font-size="54" fill="#fff">Holanda</text>
{bandera(x1 - 20, y1 - 300, ["#c60b1e", "#ffc400", "#ffc400", "#c60b1e"], 1.0 + 0.15 * llega, t)}
<text x="{x1 + 140}" y="{y1 - 160}" font-family="Montserrat" font-weight="800" font-size="{64 * (0.6 + 0.4 * llega):.0f}" fill="#fff" opacity="{entre(f, .8, .95):.2f}">España</text>
{fatbike(bx, by + 40, 0.42, t * 400, voltea=-1)}'''


def escena_final(t, dur, cara):
    entra = rebote(entre(t, 0, 0.45))
    p = dict(C.POSTURA_PIE, x=540, y=1300 + 70 * (1 - entra), esc=0.9, sombra=True, suelo=420)
    sube = rebote(entre(t, 0.25, 0.65)) * (1 - entre(t, dur - 0.6, dur - 0.2))
    antic = entre(t, 0.12, 0.25) * (1 - entre(t, 0.25, 0.35))
    if sube > 0 or antic > 0:
        saludo = math.sin((t - 0.6) * 11) if t > 0.6 else 0
        p.update(brazo_d=-150 * sube + 10 * antic - 6 * (1 - sube), codo_d=-22 * sube,
                 muneca_d=24 * saludo * sube, mano_d_tipo="abierta" if sube > .3 else "cerrada")
    cara = dict(cara, cejas=cara["cejas"] + 8 * sube)
    return f'''<rect width="1080" height="1920" fill="url(#fondo)"/>
<circle cx="540" cy="1000" r="640" fill="url(#brillo)"/>
{"".join(f'<circle cx="{540 + 420 * math.cos(t * .4 + k * 2.1):.0f}" cy="{960 + 600 * math.sin(t * .3 + k * 2.1):.0f}" r="{180 + 40 * k}" fill="none" stroke="{P.TURQ}" stroke-opacity=".14" stroke-width="3"/>' for k in range(3))}
{C.dibujar(p, cara)}'''


FUNCIONES = {"sofa": escena_sofa, "aeropuerto": escena_aeropuerto, "holanda": escena_holanda,
             "comparar": escena_comparar, "bici": escena_bici, "mapa": escena_mapa, "final": escena_final}


# --- Montaje ---------------------------------------------------------------------------

def fuente(tam):
    f = ImageFont.truetype(str(FUENTE), tam)
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def caja_texto(img, texto, op, y0, tam=50, fondo=(16, 27, 33), alfa=200, color=(255, 255, 255)):
    """Texto centrado en una caja redondeada (subtítulos y gancho). Devuelve dónde acaba."""
    if op <= 0:
        return y0
    d = ImageDraw.Draw(img, "RGBA")
    f = fuente(tam)
    palabras, lineas, actual = texto.split(), [], ""
    for w in palabras:
        prueba = (actual + " " + w).strip()
        if d.textlength(prueba, font=f) > 880:
            lineas.append(actual)
            actual = w
        else:
            actual = prueba
    lineas.append(actual)
    salto = int(tam * 1.32)
    alto = salto * len(lineas) + 40
    d.rounded_rectangle((70, y0, 1010, y0 + alto), 30, fill=fondo + (int(alfa * op),))
    for k, l in enumerate(lineas):
        w = d.textlength(l, font=f)
        d.text(((ANCHO - w) / 2, y0 + 20 + k * salto), l, font=f, fill=color + (int(255 * op),))
    return y0 + alto


# Zona segura: por debajo de la barra de arriba de Instagram/TikTok y por encima de los botones de abajo
Y_TEXTO = 300


_logo = None


def logo_final(img, op):
    global _logo
    if op <= 0:
        return
    if _logo is None:
        l = Image.open(LOGO).convert("RGBA")
        l.thumbnail((230, 230))
        from PIL import ImageDraw as _D
        mascara = Image.new("L", l.size, 0)
        _D.Draw(mascara).ellipse((6, 6, l.width - 6, l.height - 6), fill=255)
        l.putalpha(mascara)
        _logo = l
    l = _logo.copy()
    l.putalpha(Image.eval(l.getchannel("A"), lambda a: int(a * op)))
    img.paste(l, ((ANCHO - l.width) // 2, Y_TEXTO - 70), l)
    d = ImageDraw.Draw(img, "RGBA")
    f = fuente(64)
    texto = "@urbanfatbikes"
    d.text(((ANCHO - d.textlength(texto, font=f)) / 2, Y_TEXTO + 175), texto, font=f, fill=(255, 255, 255, int(255 * op)))


def caras(n, voz=None):
    x = P.audio(voz) if voz else np.zeros(int(n / FPS * P.FM) + P.FM)
    P.FPS = FPS
    m = P.movimientos(x)
    while len(m) < n:
        m.append(dict(m[-1]))
    return m


def render(destino, voz=None, musica=None, solo=None):
    duraciones = [d for _, d, _ in ESCENAS]
    total = sum(duraciones)
    n = int(total * FPS)
    m = caras(n, voz)
    inicios = np.cumsum([0] + duraciones)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}",
             "-r", str(FPS), "-i", "-"]
    entradas = 1
    if voz:
        orden += ["-i", voz]
        entradas += 1
    if musica:
        orden += ["-stream_loop", "-1", "-i", musica]
        entradas += 1
    if voz and musica:
        orden += ["-filter_complex", "[2:a]volume=0.25[m];[1:a][m]amix=inputs=2:normalize=0,"
                  f"afade=t=out:st={total - 1.5:.2f}:d=1.5[a]", "-map", "0:v", "-map", "[a]"]
    elif musica:
        orden += ["-filter_complex", f"[1:a]volume=0.5,afade=t=out:st={total - 1.5:.2f}:d=1.5[a]", "-map", "0:v", "-map", "[a]"]
    orden += ["-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
              "-movflags", "+faststart", destino]
    pr = subprocess.Popen(orden, stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        k = int(np.searchsorted(inicios, t, side="right") - 1)
        k = min(k, len(ESCENAS) - 1)
        nombre, dur, texto = ESCENAS[k]
        tl = t - inicios[k]
        # corte seco con un pequeño «golpe de cámara» al empezar cada escena (sin fundidos a negro)
        golpe = 1 + 0.05 * (1 - suave(tl / 0.3)) if k > 0 else 1.0
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}">'
               + P.defs() + C.defs_extra() + defs_escenas()
               + f'<g transform="translate(540 960) scale({golpe:.4f}) translate(-540 -960)">'
               + FUNCIONES[nombre](tl, dur, m[i]) + '</g></svg>')
        img = Image.open(BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert("RGB")
        if nombre == "final":
            logo_final(img, entre(tl, 0.2, 0.6))
            caja_texto(img, texto, 1.0, Y_TEXTO + 270, 46)
        else:
            y = Y_TEXTO
            if k == 0:  # gancho en pantalla desde el segundo 0 (escena del sofá)
                y = caja_texto(img, GANCHO, 1.0, Y_TEXTO, 60, fondo=(60, 200, 200), alfa=235, color=(16, 27, 33)) + 16
            caja_texto(img, texto, 1.0, y)
        pr.stdin.write(img.tobytes())
    pr.stdin.close()
    pr.wait()


def foto(nombre, t, destino):
    dur = dict((a, b) for a, b, _ in ESCENAS)[nombre]
    m = caras(int(dur * FPS) + 2)
    i = min(int(t * FPS), len(m) - 1)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}">'
           + P.defs() + C.defs_extra() + defs_escenas() + FUNCIONES[nombre](t, dur, m[i]) + '</svg>')
    cairosvg.svg2png(bytestring=svg.encode(), write_to=destino)


if __name__ == "__main__":
    if sys.argv[1] == "foto":
        foto(sys.argv[2], float(sys.argv[3]), f"esc-{sys.argv[2]}-{sys.argv[3]}.png")
    else:
        render(sys.argv[2], voz=(sys.argv[3] if sys.argv[3] != "-" else None),
               musica=str(RAIZ / "contenido" / "musica" / "inspira-1.m4a"))
