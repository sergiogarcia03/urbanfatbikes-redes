"""Avatar animado de Sergio (dibujo vectorial, sin IA): se mueve al ritmo de la voz.

Cada fotograma es un SVG con el personaje en una postura (cabeza, ojos, cejas,
boca, manos, respiración) que se calcula a partir del audio.
"""

import math
import random
import subprocess
import sys
from io import BytesIO

import cairosvg
import imageio_ffmpeg
import numpy as np
from PIL import Image

ANCHO, ALTO, FPS = 1080, 1920, 60
FM = 44100

# Colores
PIEL_1, PIEL_2, PIEL_S = "#f3c9ab", "#e3aa88", "#cf8f6e"
PELO_1, PELO_2, PELO_B = "#120c09", "#241812", "#3a2a20"
OLIVA_1, OLIVA_2 = "#6a7150", "#4b5138"
CHAQ_1, CHAQ_2, CHAQ_S = "#eef1ec", "#c9cfc7", "#aab2a8"
FONDO_1, FONDO_2, TURQ = "#101b21", "#2a3840", "#3cc8c8"


def defs():
    return f'''<defs>
<linearGradient id="fondo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{FONDO_2}"/><stop offset="1" stop-color="{FONDO_1}"/></linearGradient>
<radialGradient id="brillo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{TURQ}" stop-opacity=".35"/><stop offset="1" stop-color="{TURQ}" stop-opacity="0"/></radialGradient>
<linearGradient id="piel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PIEL_1}"/><stop offset="1" stop-color="{PIEL_2}"/></linearGradient>
<linearGradient id="pielLado" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{PIEL_S}" stop-opacity=".55"/><stop offset=".22" stop-color="{PIEL_S}" stop-opacity="0"/><stop offset=".78" stop-color="{PIEL_S}" stop-opacity="0"/><stop offset="1" stop-color="{PIEL_S}" stop-opacity=".55"/></linearGradient>
<radialGradient id="mejilla" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#e98d7c" stop-opacity=".45"/><stop offset="1" stop-color="#e98d7c" stop-opacity="0"/></radialGradient>
<linearGradient id="cuello" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c58463"/><stop offset=".45" stop-color="{PIEL_2}"/><stop offset="1" stop-color="{PIEL_2}"/></linearGradient>
<linearGradient id="pelo" x1="0" y1="0" x2=".3" y2="1"><stop offset="0" stop-color="{PELO_2}"/><stop offset="1" stop-color="{PELO_1}"/></linearGradient>
<linearGradient id="degradado" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PELO_1}" stop-opacity=".95"/><stop offset=".55" stop-color="{PELO_1}" stop-opacity=".45"/><stop offset="1" stop-color="{PELO_1}" stop-opacity="0"/></linearGradient>
<radialGradient id="iris" cx=".45" cy=".4" r=".6"><stop offset="0" stop-color="#8a5a3a"/><stop offset=".7" stop-color="#4a2e1d"/><stop offset="1" stop-color="#2a1a10"/></radialGradient>
<linearGradient id="oliva" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{OLIVA_1}"/><stop offset="1" stop-color="{OLIVA_2}"/></linearGradient>
<linearGradient id="chaq" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CHAQ_1}"/><stop offset="1" stop-color="{CHAQ_2}"/></linearGradient>
<linearGradient id="chaqOsc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CHAQ_2}"/><stop offset="1" stop-color="{CHAQ_S}"/></linearGradient>
<linearGradient id="mano" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PIEL_1}"/><stop offset="1" stop-color="{PIEL_S}"/></linearGradient>
<radialGradient id="sombraSuelo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<radialGradient id="sombraFrente" cx=".5" cy="0" r=".9"><stop offset="0" stop-color="#9c5f45" stop-opacity=".45"/><stop offset="1" stop-color="#9c5f45" stop-opacity="0"/></radialGradient>
<radialGradient id="cuenca" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#b9785c" stop-opacity=".38"/><stop offset="1" stop-color="#b9785c" stop-opacity="0"/></radialGradient>
<radialGradient id="pomulo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff2e6" stop-opacity=".45"/><stop offset="1" stop-color="#fff2e6" stop-opacity="0"/></radialGradient>
<linearGradient id="labioS" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b56a5c"/><stop offset="1" stop-color="#9c5547"/></linearGradient>
<linearGradient id="labioI" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c97b6c"/><stop offset="1" stop-color="#d9907f"/></linearGradient>
<radialGradient id="iris2" cx=".5" cy=".62" r=".55"><stop offset="0" stop-color="#9a6a45"/><stop offset=".55" stop-color="#5a3824"/><stop offset="1" stop-color="#2a170c"/></radialGradient>
<linearGradient id="blancoOjo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e2d6cc"/><stop offset=".45" stop-color="#fbf8f4"/><stop offset="1" stop-color="#f3ece6"/></linearGradient>
<clipPath id="ojoI"><path d="M444 790 C456 770 498 764 518 786 C500 800 466 804 444 790Z"/></clipPath>
<clipPath id="ojoD"><path d="M562 786 C582 764 624 770 636 790 C614 804 580 800 562 786Z"/></clipPath>
</defs>'''


