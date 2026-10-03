"""Sergio de cuerpo entero: esqueleto con articulaciones para animarlo en cualquier postura.

Coordenadas locales: (0, 0) es el centro de la cadera; hacia arriba es y negativa.
Los ángulos van en grados; 0 = el miembro cuelga hacia abajo; positivo = gira en
sentido horario (en pantalla).
"""

import math

import personaje as P

PANTALON_1, PANTALON_2 = "#dcc7a3", "#b49b74"
SUDA_1, SUDA_2, SUDA_B = "#34343a", "#141417", "#4a4a52"


def defs_extra():
    return f'''<defs>
<linearGradient id="pantalon" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{PANTALON_2}"/><stop offset=".45" stop-color="{PANTALON_1}"/><stop offset="1" stop-color="{PANTALON_2}"/></linearGradient>
<linearGradient id="manga" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{SUDA_2}"/><stop offset=".45" stop-color="{SUDA_1}"/><stop offset="1" stop-color="{SUDA_2}"/></linearGradient>
<linearGradient id="zapa" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#d9dcdf"/></linearGradient>
<linearGradient id="torso" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{SUDA_2}"/><stop offset=".4" stop-color="{SUDA_1}"/><stop offset="1" stop-color="{SUDA_2}"/></linearGradient>
<radialGradient id="sombraPies" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
</defs>'''


def punta(x, y, ang, largo):
    a = math.radians(ang)
    return x - largo * math.sin(a), y + largo * math.cos(a)


def capsula(x, y, ang, largo, ancho, relleno, extra=""):
    return (f'<g transform="translate({x:.2f} {y:.2f}) rotate({ang:.2f})">'
            f'<rect x="{-ancho / 2:.1f}" y="{-ancho / 2:.1f}" width="{ancho}" height="{largo + ancho:.1f}" rx="{ancho / 2:.1f}" fill="{relleno}"/>'
            f'{extra}</g>')


def miembro(x, y, ang, largo, a1, a2, relleno, extra=""):
    """Miembro que se estrecha (a1 arriba, a2 abajo), con extremos redondos."""
    r1, r2 = a1 / 2, a2 / 2
    d = (f"M{-r1:.1f} 0 A{r1:.1f} {r1:.1f} 0 0 1 {r1:.1f} 0 L{r2:.1f} {largo:.1f} "
         f"A{r2:.1f} {r2:.1f} 0 0 1 {-r2:.1f} {largo:.1f}Z")
    return f'<g transform="translate({x:.2f} {y:.2f}) rotate({ang:.2f})"><path d="{d}" fill="{relleno}"/>{extra}</g>'


def ik(x0, y0, x1, y1, l1, l2, doblar=1):
    """Ángulos (muslo, espinilla) para que el pie llegue a (x1, y1)."""
    dx, dy = x1 - x0, y1 - y0
    d = min(math.hypot(dx, dy), l1 + l2 - 0.01)
    base = math.degrees(math.atan2(-dx, dy))
    c = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a1 = math.degrees(math.acos(max(-1, min(1, c))))
    c2 = (l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2)
    a2 = 180 - math.degrees(math.acos(max(-1, min(1, c2))))
    return base + doblar * a1, base + doblar * a1 - doblar * a2


# Medidas
HOMBRO_X, HOMBRO_Y = 90, -214
BRAZO, ANTEBRAZO = 146, 132
CADERA_X = 46
MUSLO, PIERNA = 196, 186
CUELLO_Y = -262
CABEZA_ESC = 0.43


def mano_cerrada(x, y, ang):
    return (f'<g transform="translate({x:.2f} {y:.2f}) rotate({ang:.2f})">'
            f'<ellipse cx="0" cy="18" rx="23" ry="27" fill="url(#mano)"/>'
            f'<path d="M-14 28 Q0 36 14 28" stroke="{P.PIEL_S}" stroke-width="3" fill="none" opacity=".6"/></g>')


def mano_abierta(x, y, ang):
    return f'<g transform="translate({x:.2f} {y:.2f}) rotate({ang + 180:.2f}) scale(.42)">{P.mano(-1)}</g>'


