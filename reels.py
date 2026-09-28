"""Convierte las tarjetas marcadas con "reel: sí" en reels animados.

Cada reel se guarda como contenido/reel-<nombre>.mp4 (vídeo vertical 1080 × 1920)
y se usa en calendario.yaml como cualquier otro vídeo.
Usa las mismas diapositivas que las tarjetas, pero con movimiento: el texto entra
deslizándose, las cifras cuentan hacia arriba y una barra marca el progreso.
No usa inteligencia artificial.

Si la tarjeta lleva "musica: archivo.mp3", se usa ese audio (de contenido/musica/).
Tiene que ser música libre de derechos o con licencia para redes sociales.

Si lleva "voz" (una o varias grabaciones de contenido/voz/), el reel se ajusta
a la voz: cada frase acompaña a su diapositiva y la música baja mientras se habla.
Conviene poner en cada diapositiva su frase del guion ("dice") para repartir bien.

Uso:
  python reels.py
"""

import functools
import hashlib
import json
import math
import re
import subprocess
from array import array
from pathlib import Path

import imageio_ffmpeg
import yaml
from PIL import Image, ImageDraw

import tarjetas
from tarjetas import ANCHO, ALTO, TURQUESA, contenido, fondo, pie

RAIZ = Path(__file__).parent
CONTENIDO = RAIZ / "contenido"
MUSICA = CONTENIDO / "musica"
VOZ = CONTENIDO / "voz"
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


# --- Voz ----------------------------------------------------------------------
#
# La voz se trata sola, sin tener que ajustar nada a mano:
#   1. Se juntan todas las grabaciones del reel, en orden.
#   2. Se buscan los tramos en los que se habla (separados por silencios).
#   3. Se reparten los tramos entre las diapositivas. Si las diapositivas llevan
#      su frase del guion ("dice"), se usa la duración esperada de cada frase
#      (por sílabas) y las pausas más largas; si no, solo las pausas.
#   4. Se monta una pista nueva con pausas cortas y regulares (más ritmo).
#   5. Se limpia: sin golpes graves ni ruido de fondo, "eses" suavizadas,
#      voz más clara y volumen estándar.

ANTES_VOZ = 0.3  # segundos de vídeo antes de que empiece a hablar
FM_VOZ = 44100
PAUSA_FRASE = 0.28  # pausa máxima dentro de una misma diapositiva
PAUSA_DIAPOSITIVA = 0.5  # pausa al pasar de una diapositiva a la siguiente
MARGEN_TRAMO = (0.06, 0.12)  # sonido que se conserva antes y después de cada tramo
LIMPIEZA_VOZ = ("highpass=f=90,afftdn=nf=-30:nr=12,equalizer=f=250:t=q:w=1:g=-2,"
                "equalizer=f=3200:t=q:w=1.2:g=2.5,deesser=i=0.4,"
                "acompressor=threshold=-22dB:ratio=3:attack=5:release=120:makeup=2,"
                "loudnorm=I=-16:TP=-1.5:LRA=7")


def archivos_de_voz(tarjeta):
    voz = tarjeta.get("voz") or []
    return [VOZ / a for a in ([voz] if isinstance(voz, str) else voz)]


def pcm(archivo):
    """Audio de una grabación como muestras de 16 bits, mono, sin graves molestos."""
    return subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", str(archivo),
         "-af", "highpass=f=90,highpass=f=90", "-ac", "1", "-ar", str(FM_VOZ), "-f", "s16le", "-"],
        capture_output=True, check=True).stdout


