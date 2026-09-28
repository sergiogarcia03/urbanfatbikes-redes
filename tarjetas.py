"""Genera las tarjetas de tarjetas.yaml con el diseño de urbanfatbikes.

Cada tarjeta tiene una o varias diapositivas (varias = carrusel para deslizar).
Se guardan como contenido/tarjeta-<nombre>-<número>.jpg (1080 × 1350, formato 4:5)
y se usan en calendario.yaml como cualquier otra foto.
No usa inteligencia artificial: es un diseño fijo que rellena el programa.

Uso:
  python tarjetas.py
"""

from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).parent
DEFINICIONES = RAIZ / "tarjetas.yaml"
CONTENIDO = RAIZ / "contenido"
FUENTE = RAIZ / "fuentes" / "Montserrat.ttf"
LOGO = CONTENIDO / "logo-urbanfatbikes.png"
# Círculo del logo dentro de su imagen (centro x, centro y, radio), en píxeles.
LOGO_CIRCULO = (527, 571, 462)

ANCHO, ALTO = 1080, 1350
MARGEN = 90
PIE = ALTO - 150  # donde empieza el pie con el logo

# Colores sacados del logo
FONDO_ARRIBA = (42, 56, 64)
FONDO_ABAJO = (18, 25, 30)
GRIS_AZULADO = (112, 140, 146)
TURQUESA = (50, 198, 202)
BLANCO = (255, 255, 255)
GRIS = (191, 202, 204)

# Altura (en el lado de la tarjeta) de los círculos decorativos, que siguen
# de una diapositiva a la siguiente al deslizar.
ALTURAS_CIRCULO = [380, 980, 520, 1060, 300, 900, 640, 1000, 420, 820]


def fuente(peso, tamano):
    f = ImageFont.truetype(str(FUENTE), tamano)
    f.set_variation_by_name(peso)
    return f


# --- Texto ------------------------------------------------------------------


def palabras(texto):
    """Separa el texto en palabras; las que van entre *asteriscos* se resaltan."""
    resultado = []
    resaltar = False
    for palabra in str(texto).split():
        empieza = palabra.startswith("*")
        palabra = palabra.lstrip("*")
        termina = palabra.endswith("*")
        palabra = palabra.rstrip("*")
        resultado.append((palabra, resaltar or empieza))
        resaltar = (resaltar or empieza) and not termina
    return resultado


def partir(texto, letra, ancho):
    """Parte un texto en líneas (listas de palabras) que quepan en el ancho."""
    lineas = []
    for parrafo in str(texto).split("\n"):
        linea = []
        for palabra in palabras(parrafo):
            prueba = " ".join(p for p, _ in linea + [palabra])
            if letra.getlength(prueba) <= ancho or not linea:
                linea.append(palabra)
            else:
                lineas.append(linea)
                linea = [palabra]
        lineas.append(linea)
    return lineas


def escribir(d, x, y, texto, letra, color, ancho, interlineado=1.15, centrado=False):
    """Escribe un texto con saltos de línea automáticos. Devuelve la y final."""
    alto_linea = round(letra.size * interlineado)
    for linea in partir(texto, letra, ancho):
        total = letra.getlength(" ".join(p for p, _ in linea))
        cx = x + (ancho - total) / 2 if centrado else x
        for palabra, resaltada in linea:
            d.text((cx, y), palabra, font=letra, fill=TURQUESA if resaltada else color)
            cx += letra.getlength(palabra + " ")
        y += alto_linea
    return y


# --- Imágenes ---------------------------------------------------------------


def logo_redondo(diametro):
    """Recorta el círculo del logo (sin el fondo gris cuadrado)."""
    x, y, r = LOGO_CIRCULO
    with Image.open(LOGO) as imagen:
        recorte = imagen.convert("RGB").crop((x - r, y - r, x + r, y + r))
    recorte = recorte.resize((diametro, diametro), Image.LANCZOS)
    mascara = Image.new("L", (diametro * 4, diametro * 4), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, diametro * 4 - 1, diametro * 4 - 1), fill=255)
    return recorte, mascara.resize((diametro, diametro), Image.LANCZOS)


def producto(nombre, ancho_max, alto_max):
    """Carga una foto de producto sin fondo (PNG/WEBP transparente) y la ajusta."""
    with Image.open(CONTENIDO / nombre) as imagen:
        foto = imagen.convert("RGBA")
    foto = foto.crop(foto.getchannel("A").getbbox())
    escala = min(ancho_max / foto.width, alto_max / foto.height)
    return foto.resize((round(foto.width * escala), round(foto.height * escala)), Image.LANCZOS)