def fondo(t):
    circulos = ""
    for i, (x, y, r, v) in enumerate([(160, 380, 260, .07), (930, 620, 330, .05), (220, 1500, 300, .06), (900, 1650, 200, .08)]):
        dx = 30 * math.sin(t * v * 2 + i)
        dy = 40 * math.cos(t * v * 1.6 + i * 2)
        circulos += f'<circle cx="{x + dx:.1f}" cy="{y + dy:.1f}" r="{r}" fill="none" stroke="{TURQ}" stroke-opacity=".13" stroke-width="3"/>'
    return (f'<rect width="{ANCHO}" height="{ALTO}" fill="url(#fondo)"/>'
            f'<circle cx="540" cy="900" r="620" fill="url(#brillo)"/>{circulos}')


OJO_I = "M444 790 C456 770 498 764 518 786 C500 800 466 804 444 790Z"
OJO_D = "M562 786 C582 764 624 770 636 790 C614 804 580 800 562 786Z"


def ojo(cx, cy, clip, gx, gy, cierre, lado):
    """Ojo detallado: párpado con pestañas, iris con aro y brillos, línea inferior."""
    s = max(0.06, 1 - cierre)
    forma = OJO_I if lado < 0 else OJO_D
    ext = 1 if lado > 0 else -1  # hacia el lado de fuera
    ix, iy = cx + gx, cy - 2 + gy
    sombra_parpado = f'<ellipse cx="{cx}" cy="{cy - 14}" rx="46" ry="22" fill="url(#cuenca)"/>'
    pliegue = f'<path d="M{cx - 30} {cy - 20} C{cx - 14} {cy - 34} {cx + 14} {cy - 34} {cx + 32 * ext if ext > 0 else cx + 30} {cy - 20}" stroke="#b9785c" stroke-width="3" fill="none" opacity=".55" stroke-linecap="round"/>'
    blanco = f'<path d="{forma}" fill="url(#blancoOjo)"/>'
    iris = (f'<g clip-path="url(#{clip})">'
            f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="16.5" fill="url(#iris2)"/>'
            f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="16" fill="none" stroke="#1d0f07" stroke-width="2.5"/>'
            f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="7.5" fill="#0d0704"/>'
            f'<circle cx="{ix + 5:.1f}" cy="{iy - 6:.1f}" r="4.2" fill="#fff"/>'
            f'<circle cx="{ix - 5:.1f}" cy="{iy + 6:.1f}" r="2" fill="#fff" opacity=".7"/>'
            f'<path d="{forma}" fill="none" stroke="#7a4a35" stroke-width="10" opacity=".18"/></g>')
    # párpado superior grueso con un pequeño rabillo de pestañas
    if lado < 0:
        sup = f"M442 791 C456 768 498 762 520 785"
        rabillo = "M446 786 L436 780"
    else:
        sup = f"M560 785 C582 762 624 768 638 791"
        rabillo = "M634 786 L644 780"
    linea = f'<path d="{sup}" stroke="#1a0f0a" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
    inferior = f'<path d="{"M452 795 C470 803 498 801 514 790" if lado < 0 else "M566 790 C582 801 610 803 628 795"}" stroke="#a8695a" stroke-width="2.5" fill="none" opacity=".7" stroke-linecap="round"/>'
    ojera = f'<path d="{"M456 806 C474 814 498 812 512 802" if lado < 0 else "M568 802 C582 812 606 814 624 806"}" stroke="#c48a72" stroke-width="2" fill="none" opacity=".35"/>'
    return (f'<g transform="translate({cx} {cy}) scale(1.12) translate({-cx} {-cy})">' + sombra_parpado + pliegue + ojera
            + f'<g transform="translate({cx} {cy - 6}) scale(1 {s:.3f}) translate({-cx} {-(cy - 6)})">'
            + blanco + iris + inferior + linea + '</g></g>')