def tramos_con_voz(muestras):
    """Tramos (inicio, fin) en segundos en los que se habla."""
    datos = array("h", muestras)
    ventana = FM_VOZ // 50  # 20 ms
    energia = []
    for i in range(0, len(datos) - ventana, ventana):
        trozo = datos[i:i + ventana]
        energia.append(math.sqrt(sum(x * x for x in trozo[::4]) / (len(trozo) / 4)) / 32768)
    if not energia:
        return []
    # Umbral según el ruido de fondo de esta grabación
    ordenada = sorted(energia)
    fondo_ = ordenada[len(ordenada) // 10]
    pico = ordenada[int(len(ordenada) * 0.98)]
    umbral = max(fondo_ * 3, pico * 0.06)
    tramos, inicio, silencio = [], None, 0
    for k, e in enumerate(energia + [0.0] * 20):
        if e > umbral:
            if inicio is None:
                inicio = k
            silencio = 0
        elif inicio is not None:
            silencio += 1
            if silencio * 0.02 >= 0.12:  # 120 ms de silencio cierran el tramo
                tramos.append((inicio * 0.02, (k - silencio + 1) * 0.02))
                inicio, silencio = None, 0
    return [t for t in tramos if t[1] - t[0] >= 0.1]  # fuera chasquidos sueltos


def silabas(texto):
    return max(1, len(re.findall(r"[aeiouáéíóúü]+", str(texto).lower())))


def repartir(tramos, diapositivas):
    """Agrupa los tramos seguidos en tantas partes como diapositivas.

    Busca el reparto cuyas duraciones se parezcan más a lo esperado por el guion
    y que corte por las pausas más largas.
    """
    n, m = len(diapositivas), len(tramos)
    if m < n:
        raise SystemExit(f"❌ La voz tiene {m} frases y el reel {n} diapositivas. "
                         "Graba una frase por diapositiva, con una pausa entre frases.")
    pesos = [silabas(d.get("dice", "")) if any(x.get("dice") for x in diapositivas) else 1 for d in diapositivas]
    total_voz = sum(b - a for a, b in tramos)
    esperado = [total_voz * p / sum(pesos) for p in pesos]
    pausa = [tramos[k + 1][0] - tramos[k][1] for k in range(m - 1)]
    max_pausa = max(pausa) if pausa else 1

    @functools.lru_cache(maxsize=None)
    def mejor(k, i):
        """Mejor coste para repartir los tramos k.. entre las diapositivas i.."""
        if i == n:
            return (0.0, ()) if k == m else (math.inf, ())
        resultado = (math.inf, ())
        for fin in range(k + 1, m - (n - i - 1) + 1):
            duracion_ = sum(b - a for a, b in tramos[k:fin])
            coste = ((duracion_ - esperado[i]) / max(esperado[i], 0.5)) ** 2
            if fin < m:
                coste -= 0.8 * pausa[fin - 1] / max_pausa  # premio a cortar en pausas largas
            resto = mejor(fin, i + 1)
            if coste + resto[0] < resultado[0]:
                resultado = (coste + resto[0], (fin,) + resto[1])
        return resultado

    cortes = (0,) + mejor(0, 0)[1]
    return [tramos[a:b] for a, b in zip(cortes, cortes[1:])]


def preparar_voz(tarjeta):
    """Monta y limpia la pista de voz. Devuelve (archivo, inicio de cada diapositiva, duración)."""
    # Se colocan todas las grabaciones en una línea de tiempo común; el paso de
    # una grabación a otra cuenta como una pausa larga (buen sitio para cortar).
    tramos, locales, fuentes, desplazamiento = [], [], [], 0.0
    for archivo in archivos_de_voz(tarjeta):
        muestras = pcm(archivo)
        propios = tramos_con_voz(muestras)
        for a, b in propios:
            tramos.append((desplazamiento + a, desplazamiento + b))
            locales.append((a, b))
            fuentes.append(muestras)
        if propios:
            desplazamiento += propios[-1][1] + 2.0
    grupos_globales = repartir(tramos, tarjeta["diapositivas"])
    # Vuelve a los tiempos de cada grabación para recortar el audio
    grupos, k = [], 0
    for grupo in grupos_globales:
        grupos.append(locales[k:k + len(grupo)])
        k += len(grupo)

    # Nueva pista: cada tramo con su margen y pausas cortas y regulares
    salida, inicios, posicion = bytearray(), [], 0.0
    indice = 0
    for g, grupo in enumerate(grupos):
        inicios.append(posicion)
        for j, (a, b) in enumerate(grupo):
            muestras = fuentes[indice]
            indice += 1
            desde = max(0, int((a - MARGEN_TRAMO[0]) * FM_VOZ)) * 2
            hasta = min(len(muestras), int((b + MARGEN_TRAMO[1]) * FM_VOZ) * 2)
            salida += muestras[desde:hasta]
            posicion += (hasta - desde) / 2 / FM_VOZ
            if j < len(grupo) - 1:
                siguiente = grupo[j + 1][0]
                hueco = min(PAUSA_FRASE, max(0.0, siguiente - b - sum(MARGEN_TRAMO)))
            elif g < len(grupos) - 1:
                hueco = PAUSA_DIAPOSITIVA
            else:
                hueco = 0.0
            salida += bytes(int(hueco * FM_VOZ) * 2)
            posicion += hueco

    crudo = CONTENIDO / ".voz-cruda.raw"
    limpio = CONTENIDO / ".voz-limpia.wav"
    crudo.write_bytes(salida)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-f", "s16le", "-ar", str(FM_VOZ), "-ac", "1", "-i", str(crudo),
                    "-af", LIMPIEZA_VOZ, "-ar", str(FM_VOZ), "-ac", "2", str(limpio)], check=True)
    crudo.unlink()
    return limpio, inicios, posicion