def pegar_producto(lienzo, foto, x, y):
    """Pega la foto de producto con una sombra suave debajo."""
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse(
        (x + foto.width * 0.1, y + foto.height * 0.9, x + foto.width * 0.9, y + foto.height * 1.03),
        fill=(0, 0, 0, 170),
    )
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(25)))
    lienzo.alpha_composite(foto, (x, y))


def fondo(indice, total, alto=ALTO):
    """Degradado oscuro con círculos que continúan en la diapositiva siguiente."""
    lienzo = Image.new("RGBA", (ANCHO, alto))
    d = ImageDraw.Draw(lienzo)
    for y in range(alto):
        t = y / alto
        color = tuple(round(a + (b - a) * t) for a, b in zip(FONDO_ARRIBA, FONDO_ABAJO))
        d.line((0, y, ANCHO, y), fill=color)

    capa = Image.new("RGBA", (ANCHO, alto), (0, 0, 0, 0))
    desplazar = (alto - ALTO) // 2
    c = ImageDraw.Draw(capa)
    radio = 330
    centros = []
    if indice > 0:  # el círculo que venía de la diapositiva anterior
        centros.append((0, desplazar + ALTURAS_CIRCULO[(indice - 1) % len(ALTURAS_CIRCULO)]))
    if indice < total - 1 or total == 1:
        centros.append((ANCHO, desplazar + ALTURAS_CIRCULO[indice % len(ALTURAS_CIRCULO)]))
    for cx, cy in centros:
        c.ellipse((cx - radio, cy - radio, cx + radio, cy + radio), fill=GRIS_AZULADO + (60,))
        c.ellipse((cx - radio - 40, cy - radio - 40, cx + radio + 40, cy + radio + 40), outline=TURQUESA + (110,), width=6)
    lienzo.alpha_composite(capa)
    return lienzo