def ceja(cx, cy, sube, lado):
    """Ceja espesa con pelitos."""
    y = cy - sube
    k = -1 if lado < 0 else 1
    def px(dx):
        return cx + k * dx
    base = (f"M{px(-44)} {y + 10} C{px(-30)} {y - 6} {px(0)} {y - 12} {px(42)} {y - 4} "
            f"L{px(40)} {y + 6} C{px(4)} {y} {px(-24)} {y + 4} {px(-40)} {y + 18}Z")
    pelos = ""
    for i in range(9):
        f = i / 8
        x0 = -34 + 68 * f
        y0 = y + 8 - 12 * math.sin(f * 2.4)
        pelos += f'<path d="M{px(x0)} {y0 + 2:.1f} l{k * 7} -6" stroke="#3a281c" stroke-width="2.2" stroke-linecap="round" opacity=".55"/>'
    return f'<path d="{base}" fill="{PELO_1}"/>' + pelos


def boca(abre, ancho, sonrisa):
    cx, cy = 540, 930
    hw = 38 * ancho
    abre = max(0.0, min(1.0, abre))
    filtrum = (f'<path d="M532 890 L530 914 M548 890 L550 914" stroke="#c98a70" stroke-width="2.5" opacity=".45"/>')
    comisuras = (f'<path d="M{cx - hw - 6} {cy - 4} q-4 6 0 12 M{cx + hw + 6} {cy - 4} q4 6 0 12" stroke="#c07c66" stroke-width="2.5" fill="none" opacity=".6"/>')
    if abre < 0.06:
        sup = (f"M{cx - hw} {cy} C{cx - hw * .6} {cy - 10} {cx - 10} {cy - 14} {cx} {cy - 8} "
               f"C{cx + 10} {cy - 14} {cx + hw * .6} {cy - 10} {cx + hw} {cy} C{cx + 10} {cy + 4 + 3 * sonrisa} {cx - 10} {cy + 4 + 3 * sonrisa} {cx - hw} {cy}Z")
        inf = (f"M{cx - hw + 4} {cy + 2} C{cx - 14} {cy + 6} {cx + 14} {cy + 6} {cx + hw - 4} {cy + 2} "
               f"C{cx + hw * .6} {cy + 22} {cx - hw * .6} {cy + 22} {cx - hw + 4} {cy + 2}Z")
        return (filtrum + f'<path d="{inf}" fill="url(#labioI)"/><path d="{sup}" fill="url(#labioS)"/>'
                f'<path d="M{cx - hw} {cy} C{cx - 10} {cy + 5 + 3 * sonrisa} {cx + 10} {cy + 5 + 3 * sonrisa} {cx + hw} {cy}" stroke="#7a3a30" stroke-width="3" fill="none" stroke-linecap="round"/>'
                f'<ellipse cx="{cx}" cy="{cy + 12}" rx="12" ry="3.5" fill="#fff" opacity=".35"/>'
                f'<path d="M{cx - 14} {cy + 30} Q{cx} {cy + 35} {cx + 14} {cy + 30}" stroke="#c98a70" stroke-width="2.5" fill="none" opacity=".35"/>'
                + comisuras)
    alto = 8 + 48 * abre
    arriba, abajo = cy - 4, cy + alto
    interior = (f"M{cx - hw} {cy} Q{cx - hw * .5} {arriba - 4} {cx} {arriba} Q{cx + hw * .5} {arriba - 4} {cx + hw} {cy}"
                f" Q{cx + hw * .7} {abajo} {cx} {abajo} Q{cx - hw * .7} {abajo} {cx - hw} {cy}Z")
    dientes = min(12, 4 + 20 * abre)
    labio_sup = (f"M{cx - hw - 3} {cy} C{cx - hw * .6} {arriba - 14} {cx - 10} {arriba - 16} {cx} {arriba - 10} "
                 f"C{cx + 10} {arriba - 16} {cx + hw * .6} {arriba - 14} {cx + hw + 3} {cy} Q{cx} {arriba - 2} {cx - hw - 3} {cy}Z")
    labio_inf = (f"M{cx - hw - 2} {cy + 2} Q{cx} {2 * abajo - cy} {cx + hw + 2} {cy + 2} "
                 f"Q{cx} {2 * (abajo + 10) - cy} {cx - hw - 2} {cy + 2}Z")
    return (filtrum + f'<path d="{interior}" fill="#4a1615"/>'
            f'<clipPath id="bocaC"><path d="{interior}"/></clipPath>'
            f'<g clip-path="url(#bocaC)"><rect x="{cx - hw}" y="{arriba - 6}" width="{2 * hw}" height="{dientes + 6}" fill="#fbf7f2"/>'
            f'<path d="M{cx - 12} {arriba} l0 {dientes} M{cx + 12} {arriba} l0 {dientes}" stroke="#e6ddd4" stroke-width="1.5"/>'
            f'<ellipse cx="{cx}" cy="{abajo + 2}" rx="{hw * .5}" ry="{5 + 9 * abre}" fill="#b4504b"/></g>'
            f'<path d="{labio_inf}" fill="url(#labioI)"/><path d="{labio_sup}" fill="url(#labioS)"/>'
            f'<ellipse cx="{cx}" cy="{abajo + 5}" rx="10" ry="2.5" fill="#fff" opacity=".3"/>' + comisuras)