def zapato(x, y, giro=0, perfil=0):
    """Zapatilla blanca. perfil: -1/1 mirando a izquierda/derecha, 0 de frente."""
    if perfil:
        s = perfil
        return (f'<g transform="translate({x:.2f} {y:.2f}) rotate({giro:.2f}) scale({s} 1)">'
                f'<path d="M-30 -18 Q-30 -32 -10 -32 L20 -26 Q60 -20 62 2 L62 12 L-34 12Z" fill="url(#zapa)"/>'
                f'<rect x="-36" y="4" width="100" height="18" rx="7" fill="#eef0f2"/></g>')
    return (f'<g transform="translate({x:.2f} {y:.2f}) rotate({giro:.2f})">'
            f'<path d="M-40 8 Q-42 -24 0 -28 Q42 -24 40 8Z" fill="url(#zapa)"/>'
            f'<rect x="-44" y="2" width="88" height="22" rx="9" fill="#eef0f2"/>'
            f'<path d="M-44 16 L44 16" stroke="#c9cdd2" stroke-width="3"/>'
            f'<path d="M-12 -16 L12 -16 M-15 -7 L15 -7" stroke="#c7cbd0" stroke-width="3"/></g>')


def torso(inclina, respira):
    """Sudadera negra ajustada: capucha con forro, cremallera con dientes, costuras,
    bolsillos laterales con vivo, puños y bajo de canalé."""
    e = 1 + 0.015 * respira
    cy = CUELLO_Y
    dientes = "".join(f'<rect x="-3.5" y="{y_}" width="7" height="3" fill="#8d9196"/>' for y_ in range(cy + 34, 18, 7))
    canale = "".join(f'<path d="M{x_} 26 L{x_} 50" stroke="#26262b" stroke-width="2"/>' for x_ in range(-92, 93, 8))
    return f'''<g transform="rotate({inclina:.2f}) scale({e:.4f} 1)">
<!-- capucha (por detrás del cuello) con su forro -->
<path d="M-70 {cy + 30} Q-68 {cy - 38} 0 {cy - 34} Q68 {cy - 38} 70 {cy + 30} L-70 {cy + 30}Z" fill="{SUDA_2}"/>
<path d="M-56 {cy + 22} Q-52 {cy - 22} 0 {cy - 20} Q52 {cy - 22} 56 {cy + 22} L-56 {cy + 22}Z" fill="#2b2b31"/>
<rect x="-27" y="{cy - 34}" width="54" height="54" rx="14" fill="url(#cuello)"/>
<path d="M-28 {cy + 12} Q0 {cy + 32} 28 {cy + 12} L24 {cy + 30} L-24 {cy + 30}Z" fill="#f4f4f2"/>
<!-- cuerpo ajustado -->
<path d="M-96 -176 Q-104 {cy + 18} -60 {cy + 14} Q-28 {cy + 28} 0 {cy + 28} Q28 {cy + 28} 60 {cy + 14} Q104 {cy + 18} 96 -176
         Q90 -90 94 26 Q0 36 -94 26 Q-90 -90 -96 -176Z" fill="url(#torso)"/>
<!-- brillo suave del tejido -->
<path d="M-70 -200 Q-60 -100 -66 10" stroke="#55555e" stroke-width="10" fill="none" opacity=".25" stroke-linecap="round"/>
<path d="M58 -190 Q50 -110 56 0" stroke="#55555e" stroke-width="6" fill="none" opacity=".18" stroke-linecap="round"/>
<!-- borde de la capucha delante -->
<path d="M-56 {cy + 16} Q0 {cy + 58} 56 {cy + 16}" stroke="#3c3c44" stroke-width="10" fill="none"/>
<path d="M-56 {cy + 16} Q0 {cy + 58} 56 {cy + 16}" stroke="#5a5a64" stroke-width="2" fill="none" stroke-dasharray="5 4"/>
<!-- cordones con puntera metálica -->
<path d="M-20 {cy + 34} Q-28 {cy + 80} -17 {cy + 108}" stroke="#e4e4e4" stroke-width="4" fill="none" stroke-linecap="round"/>
<path d="M20 {cy + 34} Q27 {cy + 72} 16 {cy + 100}" stroke="#e4e4e4" stroke-width="4" fill="none" stroke-linecap="round"/>
<rect x="-20" y="{cy + 106}" width="6" height="12" rx="2" fill="#a9adb2"/><rect x="13" y="{cy + 98}" width="6" height="12" rx="2" fill="#a9adb2"/>
<!-- costuras de los hombros (pespunte) -->
<path d="M-60 {cy + 16} Q-80 {cy + 30} -94 -168 M60 {cy + 16} Q80 {cy + 30} 94 -168" stroke="#4a4a52" stroke-width="2" fill="none" stroke-dasharray="6 4"/>
<!-- cremallera: cinta, dientes y tirador -->
<rect x="-6" y="{cy + 30}" width="12" height="{-cy - 4}" fill="#1b1b1f"/>
{dientes}
<path d="M0 {cy + 64} L0 {cy + 80}" stroke="#c9ccd0" stroke-width="3"/>
<rect x="-6" y="{cy + 58}" width="12" height="10" rx="3" fill="#c9ccd0"/>
<rect x="-5" y="{cy + 78}" width="10" height="22" rx="4" fill="#d6d9dc"/>
<!-- bolsillos laterales con vivo -->
<path d="M-74 -86 L-44 -20" stroke="#0d0d10" stroke-width="7" stroke-linecap="round"/>
<path d="M-71 -88 L-41 -22" stroke="#4a4a52" stroke-width="2" stroke-linecap="round"/>
<path d="M74 -86 L44 -20" stroke="#0d0d10" stroke-width="7" stroke-linecap="round"/>
<path d="M71 -88 L41 -22" stroke="#4a4a52" stroke-width="2" stroke-linecap="round"/>
<!-- pliegues al estar ajustada -->
<path d="M-86 -60 Q-70 -50 -58 -62 M86 -60 Q70 -50 58 -62 M-40 -150 Q-30 -138 -18 -146 M40 -150 Q30 -138 18 -146" stroke="#3a3a42" stroke-width="3" fill="none" opacity=".9"/>
<!-- bajo de canalé -->
<path d="M-94 24 Q0 36 94 24 L94 50 Q0 60 -94 50Z" fill="#17171a"/>
<g clip-path="url(#bajoC)">{canale}</g>
<clipPath id="bajoC"><path d="M-94 24 Q0 36 94 24 L94 50 Q0 60 -94 50Z"/></clipPath>
</g>'''