def pie(lienzo, indice, total, con_logo=True):
    d = ImageDraw.Draw(lienzo)
    diametro = 84
    y = ALTO - MARGEN - diametro + 30
    x = MARGEN
    if con_logo:
        logo, mascara = logo_redondo(diametro)
        lienzo.paste(logo, (x, y), mascara)
        x += diametro + 22
    d.text((x, y + diametro // 2), "@urbanfatbikes", font=fuente("Bold", 32), fill=BLANCO, anchor="lm")

    if total > 1:
        # Numeración arriba a la derecha
        d.text((ANCHO - MARGEN, MARGEN - 20), f"{indice + 1}/{total}", font=fuente("SemiBold", 30), fill=GRIS, anchor="rt")
        if indice == 0:
            # Botón "Desliza" en la portada del carrusel
            letra = fuente("Bold", 34)
            texto = "Desliza  →"
            ancho = letra.getlength(texto) + 60
            x1, y1 = ANCHO - MARGEN - ancho, y + diametro // 2 - 34
            d.rounded_rectangle((x1, y1, x1 + ancho, y1 + 68), radius=34, fill=TURQUESA)
            d.text((x1 + ancho / 2, y1 + 34), texto, font=letra, fill=FONDO_ABAJO, anchor="mm")


# --- Tipos de diapositiva ---------------------------------------------------


def portada(lienzo, datos):
    """Titular grande con gancho y, si hay, la bici o el logo como protagonista."""
    d = ImageDraw.Draw(lienzo)
    ancho = ANCHO - 2 * MARGEN
    y = MARGEN + 40
    if datos.get("antetitulo"):
        d.text((MARGEN, y), datos["antetitulo"].upper(), font=fuente("Bold", 34), fill=TURQUESA)
        y += 70
    y = escribir(d, MARGEN, y, datos["titulo"], fuente("Black", datos.get("tamano", 112)), BLANCO, ancho, 1.05)
    if datos.get("subtitulo"):
        y = escribir(d, MARGEN, y + 25, datos["subtitulo"], fuente("Medium", 42), GRIS, ancho)

    hueco = PIE - 40 - (y + 30)
    if datos.get("imagen"):
        foto = producto(datos["imagen"], ANCHO - 60, hueco)
        pegar_producto(lienzo, foto, (ANCHO - foto.width) // 2, PIE - 40 - foto.height)
    elif datos.get("logo"):
        diametro = min(hueco, 480)
        logo, mascara = logo_redondo(diametro)
        lienzo.paste(logo, ((ANCHO - diametro) // 2, PIE - 40 - diametro), mascara)


def dato(lienzo, datos):
    """Una cifra gigante con su unidad y una explicación corta."""
    d = ImageDraw.Draw(lienzo)
    ancho = ANCHO - 2 * MARGEN
    y = MARGEN + 60
    if datos.get("antetitulo"):
        d.text((MARGEN, y), datos["antetitulo"].upper(), font=fuente("Bold", 34), fill=TURQUESA)
        y += 60

    numero = str(datos["numero"])
    tamano = 330
    letra = fuente("Black", tamano)
    while letra.getlength(numero) > ancho and tamano > 120:
        tamano -= 10
        letra = fuente("Black", tamano)
    caja = d.textbbox((MARGEN, y), numero, font=letra)
    d.text((MARGEN, y - (caja[1] - y)), numero, font=letra, fill=TURQUESA)
    y += caja[3] - caja[1] + 30
    if datos.get("unidad"):
        y = escribir(d, MARGEN, y, datos["unidad"], fuente("ExtraBold", 84), BLANCO, ancho, 1.05)
    d.rectangle((MARGEN, y + 30, MARGEN + 140, y + 40), fill=TURQUESA)
    escribir(d, MARGEN, y + 90, datos.get("texto", ""), fuente("Medium", 46), GRIS, ancho, 1.3)


def lista(lienzo, datos):
    """Un título y varios puntos con marcas turquesa."""
    d = ImageDraw.Draw(lienzo)
    ancho = ANCHO - 2 * MARGEN
    y = MARGEN + 60
    y = escribir(d, MARGEN, y, datos["titulo"], fuente("Black", datos.get("tamano", 88)), BLANCO, ancho, 1.05)
    d.rectangle((MARGEN, y + 25, MARGEN + 140, y + 35), fill=TURQUESA)
    y += 100
    letra = fuente("SemiBold", 50)
    for punto in datos.get("puntos") or []:
        d.rounded_rectangle((MARGEN, y + 8, MARGEN + 44, y + 52), radius=12, fill=TURQUESA)
        d.line((MARGEN + 11, y + 31, MARGEN + 20, y + 41, MARGEN + 34, y + 20), fill=FONDO_ABAJO, width=6)
        y = escribir(d, MARGEN + 76, y, punto, letra, BLANCO, ancho - 76, 1.2) + 34
    if datos.get("nota"):
        escribir(d, MARGEN, y + 20, datos["nota"], fuente("Medium", 36), GRIS, ancho, 1.3)


def cierre(lienzo, datos):
    """Última diapositiva: logo grande y llamada a seguir la cuenta."""
    d = ImageDraw.Draw(lienzo)
    ancho = ANCHO - 2 * MARGEN
    diametro = 420
    logo, mascara = logo_redondo(diametro)
    lienzo.paste(logo, ((ANCHO - diametro) // 2, 170), mascara)
    y = escribir(d, MARGEN, 170 + diametro + 80, datos["titulo"], fuente("Black", 80), BLANCO, ancho, 1.1, centrado=True)
    if datos.get("texto"):
        escribir(d, MARGEN, y + 25, datos["texto"], fuente("Medium", 44), GRIS, ancho, 1.3, centrado=True)


TIPOS = {"portada": portada, "dato": dato, "lista": lista, "cierre": cierre}


def contenido(datos):
    """Dibuja el contenido de una diapositiva sobre una capa transparente.

    Si no lleva foto ni logo, el contenido se centra en vertical.
    """
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    TIPOS[datos["tipo"]](capa, datos)
    caja = capa.getbbox()
    if caja and datos["tipo"] != "cierre" and not datos.get("imagen") and not datos.get("logo"):
        arriba = MARGEN + 20 + (PIE - 60 - MARGEN - (caja[3] - caja[1])) // 2
        centrada = Image.new("RGBA", capa.size, (0, 0, 0, 0))
        centrada.alpha_composite(capa.crop((0, caja[1], ANCHO, caja[3])), (0, max(MARGEN, arriba)))
        capa = centrada
    return capa


def generar(tarjeta):
    diapositivas = tarjeta["diapositivas"]
    archivos = []
    for indice, datos in enumerate(diapositivas):
        lienzo = fondo(indice, len(diapositivas))
        lienzo.alpha_composite(contenido(datos))
        pie(lienzo, indice, len(diapositivas), con_logo=datos["tipo"] != "cierre" and not datos.get("logo"))
        destino = CONTENIDO / f"tarjeta-{tarjeta['nombre']}-{indice + 1}.jpg"
        lienzo.convert("RGB").save(destino, "JPEG", quality=92, optimize=True)
        archivos.append(destino)
        print(f"✅ {destino.name}")
    return archivos


def main():
    datos = yaml.safe_load(DEFINICIONES.read_text(encoding="utf-8")) or {}
    generadas = set()
    for tarjeta in datos.get("tarjetas") or []:
        generadas.update(generar(tarjeta))
    # Borra las tarjetas que ya no están en tarjetas.yaml.
    for sobrante in CONTENIDO.glob("tarjeta-*.jpg"):
        if sobrante not in generadas:
            sobrante.unlink()
            print(f"🗑️  {sobrante.name}")


if __name__ == "__main__":
    main()