def pelo():
    """Pelo oscuro, rizado y despeinado: rizos alrededor de la cabeza y mechones hacia la frente."""
    rng = random.Random(7)
    rizos = []
    for i in range(9):
        a = math.pi * (1.04 + 0.92 * i / 8)  # de la sien izquierda a la derecha, por arriba
        rx, ry = 150, 150
        x = 540 + rx * math.cos(a) + rng.uniform(-5, 5)
        y = 650 + ry * math.sin(a) + rng.uniform(-5, 5)
        r = rng.uniform(50, 58) * (0.7 if i in (0, 8) else 1)
        rizos.append((x, y, r))
    base = ('<path d="M374 676 C360 560 410 470 540 462 C670 470 720 560 706 676 C690 640 600 600 540 604 '
            'C480 600 390 640 374 676Z" fill="url(#pelo)"/>')
    circ = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="url(#pelo)"/>' for x, y, r in rizos)
    brillos = "".join(
        f'<path d="M{x - r * .55:.1f} {y - r * .1:.1f} Q{x:.1f} {y - r * .7:.1f} {x + r * .5:.1f} {y - r * .2:.1f}" '
        f'stroke="#5e4637" stroke-width="4" fill="none" stroke-linecap="round" opacity=".55"/>'
        for x, y, r in rizos[1:8])
    mechones = ('<path d="M450 600 C470 636 466 656 446 668 C490 662 512 636 506 604Z" fill="url(#pelo)"/>'
                '<path d="M520 604 C548 636 548 660 532 676 C576 664 592 634 580 604Z" fill="url(#pelo)"/>'
                '<path d="M600 606 C624 630 630 650 622 664 C654 650 664 626 652 606Z" fill="url(#pelo)"/>')
    rizos_frente = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#pelo)"/>'
                           for x, y, r in [(452, 590, 44), (540, 576, 48), (628, 590, 44)])
    return base + circ + rizos_frente + mechones + brillos


def casco():
    """Casco de bici (negro con raya turquesa, rejillas y correa)."""
    return f'''<path d="M392 690 L436 950 Q540 1004 644 950 L688 690" stroke="#1d1f22" stroke-width="7" fill="none"/>
<path d="M500 610 C490 640 470 660 446 668 C484 664 512 640 514 612Z" fill="url(#pelo)"/>
<path d="M566 612 C580 640 600 652 620 656 C596 640 586 626 584 610Z" fill="url(#pelo)"/>
<path d="M360 700 C342 520 420 404 540 398 C660 404 738 520 720 700 C700 660 650 618 540 616 C430 618 380 660 360 700Z" fill="#23272c"/>
<path d="M376 650 C378 520 446 432 540 428 C634 432 702 520 704 650" stroke="#3a4048" stroke-width="10" fill="none" opacity=".7"/>
<path d="M540 400 C556 470 556 560 546 618" stroke="{TURQ}" stroke-width="16" fill="none"/>
<path d="M470 440 Q480 500 470 560 M610 440 Q600 500 610 560" stroke="#0f1113" stroke-width="12" fill="none" stroke-linecap="round"/>
<path d="M366 690 C390 650 450 630 540 628 C630 630 690 650 714 690" stroke="#15171a" stroke-width="14" fill="none" stroke-linecap="round"/>
<ellipse cx="470" cy="470" rx="40" ry="18" fill="#fff" opacity=".12" transform="rotate(-30 470 470)"/>'''