def brazo(lado, p, inclina):
    """Brazo completo (manga, antebrazo y mano). lado -1 = izquierda de la pantalla."""
    a = math.radians(inclina)
    sx = lado * HOMBRO_X * math.cos(a) - HOMBRO_Y * math.sin(a)
    sy = lado * HOMBRO_X * math.sin(a) + HOMBRO_Y * math.cos(a)
    sup = p[f"brazo_{'i' if lado < 0 else 'd'}"] + inclina
    inf = sup + p[f"codo_{'i' if lado < 0 else 'd'}"]
    ex, ey = punta(sx, sy, sup, BRAZO)
    wx, wy = punta(ex, ey, inf, ANTEBRAZO)
    pliegues = (f'<path d="M-16 {BRAZO - 18} Q0 {BRAZO - 6} 16 {BRAZO - 20}" stroke="#3a3a42" stroke-width="3" fill="none"/>'
                f'<path d="M-10 12 L-12 {BRAZO - 30}" stroke="#55555e" stroke-width="6" opacity=".22" stroke-linecap="round"/>')
    svg = miembro(sx, sy, sup, BRAZO, 58, 50, "url(#manga)", pliegues)
    canale = "".join(f'<path d="M{x_} {ANTEBRAZO - 36} L{x_} {ANTEBRAZO - 16}" stroke="#2a2a30" stroke-width="2"/>' for x_ in range(-18, 19, 6))
    svg += miembro(ex, ey, inf, ANTEBRAZO - 18, 50, 44, "url(#manga)",
                   f'<path d="M-12 30 Q2 40 14 26 M-10 64 Q2 72 12 60" stroke="#3a3a42" stroke-width="3" fill="none"/>'
                   f'<rect x="-22" y="{ANTEBRAZO - 38}" width="44" height="24" rx="8" fill="#17171a"/>' + canale)
    tipo = p.get(f"mano_{'i' if lado < 0 else 'd'}_tipo", "cerrada")
    if tipo == "bolsillo":
        pass
    elif tipo == "abierta":
        svg += mano_abierta(wx, wy, inf + p.get(f"muneca_{'i' if lado < 0 else 'd'}", 0))
    else:
        svg += mano_cerrada(wx, wy - 4, inf)
    return svg, (wx, wy)


