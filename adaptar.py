"""Adapta las fotos de contenido/ a lo que exige Instagram.

Por cada foto crea una copia en contenido/instagram/ (el original no se toca):
  - la gira según la orientación con la que se hizo (fotos de móvil)
  - la recorta por el centro si es más alargada de lo que admite Instagram
    (entre 4:5 vertical y 1,91:1 horizontal)
  - la reduce si mide más de 1440 píxeles de ancho
  - la guarda en JPG (acepta también PNG, WEBP y HEIC de iPhone)
  - quita los datos ocultos de la foto, como la ubicación GPS

Uso:
  python adaptar.py
"""

from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

RAIZ = Path(__file__).parent
CONTENIDO = RAIZ / "contenido"
ADAPTADAS = CONTENIDO / "instagram"

EXT_FOTO = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
PROPORCION_MIN = 4 / 5  # la más vertical que admite Instagram
PROPORCION_MAX = 1.91  # la más horizontal
ANCHO_MAX = 1440
ANCHO_MIN = 320


def ruta_adaptada(archivo):
    """Dónde queda la versión adaptada de una foto de contenido/."""
    return ADAPTADAS / f"{Path(archivo).stem}.jpg"


def recortar(foto):
    ancho, alto = foto.size
    proporcion = ancho / alto
    if proporcion < PROPORCION_MIN:
        nuevo_alto = round(ancho / PROPORCION_MIN)
        arriba = (alto - nuevo_alto) // 2
        return foto.crop((0, arriba, ancho, arriba + nuevo_alto))
    if proporcion > PROPORCION_MAX:
        nuevo_ancho = round(alto * PROPORCION_MAX)
        izquierda = (ancho - nuevo_ancho) // 2
        return foto.crop((izquierda, 0, izquierda + nuevo_ancho, alto))
    return foto


def adaptar(origen, destino):
    with Image.open(origen) as foto:
        foto = ImageOps.exif_transpose(foto).convert("RGBA")
    # Las zonas transparentes (fotos de producto sin fondo) quedan en blanco.
    fondo = Image.new("RGBA", foto.size, "white")
    foto = Image.alpha_composite(fondo, foto).convert("RGB")
    foto = recortar(foto)
    if foto.width > ANCHO_MAX:
        foto = foto.resize((ANCHO_MAX, round(foto.height * ANCHO_MAX / foto.width)), Image.LANCZOS)
    destino.parent.mkdir(exist_ok=True)
    # Sin pasar exif=..., la copia se guarda sin datos ocultos (ni GPS).
    foto.save(destino, "JPEG", quality=90, optimize=True)
    return foto.size


def main():
    fotos = sorted(p for p in CONTENIDO.iterdir() if p.suffix.lower() in EXT_FOTO)
    usados = {}
    for origen in fotos:
        destino = ruta_adaptada(origen.name)
        if destino in usados:
            print(f"⚠️  {origen.name}: se llama igual que {usados[destino]}, cámbiale el nombre")
            continue
        usados[destino] = origen.name
        ancho, alto = adaptar(origen, destino)
        aviso = "  ⚠️ muy pequeña, se verá borrosa" if ancho < ANCHO_MIN else ""
        print(f"✅ {origen.name} → instagram/{destino.name} ({ancho}×{alto}){aviso}")

    # Borra las adaptadas cuyo original ya no existe.
    if ADAPTADAS.exists():
        for sobrante in ADAPTADAS.glob("*.jpg"):
            if sobrante not in usados:
                sobrante.unlink()
                print(f"🗑️  instagram/{sobrante.name} (ya no está el original)")


if __name__ == "__main__":
    main()