def cabeza(p):
    o = ojo(480, 790, "ojoI", p["gx"], p["gy"], p["parpadeo"], -1) + ojo(600, 790, "ojoD", p["gx"], p["gy"], p["parpadeo"], 1)
    c = ceja(480, 740, p["cejas"], -1) + ceja(600, 740, p["cejas"] * 0.9, 1)
    cara = ("M380 690 C380 560 452 518 540 518 C628 518 700 560 700 690 L698 800 C694 872 664 932 618 968 "
            "C594 988 568 1000 540 1000 C512 1000 486 988 462 968 C416 932 386 872 382 800Z")
    return f'''
<!-- orejas con detalle -->
<g><ellipse cx="374" cy="800" rx="28" ry="50" fill="{PIEL_2}"/>
<path d="M370 766 C350 772 350 826 372 840" stroke="{PIEL_S}" stroke-width="6" fill="none" stroke-linecap="round"/>
<path d="M378 784 C366 792 368 812 380 818" stroke="#c58463" stroke-width="4" fill="none" stroke-linecap="round"/></g>
<g><ellipse cx="706" cy="800" rx="28" ry="50" fill="{PIEL_2}"/>
<path d="M710 766 C730 772 730 826 708 840" stroke="{PIEL_S}" stroke-width="6" fill="none" stroke-linecap="round"/>
<path d="M702 784 C714 792 712 812 700 818" stroke="#c58463" stroke-width="4" fill="none" stroke-linecap="round"/></g>
<!-- cara con volumen -->
<path d="{cara}" fill="url(#piel)"/>
<path d="{cara}" fill="url(#pielLado)"/>
<path d="M392 860 C410 930 470 984 540 1000 C470 990 418 940 392 860Z" fill="{PIEL_S}" opacity=".35"/>
<path d="M688 860 C670 930 610 984 540 1000 C610 990 662 940 688 860Z" fill="{PIEL_S}" opacity=".35"/>
<ellipse cx="540" cy="600" rx="170" ry="80" fill="url(#sombraFrente)"/>
<ellipse cx="438" cy="852" rx="40" ry="22" fill="url(#pomulo)" opacity=".5"/><ellipse cx="642" cy="852" rx="40" ry="22" fill="url(#pomulo)" opacity=".5"/>
<ellipse cx="434" cy="884" rx="44" ry="26" fill="url(#mejilla)" opacity=".7"/><ellipse cx="646" cy="884" rx="44" ry="26" fill="url(#mejilla)" opacity=".7"/>
<!-- barbilla -->
<path d="M522 980 Q540 986 558 980" stroke="#c98a70" stroke-width="2.5" fill="none" opacity=".35"/>
<!-- lados cortos (degradado) -->
<path d="M378 604 Q372 690 382 760 Q388 700 400 652 Q394 622 378 604Z" fill="url(#degradado)" opacity=".55"/>
<path d="M702 604 Q708 690 698 760 Q692 700 680 652 Q686 622 702 604Z" fill="url(#degradado)" opacity=".55"/>
{casco() if p.get("casco") else f'<g transform="translate({p.get("pelo_dx", 0):.2f} {p.get("pelo_dy", 0):.2f})">' + pelo() + '</g>'}
{c}{o}
<!-- nariz con volumen -->
<path d="M528 790 C524 830 520 852 512 872" stroke="#c98a70" stroke-width="5" fill="none" opacity=".45" stroke-linecap="round"/>
<path d="M552 800 C556 830 560 850 566 866" stroke="#fff" stroke-width="5" fill="none" opacity=".18" stroke-linecap="round"/>
<ellipse cx="540" cy="872" rx="20" ry="15" fill="#e6a888" opacity=".55"/>
<ellipse cx="544" cy="864" rx="8" ry="5" fill="#fff" opacity=".4"/>
<path d="M512 876 C506 886 516 894 526 890 M568 876 C574 886 564 894 554 890" stroke="#b9785c" stroke-width="3.5" fill="none" stroke-linecap="round"/>
<ellipse cx="528" cy="888" rx="6" ry="3.2" fill="#8a4c3a" opacity=".75"/><ellipse cx="552" cy="888" rx="6" ry="3.2" fill="#8a4c3a" opacity=".75"/>
{boca(p["boca"], p["ancho"], p["sonrisa"])}'''


