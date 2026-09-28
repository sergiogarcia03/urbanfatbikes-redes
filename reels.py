"""Convierte las tarjetas marcadas con "reel: sí" en reels animados.

Cada reel se guarda como contenido/reel-<nombre>.mp4 (vídeo vertical 1080 × 1920)
y se usa en calendario.yaml como cualquier otro vídeo.
Usa las mismas diapositivas que las tarjetas, pero con movimiento: el texto entra
deslizándose, las cifras cuentan hacia arriba y una barra marca el progreso.
No usa inteligencia artificial.

Si la tarjeta lleva "musica: archivo.mp3", se usa ese audio (de contenido/musica/).
Tiene que ser música libre de derechos o con licencia para redes sociales.

Uso:
  python reels.py
"""

import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import yaml
from PIL import Image, ImageDraw

import tarjetas
from tarjetas import ANCHO, ALTO, TURQUESA, contenido, fondo, pie

RAIZ = Path(__file__).parent
CONTENIDO = RAIZ / "contenido"
MUSICA = CONTENIDO / "musica"
HUELLAS = CONTENIDO / "reels.json"  # para no rehacer reels que no han cambiado

ALTO_REEL = 1920
ARRIBA = (ALTO_REEL - ALTO) // 2  # la diapositiva va centrada en el vídeo
FPS = 30
ENTRADA = 0.5  # segundos que tarda en entrar el texto
SALIDA = 0.3  # segundos del fundido al pasar a la siguiente
CUENTA = 0.9  # segundos que tarda una cifra en contar hasta su valor


def suave(t):
    """Curva de animación: empieza rápido y frena al final."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def duracion(datos):
    """Segundos que se ve una diapositiva: más texto, más tiempo para leerlo."""
    texto = " ".join(str(datos.get(k, "")) for k in ("antetitulo", "titulo", "subtitulo", "texto", "unidad"))
    texto += " ".join(datos.get("puntos") or [])
    extra = 0.8 if datos["tipo"] == "cierre" else 0.0
    return min(4.5, max(2.0, 0.8 + len(texto) / 24)) + extra


def numero_animado(datos, t):
    """Si la cifra es un número entero, la hace contar desde 0."""
    numero = str(datos["numero"])
    if not numero.isdigit():
        return datos
    return {**datos, "numero": round(int(numero) * suave(t / CUENTA))}


def fotogramas(tarjeta):
    diapositivas = tarjeta["diapositivas"]
    total = len(diapositivas)
    tiempos = [duracion(d) for d in diapositivas]
    duracion_total = sum(tiempos)
    transcurrido = 0.0
    # Pie con el logo y @urbanfatbikes (sin numeración), a la altura de la diapositiva
    capa_pie = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    pie(capa_pie, 0, 1)
    fondos = [fondo(i, total, ALTO_REEL) for i in range(total)]
    for f in fondos:
        f.alpha_composite(capa_pie, (0, ARRIBA))
    for indice, datos in enumerate(diapositivas):
        capa_fija = None if datos["tipo"] == "dato" else contenido(datos)
        cuadros = round(tiempos[indice] * FPS)
        for cuadro in range(cuadros):
            t = cuadro / FPS
            restante = tiempos[indice] - t

            # Fondo: fundido con el de la siguiente diapositiva al salir
            imagen = fondos[indice]
            if restante < SALIDA and indice < total - 1:
                imagen = Image.blend(fondos[indice], fondos[indice + 1], 1 - restante / SALIDA)
            imagen = imagen.copy()

            capa = capa_fija or contenido(numero_animado(datos, t))
            # Entrada: sube y aparece (la primera se ve entera desde el principio,
            # así la portada del reel no sale vacía).
            avance = 1.0 if indice == 0 else suave(t / ENTRADA)
            opacidad = avance
            if restante < SALIDA and indice < total - 1:
                opacidad *= restante / SALIDA
            if opacidad < 1:
                capa = capa.copy()
                capa.putalpha(capa.getchannel("A").point(lambda a: round(a * opacidad)))
            imagen.alpha_composite(capa, (0, ARRIBA + round(80 * (1 - avance))))

            # Barra de progreso arriba
            progreso = (transcurrido + t) / duracion_total
            barra = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(barra)
            d.rounded_rectangle((60, 150, ANCHO - 60, 158), radius=4, fill=(255, 255, 255, 60))
            d.rounded_rectangle((60, 150, 60 + round((ANCHO - 120) * progreso), 158), radius=4, fill=TURQUESA)
            imagen.alpha_composite(barra)
            yield imagen.convert("RGB")
        transcurrido += tiempos[indice]


def huella(tarjeta):
    """Resumen de todo lo que influye en el vídeo, para saber si ha cambiado."""
    h = hashlib.sha256(json.dumps(tarjeta, sort_keys=True, ensure_ascii=False).encode())
    for archivo in (Path(__file__), Path(tarjetas.__file__)):
        h.update(archivo.read_bytes())
    for clave in ("imagen", "musica"):
        for datos in [tarjeta] + tarjeta["diapositivas"]:
            if datos.get(clave):
                carpeta = MUSICA if clave == "musica" else CONTENIDO
                h.update((carpeta / datos[clave]).read_bytes())
    return h.hexdigest()


def generar(tarjeta, destino):
    segundos = sum(duracion(d) for d in tarjeta["diapositivas"])
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ffmpeg, "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO_REEL}", "-r", str(FPS), "-i", "-"]
    if tarjeta.get("musica"):
        orden += ["-i", str(MUSICA / tarjeta["musica"]), "-af", f"afade=t=out:st={max(0, segundos - 1.5):.2f}:d=1.5"]
    else:
        # Pista de audio en silencio: Instagram la espera aunque no haya música.
        orden += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    orden += ["-map", "0:v", "-map", "1:a", "-shortest",
              "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "20", "-g", "60",
              "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(destino)]
    proceso = subprocess.Popen(orden, stdin=subprocess.PIPE)
    for imagen in fotogramas(tarjeta):
        proceso.stdin.write(imagen.tobytes())
    proceso.stdin.close()
    if proceso.wait() != 0:
        raise SystemExit(f"❌ No se pudo crear {destino.name}")


def main():
    datos = yaml.safe_load(tarjetas.DEFINICIONES.read_text(encoding="utf-8")) or {}
    huellas = json.loads(HUELLAS.read_text()) if HUELLAS.exists() else {}
    nuevas = {}
    for tarjeta in datos.get("tarjetas") or []:
        if not tarjeta.get("reel"):
            continue
        destino = CONTENIDO / f"reel-{tarjeta['nombre']}.mp4"
        nuevas[destino.name] = huella(tarjeta)
        if destino.exists() and huellas.get(destino.name) == nuevas[destino.name]:
            print(f"⏭️  {destino.name} (sin cambios)")
            continue
        generar(tarjeta, destino)
        print(f"✅ {destino.name}")

    # Borra los reels que ya no están en tarjetas.yaml.
    for sobrante in CONTENIDO.glob("reel-*.mp4"):
        if sobrante.name not in nuevas:
            sobrante.unlink()
            print(f"🗑️  {sobrante.name}")
    HUELLAS.write_text(json.dumps(nuevas, indent=2) + "\n")


if __name__ == "__main__":
    main()