def tiempos(tarjeta, voz=None):
    """Duración de cada diapositiva (ajustada a la voz si la hay)."""
    if not voz:
        return [duracion(d) for d in tarjeta["diapositivas"]]
    _, inicios, total = voz
    cambios = [0.0] + [ANTES_VOZ + x - 0.15 for x in inicios[1:]]
    cola = 2.0 if tarjeta["diapositivas"][-1]["tipo"] == "cierre" else 1.2
    final = ANTES_VOZ + total + cola
    return [max(1.0, b - a) for a, b in zip(cambios, cambios[1:] + [final])]


# --- Vídeo ----------------------------------------------------------------------


def fotogramas(tarjeta, tiempos_):
    diapositivas = tarjeta["diapositivas"]
    total = len(diapositivas)
    duracion_total = sum(tiempos_)
    transcurrido = 0.0
    # Pie con el logo y @urbanfatbikes (sin numeración), a la altura de la diapositiva
    capa_pie = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    pie(capa_pie, 0, 1)
    fondos = [fondo(i, total, ALTO_REEL) for i in range(total)]
    for f in fondos:
        f.alpha_composite(capa_pie, (0, ARRIBA))
    for indice, datos in enumerate(diapositivas):
        capa_fija = None if datos["tipo"] == "dato" else contenido(datos)
        cuadros = round(tiempos_[indice] * FPS)
        for cuadro in range(cuadros):
            t = cuadro / FPS
            restante = tiempos_[indice] - t

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
        transcurrido += tiempos_[indice]


def huella(tarjeta):
    """Resumen de todo lo que influye en el vídeo, para saber si ha cambiado."""
    h = hashlib.sha256(json.dumps(tarjeta, sort_keys=True, ensure_ascii=False).encode())
    for archivo in (Path(__file__), Path(tarjetas.__file__)):
        h.update(archivo.read_bytes())
    for datos in [tarjeta] + tarjeta["diapositivas"]:
        if datos.get("imagen"):
            h.update((CONTENIDO / datos["imagen"]).read_bytes())
    if tarjeta.get("musica"):
        h.update((MUSICA / tarjeta["musica"]).read_bytes())
    for archivo in archivos_de_voz(tarjeta):
        h.update(archivo.read_bytes())
    return h.hexdigest()


def generar(tarjeta, destino):
    voz = preparar_voz(tarjeta) if tarjeta.get("voz") else None
    tiempos_ = tiempos(tarjeta, voz)
    segundos = sum(tiempos_)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    orden = [ffmpeg, "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO_REEL}", "-r", str(FPS), "-i", "-"]
    if tarjeta.get("musica"):
        orden += ["-stream_loop", "-1", "-i", str(MUSICA / tarjeta["musica"])]
    else:
        # Pista de audio en silencio: Instagram la espera aunque no haya música.
        orden += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    final = f"afade=t=out:st={max(0, segundos - 1.5):.2f}:d=1.5"
    if tarjeta.get("voz"):
        retardo = round(ANTES_VOZ * 1000)
        orden += ["-i", str(voz[0]), "-filter_complex",
                  f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                  f"adelay={retardo}|{retardo},apad,asplit=2[v1][v2];"
                  # La música baja sola mientras se habla
                  f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.5[m];"
                  f"[m][v1]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[mb];"
                  f"[mb][v2]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5,{final}[a]",
                  "-map", "0:v", "-map", "[a]"]
    else:
        orden += ["-af", final, "-map", "0:v", "-map", "1:a"]
    orden += ["-t", f"{segundos:.2f}",
              "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "20", "-g", "60",
              "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(destino)]
    proceso = subprocess.Popen(orden, stdin=subprocess.PIPE)
    for imagen in fotogramas(tarjeta, tiempos_):
        proceso.stdin.write(imagen.tobytes())
    proceso.stdin.close()
    if proceso.wait() != 0:
        raise SystemExit(f"❌ No se pudo crear {destino.name}")
    if voz:
        voz[0].unlink()


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