def mano(lado):
    """Mano abierta con la palma hacia delante, dibujada con la muñeca en (0, 0)."""
    s = -1 if lado < 0 else 1
    dedos = ""
    for dx, largo, ang in [(-31, 70, -8), (-10, 86, -2), (11, 82, 3), (31, 66, 9)]:
        dedos += (f'<g transform="translate({dx * s} -104) rotate({ang * s})">'
                  f'<path d="M-12 8 L-12 {-largo + 12} Q-12 {-largo} 0 {-largo} Q12 {-largo} 12 {-largo + 12} L12 8Z" fill="url(#mano)"/>'
                  f'<path d="M-6 {-largo + 8} Q0 {-largo + 3} 6 {-largo + 8}" stroke="#f8dccb" stroke-width="3" fill="none" opacity=".8"/>'
                  f'<path d="M-7 {-largo * .42} Q0 {-largo * .38} 7 {-largo * .42}" stroke="{PIEL_S}" stroke-width="2.5" fill="none" opacity=".7"/></g>')
    pulgar = (f'<g transform="translate({-46 * s} -40) rotate({-38 * s})">'
              f'<path d="M-13 10 L-13 -42 Q-13 -56 0 -56 Q13 -56 13 -42 L13 10Z" fill="url(#mano)"/></g>')
    palma = (f'<path d="M-46 -112 Q-50 -40 -32 0 L32 0 Q50 -40 46 -112 Q0 -122 -46 -112Z" fill="url(#mano)"/>'
             f'<path d="M-44 -106 L44 -106" stroke="{PIEL_S}" stroke-width="3" opacity=".35"/>')
    linea = (f'<path d="M-30 -66 Q0 -48 30 -72" stroke="{PIEL_S}" stroke-width="3" fill="none" opacity=".55"/>'
             f'<path d="M-26 -40 Q-4 -30 14 -46" stroke="{PIEL_S}" stroke-width="2.5" fill="none" opacity=".45"/>')
    return palma + dedos + pulgar + linea


def brazo(x, y, angulo, lado):
    """Antebrazo con manga acolchada y mano, entrando desde abajo."""
    return (f'<g transform="translate({x:.1f} {y:.1f}) rotate({angulo:.2f})">'
            f'<path d="M-70 400 L-62 30 Q0 0 62 30 L70 400Z" fill="url(#chaq)"/>'
            f'<path d="M-66 120 Q0 104 66 120 M-68 230 Q0 214 68 230 M-69 330 Q0 314 69 330" stroke="{CHAQ_S}" stroke-width="5" fill="none"/>'
            f'<rect x="-58" y="10" width="116" height="34" rx="16" fill="{CHAQ_2}"/>'
            f'<g transform="translate(0 16) scale(1.25)">{mano(lado)}</g></g>')


def cuerpo(respira):
    e = 1 + 0.012 * respira
    return f'''<g transform="translate(540 1920) scale({e:.4f} {e:.4f}) translate(-540 -1920)">
<!-- capucha detrás -->
<path d="M330 1150 Q340 1060 540 1052 Q740 1060 750 1150 Q700 1110 540 1108 Q380 1110 330 1150Z" fill="url(#chaqOsc)"/>
<!-- cuello -->
<path d="M480 960 L480 1120 Q540 1150 600 1120 L600 960Z" fill="url(#cuello)"/>
<!-- camiseta -->
<path d="M430 1110 Q540 1150 650 1110 L690 2100 L390 2100Z" fill="url(#oliva)"/>
<path d="M466 1112 Q540 1150 614 1112" stroke="{OLIVA_2}" stroke-width="12" fill="none"/>
<!-- chaqueta -->
<path d="M140 1920 Q140 1300 300 1190 Q380 1140 440 1130 Q470 1300 470 2100 L140 2100Z" fill="url(#chaq)"/>
<path d="M940 1920 Q940 1300 780 1190 Q700 1140 640 1130 Q610 1300 610 2100 L940 2100Z" fill="url(#chaq)"/>
<path d="M440 1130 Q420 1200 470 1300 L470 1920 L458 1920 L458 1310 Q404 1210 430 1128Z" fill="{CHAQ_S}" opacity=".7"/>
<path d="M640 1130 Q660 1200 610 1300 L610 1920 L622 1920 L622 1310 Q676 1210 650 1128Z" fill="{CHAQ_S}" opacity=".7"/>
<path d="M190 1400 Q330 1380 462 1400 M160 1560 Q320 1540 466 1560 M150 1720 Q320 1700 468 1720
         M618 1400 Q750 1380 890 1400 M614 1560 Q760 1540 920 1560 M612 1720 Q760 1700 930 1720" stroke="{CHAQ_S}" stroke-width="5" fill="none"/>
<path d="M300 1190 Q260 1260 250 1340 M780 1190 Q820 1260 830 1340" stroke="{CHAQ_S}" stroke-width="5" fill="none" opacity=".8"/>
<rect x="452" y="1300" width="6" height="800" fill="#9aa298"/><rect x="622" y="1300" width="6" height="800" fill="#9aa298"/>
</g>'''


