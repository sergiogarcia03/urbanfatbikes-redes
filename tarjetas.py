"""Genera las tarjetas de texto de tarjetas.yaml con los colores de urbanfatbikes.

Cada tarjeta se guarda como contenido/<archivo>.jpg (1080 × 1350, formato 4:5)
y se puede usar en calendario.yaml como cualquier otra foto.
No usa inteligencia artificial: es un diseño fijo que rellena el programa.

Uso:
  python tarjetas.py
"""

from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).parent
DEFINICIONES = RAIZ / "tarjetas.yaml"
CONTENIDO = RAIZ / "contenido"
FUENTE = RAIZ / "fuentes" / "Montserrat.ttf"
LOGO = CONTENIDO / "logo-urbanfatbikes.png"
# Círculo del logo dentro de su imagen (centro x, centro y, radio), en píxeles.
LOGO_CIRCULO = (527, 571, 462)

ANCHO, ALTO = 1080, 1350
MARGEN = 90

# Colores sacados del logo
FONDO = "#212B31"
TURQUESA = "#32C6CA"
BLANCO = "#FFFFFF"
GRIS = "#BFCACC"


def fuente(peso, tamano):
    f = ImageFont.truetype(str(FUENTE), tamano)
    f.set_variation_by_name(peso)
    return f


def partir(texto, letra, ancho):
    """Parte un texto en líneas que quepan en el ancho indicado."""
    lineas = []
    for parrafo in str(texto).split("\n"):
        linea = ""
        for palabra in parrafo.split():
            prueba = f"{linea} {palabra}".strip()
            if letra.getlength(prueba) <= ancho:
                linea = prueba
            else:
                if linea:
                    lineas.append(linea)
                linea = palabra
        lineas.append(linea)
    return lineas


def logo_redondo(diametro):
    """Recorta el círculo del logo (sin el fondo gris cuadrado)."""
    x, y, r = LOGO_CIRCULO
    with Image.open(LOGO) as imagen:
        recorte = imagen.convert("RGB").crop((x - r, y - r, x + r, y + r))
    recorte = recorte.resize((diametro, diametro), Image.LANCZOS)
    mascara = Image.new("L", (diametro * 4, diametro * 4), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, diametro * 4 - 1, diametro * 4 - 1), fill=255)
    return recorte, mascara.resize((diametro, diametro), Image.LANCZOS)


def dibujar(tarjeta, escala, bajar=0):
    """Dibuja la tarjeta y devuelve (imagen, alto usado por el contenido)."""
    imagen = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(imagen)
    ancho_texto = ANCHO - 2 * MARGEN
    y = MARGEN + 10 + bajar

    if tarjeta.get("logo_grande"):
        diametro = 520
        logo, mascara = logo_redondo(diametro)
        imagen.paste(logo, ((ANCHO - diametro) // 2, y), mascara)
        y += diametro + 70

    letra = fuente("ExtraBold", round(72 * escala))
    for linea in partir(tarjeta["titulo"], letra, ancho_texto):
        d.text((MARGEN, y), linea, font=letra, fill=BLANCO)
        y += round(88 * escala)
    y += 20
    d.rectangle((MARGEN, y, MARGEN + 140, y + 10), fill=TURQUESA)
    y += round(60 * escala)

    if tarjeta.get("subtitulo"):
        letra = fuente("Medium", round(40 * escala))
        for linea in partir(tarjeta["subtitulo"], letra, ancho_texto):
            d.text((MARGEN, y), linea, font=letra, fill=GRIS)
            y += round(54 * escala)
        y += round(30 * escala)

    for bloque in tarjeta.get("bloques") or []:
        letra = fuente("Bold", round(44 * escala))
        for linea in partir(bloque["titulo"], letra, ancho_texto):
            d.text((MARGEN, y), linea, font=letra, fill=TURQUESA)
            y += round(58 * escala)
        y += round(10 * escala)
        letra = fuente("Regular", round(38 * escala))
        sangria = round(40 * escala)
        for punto in bloque.get("puntos") or []:
            lineas = partir(punto, letra, ancho_texto - sangria)
            radio = round(7 * escala)
            centro = y + round(24 * escala)
            d.ellipse((MARGEN + 4, centro - radio, MARGEN + 4 + 2 * radio, centro + radio), fill=TURQUESA)
            for linea in lineas:
                d.text((MARGEN + sangria, y), linea, font=letra, fill=BLANCO)
                y += round(52 * escala)
            y += round(8 * escala)
        y += round(40 * escala)

    if tarjeta.get("nota"):
        letra = fuente("Medium", round(32 * escala))
        for linea in partir(tarjeta["nota"], letra, ancho_texto):
            d.text((MARGEN, y), linea, font=letra, fill=GRIS)
            y += round(44 * escala)

    # Pie: logo pequeño y nombre de la cuenta
    diametro = 96
    pie_y = ALTO - MARGEN + 20 - diametro
    if not tarjeta.get("logo_grande"):
        logo, mascara = logo_redondo(diametro)
        imagen.paste(logo, (MARGEN, pie_y), mascara)
        x_texto = MARGEN + diametro + 24
    else:
        x_texto = MARGEN
    d.text((x_texto, pie_y + diametro // 2), "@urbanfatbikes", font=fuente("Bold", 34), fill=BLANCO, anchor="lm")
    return imagen, y, pie_y


def generar(tarjeta):
    # Si el texto no cabe, se va reduciendo la letra hasta que quepa.
    escala = 1.0
    while True:
        imagen, fin_contenido, pie_y = dibujar(tarjeta, escala)
        if fin_contenido <= pie_y - 30 or escala < 0.6:
            break
        escala -= 0.05
    # Si sobra sitio, centra el contenido en vertical.
    sobra = pie_y - 30 - fin_contenido
    if sobra > 0:
        imagen, fin_contenido, pie_y = dibujar(tarjeta, escala, bajar=sobra // 2)
    destino = CONTENIDO / f"{tarjeta['archivo']}.jpg"
    imagen.save(destino, "JPEG", quality=92, optimize=True)
    aviso = "  ⚠️ demasiado texto, acórtalo" if fin_contenido > pie_y - 30 else ""
    print(f"✅ {destino.name}{aviso}")


def main():
    datos = yaml.safe_load(DEFINICIONES.read_text(encoding="utf-8")) or {}
    for tarjeta in datos.get("tarjetas") or []:
        generar(tarjeta)


if __name__ == "__main__":
    main()