def pierna(lado, p):
    hx = lado * CADERA_X
    sup = p[f"muslo_{'i' if lado < 0 else 'd'}"]
    inf = sup + p[f"rodilla_{'i' if lado < 0 else 'd'}"]
    largo_muslo = MUSLO * p.get("escorzo", 1.0)
    kx, ky = punta(hx, 10, sup, largo_muslo)
    ax, ay = punta(kx, ky, inf, PIERNA)
    arrugas = f'<path d="M-24 {PIERNA * .35:.0f} Q0 {PIERNA * .42:.0f} 22 {PIERNA * .3:.0f} M-20 {PIERNA * .62:.0f} Q2 {PIERNA * .7:.0f} 20 {PIERNA * .58:.0f}" stroke="#a88f68" stroke-width="3" fill="none"/>'
    svg = miembro(hx, 10, sup, largo_muslo, 88, 72, "url(#pantalon)",
                  f'<path d="M-30 {largo_muslo * .5:.0f} Q0 {largo_muslo * .6:.0f} 28 {largo_muslo * .45:.0f}" stroke="#a88f68" stroke-width="3" fill="none"/>')
    svg += miembro(kx, ky, inf, PIERNA - 10, 72, 60, "url(#pantalon)", arrugas
                   + f'<rect x="-29" y="{PIERNA - 34}" width="58" height="22" rx="9" fill="#c9b38c"/>')
    svg += zapato(ax, ay + 16, 0, p.get("perfil", 0))
    return svg, (ax, ay)


def dibujar(p, cara, extra_mano=None):
    """Devuelve el SVG del personaje. p: postura; cara: parámetros de la cara (boca, ojos...).

    p["x"], p["y"]: posición de la cadera en la escena; p["esc"]: tamaño.
    extra_mano(lado, x, y) -> SVG de lo que lleva en la mano (móvil, maleta...).
    """
    inclina = p.get("inclina", 0)
    piernas = ""
    for lado in (-1, 1):
        s, _ = pierna(lado, p)
        piernas += s
    brazos, manos = {}, {}
    for lado in (-1, 1):
        brazos[lado], manos[lado] = brazo(lado, p, inclina)
    nx = -CUELLO_Y * math.sin(math.radians(inclina))
    ny = CUELLO_Y * math.cos(math.radians(inclina))
    cabeza = (f'<g transform="translate({nx + cara["hx"] * .4:.2f} {ny + 6 + cara["hy"] * .4:.2f}) rotate({cara["giro"] + p.get("cabeza", 0):.2f}) '
              f'scale({CABEZA_ESC}) translate(-540 -1000)">' + P.cabeza(cara) + '</g>')
    objetos = ""
    if extra_mano:
        for lado in (-1, 1):
            objetos += extra_mano(lado, *manos[lado]) or ""
    frente = [l for l in (-1, 1) if l in p.get("brazos_delante", (-1, 1))]
    detras = [l for l in (-1, 1) if l not in frente]
    sombra = f'<ellipse cx="0" cy="{p.get("suelo", 420)}" rx="150" ry="22" fill="url(#sombraPies)"/>' if p.get("sombra", True) else ""
    return (f'<g transform="translate({p["x"]:.2f} {p["y"]:.2f}) scale({p.get("esc", 1) * p.get("voltea", 1):.3f} {p.get("esc", 1):.3f})">'
            + sombra + piernas
            + "".join(brazos[l] for l in detras)
            + torso(inclina, cara.get("respira", 0)) + cabeza
            + "".join(brazos[l] for l in frente) + objetos + '</g>')


# De pie, relajado: apoyado en una pierna, la otra suelta y los brazos caídos sin forzar
POSTURA_PIE = {
    "brazo_i": 9, "codo_i": -10, "brazo_d": -5, "codo_d": 14,
    "muslo_i": 7, "rodilla_i": -9, "muslo_d": -1, "rodilla_d": 1, "inclina": 1.5, "cabeza": -2,
}


def mezcla(a, b, f):
    """Postura intermedia entre a y b (f de 0 a 1)."""
    r = dict(a)
    for k, v in b.items():
        if isinstance(v, (int, float)) and isinstance(a.get(k), (int, float)):
            r[k] = a[k] + (v - a[k]) * f
        else:
            r[k] = v if f >= 0.5 else a.get(k, v)
    return r