def fotograma(t, p):
    cg, cx = p.get("cuerpo_giro", 0), p.get("cuerpo_x", 0)
    cuerpo_ = (f'<g transform="translate({cx:.2f} -45) rotate({cg:.3f} 540 1900)">' + cuerpo(p["respira"]) + '</g>')
    g = (f'<g transform="translate({p["hx"]:.2f} {p["hy"]:.2f}) rotate({p["giro"]:.3f} 540 1080)">' + cabeza(p) + '</g>')
    manos = ""
    for lado, x0, a0, fase in [(-1, 300, -16, 0.0), (1, 780, 16, 1.7)]:
        sube = p["mano_i"] if lado < 0 else p["mano_d"]
        if sube > 0.005:
            y = 2250 - 720 * sube
            ang = a0 * (1 - sube) + lado * (5 * math.sin(t * 2.4 + fase) + 3 * math.sin(t * 3.7 + fase)) * sube
            manos += brazo(x0 + cx - lado * 24 * sube, y, ang, lado)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}">'
            + defs() + fondo(t) + '<g transform="translate(540 1920) scale(1.16) translate(-540 -1920)">'
            + cuerpo_ + g + manos + '</g></svg>')


# --- Movimiento a partir de la voz -------------------------------------------------------

def audio(archivo, desde=0.0, hasta=None):
    orden = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-ss", str(desde)]
    if hasta:
        orden += ["-t", str(hasta - desde)]
    orden += ["-i", archivo, "-ac", "1", "-ar", str(FM), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(orden, capture_output=True, check=True).stdout, np.float32)


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def muelle(objetivo, frecuencia, amortiguacion=1.0):
    """Sigue una señal como un muelle: sin saltos, con inercia natural."""
    w = 2 * math.pi * frecuencia
    dt = 1 / FPS
    x, v = float(objetivo[0]), 0.0
    salida = np.zeros(len(objetivo))
    for i, o in enumerate(objetivo):
        for _ in range(4):  # pasos pequeños para que sea estable
            a = w * w * (o - x) - 2 * amortiguacion * w * v
            v += a * dt / 4
            x += v * dt / 4
        salida[i] = x
    return salida


def ruido(t, semilla, velocidad=1.0):
    """Movimiento suave y sin repetirse (suma de ondas lentas)."""
    r = random.Random(semilla)
    total = 0.0
    for k in range(4):
        f = velocidad * r.uniform(0.15, 0.6) * (1.6 ** k)
        total += math.sin(2 * math.pi * f * t + r.uniform(0, 6.28)) / (1.7 ** k)
    return total


def movimientos(x, semilla=3):
    n = int(len(x) / FM * FPS) + 1
    paso = FM // FPS
    energia, brillo = np.zeros(n), np.zeros(n)
    for i in range(n):
        tr = x[max(0, i * paso - paso):(i + 1) * paso + paso]
        if len(tr) < 64:
            continue
        energia[i] = np.sqrt((tr ** 2).mean())
        esp = np.abs(np.fft.rfft(tr * np.hanning(len(tr))))
        f = np.fft.rfftfreq(len(tr), 1 / FM)
        brillo[i] = (esp * f).sum() / (esp.sum() + 1e-9)
    db = 20 * np.log10(energia + 1e-6)
    alto, bajo = np.percentile(db, 95), np.percentile(db, 30)
    nivel = np.clip((db - bajo - 6) / max(alto - bajo - 6, 1), 0, 1)
    # La boca se adelanta un poco al sonido (como al hablar de verdad) y se mueve con muelle
    adelanto = int(0.04 * FPS)
    nivel_ad = np.r_[nivel[adelanto:], np.zeros(adelanto)]
    boca = np.clip(muelle(nivel_ad, 7.0, 0.9), 0, 1)
    habla = muelle(nivel > 0.12, 1.2) > 0.4
    br_med = np.median(brillo[nivel > 0.12]) if (nivel > 0.12).any() else 1500
    ancho = np.where(nivel > 0.12, np.clip(0.85 + 0.25 * (brillo - br_med) / (br_med + 1), 0.8, 1.12), 1.0)
    ancho = muelle(ancho, 4.0)
    rng = random.Random(semilla)
    # parpadeos: cierre rápido y apertura algo más lenta
    parpadeo = np.zeros(n)
    t = rng.uniform(1.0, 2.5)
    while t < n / FPS:
        k = int(t * FPS)
        cierra, abre = int(0.07 * FPS), int(0.13 * FPS)
        for j in range(cierra + abre):
            if k + j < n:
                parpadeo[k + j] = suave(j / cierra) if j < cierra else 1 - suave((j - cierra) / abre)
        t += rng.uniform(2.2, 5.0)
    # acentos (cuando la voz sube de golpe): asentir y subir cejas, suavizados
    golpe = np.zeros(n)
    for i in range(3, n):
        if nivel[i] - nivel[i - 3] > 0.35 and golpe[max(0, i - int(0.25 * FPS)):i].max() == 0:
            golpe[i] = 1
    acento = np.zeros(n)
    for i in range(n):
        acento[i] = max(golpe[i], acento[i - 1] * math.exp(-1 / (0.35 * FPS)) if i else 0)
    acento = muelle(acento, 3.0)
    # gestos de manos: al empezar una frase tras una pausa, alterna mano
    manos = {"i": np.zeros(n), "d": np.zeros(n)}
    ultimo, cual = -99, "d"
    activo = nivel > 0.12
    for i in range(1, n):
        if activo[i] and not activo[i - int(0.3 * FPS):i].any() and (i - ultimo) / FPS > 2.6:
            if rng.random() < 0.8:
                dur = rng.uniform(1.8, 2.8)
                for j in range(int(dur * FPS)):
                    k = i + j
                    if k >= n:
                        break
                    tt = j / FPS
                    v = suave(tt / 0.6) * suave((dur - tt) / 0.7)
                    manos[cual][k] = max(manos[cual][k], v)
                ultimo, cual = i, ("i" if cual == "d" else "d")
    mano_i, mano_d = muelle(manos["i"], 1.6, 0.8), muelle(manos["d"], 1.6, 0.8)
    # cabeza: movimiento libre y suave, más vivo al hablar
    vivo = muelle(habla.astype(float), 0.8)
    ts = np.arange(n) / FPS
    giro = np.array([ruido(t, 11) for t in ts]) * (1.6 + 2.2 * vivo)
    hx = np.array([ruido(t, 12, 0.8) for t in ts]) * (8 + 10 * vivo)
    hy = np.array([ruido(t, 13, 1.2) for t in ts]) * (3 + 3 * vivo) + 9 * acento
    giro, hx, hy = muelle(giro, 1.5), muelle(hx, 1.2), muelle(hy, 2.0)
    gx = muelle(np.array([5 * ruido(t, 14, 0.7) for t in ts]), 3.0)
    gy = muelle(np.array([2 * ruido(t, 15, 0.7) for t in ts]), 3.0)
    cejas = muelle(np.array([3 * ruido(t, 16, 0.5) for t in ts]) + 13 * acento, 4.0)
    posturas = []
    for i in range(n):
        t = ts[i]
        posturas.append({
            "boca": boca[i], "ancho": ancho[i], "sonrisa": 1.0,
            "parpadeo": parpadeo[i], "cejas": cejas[i], "gx": gx[i], "gy": gy[i],
            "giro": giro[i], "hx": hx[i], "hy": hy[i],
            # el cuerpo acompaña a la cabeza con retraso y menos amplitud
            "cuerpo_giro": 0.0, "cuerpo_x": 0.0,
            "respira": math.sin(t * 2 * math.pi / 3.8),
            "mano_i": mano_i[i], "mano_d": mano_d[i],
        })
    cg = muelle(giro * 0.35, 0.7)
    cx = muelle(hx * 0.4, 0.7)
    for i, p in enumerate(posturas):
        p["cuerpo_giro"], p["cuerpo_x"] = cg[i], cx[i]
    return posturas


def video(voz_wav, destino, desde=0.0, hasta=None):
    x = audio(voz_wav, desde, hasta)
    posturas = movimientos(x)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}",
             "-r", str(FPS), "-i", "-", "-ss", str(desde)]
    if hasta:
        orden += ["-t", str(hasta - desde)]
    orden += ["-i", voz_wav, "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
              "-crf", "20", "-c:a", "aac", "-b:a", "128k", destino]
    pr = subprocess.Popen(orden, stdin=subprocess.PIPE)
    for i, p in enumerate(posturas):
        png = cairosvg.svg2png(bytestring=fotograma(i / FPS, p).encode())
        pr.stdin.write(Image.open(BytesIO(png)).convert("RGB").tobytes())
    pr.stdin.close()
    pr.wait()


if __name__ == "__main__":
    if sys.argv[1] == "foto":
        p = {"boca": float(sys.argv[3]), "ancho": 1, "sonrisa": 1, "parpadeo": 0, "cejas": 0, "gx": 0, "gy": 0,
             "giro": 0, "hx": 0, "hy": 0, "respira": 0, "mano_i": float(sys.argv[4]), "mano_d": 0}
        cairosvg.svg2png(bytestring=fotograma(0, p).encode(), write_to=sys.argv[2])
    else:
        video(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))
