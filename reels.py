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

import difflib
import functools
import hashlib
import json
import math
import os
import re
import subprocess
import unicodedata
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
ALARGAMIENTO = 0.25  # un sonido quieto más largo que esto es un «eeeh» o una vocal alargada
MARGEN_TRAMO = (0.06, 0.12)  # sonido que se conserva antes y después de cada tramo
LIMPIEZA_VOZ = ("highpass=f=90,afftdn=nf=-30:nr=12,equalizer=f=250:t=q:w=1:g=-2,"
                "equalizer=f=3200:t=q:w=1.2:g=2.5,deesser=i=0.4,"
                "acompressor=threshold=-22dB:ratio=3:attack=5:release=120:makeup=2,"
                "loudnorm=I=-16:TP=-1.5:LRA=7")
# Con «limpieza: fuerte» en la tarjeta, antes de lo anterior se quita el ruido de
# fondo con un filtro de reducción de ruido para voz (RNNoise, modelo
# contenido/voz/quitar-ruido.rnnn: no cambia ni inventa la voz, solo quita ruido)
# y se bajan los ruidos sueltos entre palabras (respiraciones, roces).
MODELO_RUIDO = VOZ / "quitar-ruido.rnnn"
LIMPIEZA_FUERTE = (f"highpass=f=90,arnndn=m={MODELO_RUIDO.as_posix()}:mix=0.9,"
                   "agate=threshold=0.015:ratio=3:range=0.12:attack=8:release=250,")


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
    texto = str(texto).lower()
    digitos = len(re.findall(r"\d", texto))  # "V8": cada cifra cuenta como ~2 sílabas
    return max(1, len(re.findall(r"[aeiouáéíóúü]+", texto)) + 2 * digitos)


def palabras_del_guion(diapositivas):
    """Lista de (diapositiva, sílabas, pausa esperada después) para cada palabra."""
    lista = []
    for i, d in enumerate(diapositivas):
        trozos = re.findall(r"[^\s]+", str(d.get("dice", "")))
        for j, trozo in enumerate(trozos):
            if not re.search(r"[\wáéíóúüñ]", trozo, re.I):
                continue
            ultima = j == len(trozos) - 1
            if ultima or re.search(r"[.?!:;]$", trozo):
                pausa = 1.0  # final de frase: se espera una pausa clara
            elif trozo.endswith(","):
                pausa = 0.5
            else:
                pausa = 0.0
            lista.append((i, silabas(trozo), pausa))
    return lista


def repartir(tramos, diapositivas):
    """Asigna los tramos de voz a las diapositivas.

    Si hay guion ("dice"), alinea cada tramo con las palabras que dice: la duración
    de un tramo debe parecerse a la de sus sílabas, y las pausas largas deben caer
    donde el guion tiene un punto o una coma. Los tramos que no encajan en el guion
    (arranques en falso, "eeeh") se descartan. Devuelve una lista de grupos de
    tramos, uno por diapositiva.
    """
    n, m = len(diapositivas), len(tramos)
    palabras = palabras_del_guion(diapositivas) if all(d.get("dice") for d in diapositivas) else []
    if not palabras:
        return repartir_por_pausas(tramos, n)
    W = len(palabras)
    duraciones = [b - a for a, b in tramos]
    ritmo = sum(duraciones) / sum(s for _, s, _ in palabras)  # segundos por sílaba
    pausas = [tramos[k + 1][0] - tramos[k][1] for k in range(m - 1)] + [2.0]
    pausa_media = sorted(pausas)[len(pausas) // 2] or 0.3
    acumuladas = [0]
    for _, s, _ in palabras:
        acumuladas.append(acumuladas[-1] + s)
    DESCARTE = 3.0  # coste de dar por sobrante un tramo

    @functools.lru_cache(maxsize=None)
    def mejor(k, w):
        if k == m:
            return (0.0, ()) if w == W else (math.inf, ())
        # Opción 1: el tramo k sobra (titubeo, "eeeh", arranque en falso)
        coste = DESCARTE + duraciones[k] / max(ritmo * 4, 0.3)
        resto = mejor(k + 1, w)
        resultado = (coste + resto[0], (None,) + resto[1])
        # Opción 2: el tramo k dice las palabras w..w2-1 (de una misma diapositiva)
        for w2 in range(w + 1, min(W, w + 25) + 1):
            if palabras[w2 - 1][0] != palabras[w][0]:
                break
            esperado = ritmo * (acumuladas[w2] - acumuladas[w])
            coste = ((duraciones[k] - esperado) / (esperado + 0.3)) ** 2
            # Pausa tras el tramo: larga donde hay puntuación, corta donde no
            p = min(pausas[k] / pausa_media, 4.0)
            marca = palabras[w2 - 1][2]
            coste += 0.6 * (p - 1) * (0.5 - marca) if w2 < W else 0.0
            resto = mejor(k + 1, w2)
            if coste + resto[0] < resultado[0]:
                resultado = (coste + resto[0], (palabras[w][0],) + resto[1])
        return resultado

    total, asignacion = mejor(0, 0)
    if total == math.inf:
        return repartir_por_pausas(tramos, n)
    grupos = [[] for _ in range(n)]
    for tramo, diapositiva in zip(tramos, asignacion):
        if diapositiva is not None:
            grupos[diapositiva].append(tramo)
    if any(not g for g in grupos):
        return repartir_por_pausas(tramos, n)
    return grupos


def repartir_por_pausas(tramos, n):
    """Sin guion: corta por las n-1 pausas más largas."""
    if len(tramos) < n:
        raise SystemExit(f"❌ La voz tiene {len(tramos)} frases y el reel {n} diapositivas. "
                         "Graba una frase por diapositiva, con una pausa entre frases.")
    pausas = sorted(range(len(tramos) - 1), key=lambda k: tramos[k][1] - tramos[k + 1][0])[:n - 1]
    cortes = [0] + sorted(k + 1 for k in pausas) + [len(tramos)]
    return [tramos[a:b] for a, b in zip(cortes, cortes[1:])]


# --- Voz con transcripción (edición precisa) --------------------------------------
#
# Si cada grabación tiene su transcripción (contenido/voz/<audio>.json, creada por
# transcribir.py), se compara palabra a palabra lo dicho con el guion ("dice"):
# lo que no está en el guion (lo dicho antes de empezar, repeticiones, arranques
# en falso, "eeeh") se corta, y si una frase se repite se queda la última toma.

MULETILLAS = {"eh", "ehh", "eeh", "em", "emm", "ehm", "mm", "mmm", "hm", "ah", "aa"}
UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
            "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho",
            "diecinueve", "veinte", "veintiuno", "veintidos", "veintitres", "veinticuatro",
            "veinticinco", "veintiseis", "veintisiete", "veintiocho", "veintinueve"]
DECENAS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
CENTENAS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
            6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def numero_en_palabras(n):
    if n < 30:
        return UNIDADES[n]
    if n < 100:
        return DECENAS[n // 10] + ("" if n % 10 == 0 else " y " + UNIDADES[n % 10])
    if n == 100:
        return "cien"
    if n < 1000:
        return CENTENAS[n // 100] + ("" if n % 100 == 0 else " " + numero_en_palabras(n % 100))
    if n < 1000000:
        miles = "mil" if n // 1000 == 1 else numero_en_palabras(n // 1000) + " mil"
        return miles + ("" if n % 1000 == 0 else " " + numero_en_palabras(n % 1000))
    return str(n)


def normalizar(texto):
    """Pasa un texto a palabras sencillas: minúsculas, sin tildes, números en letra."""
    texto = str(texto).lower().replace("km/h", " kilometros por hora ").replace("%", " por ciento ")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"(\d+)", lambda m: " " + numero_en_palabras(int(m.group(1))) + " ", texto)
    return re.findall(r"[a-z]+", texto)


def parecido(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def alinear(guion, dicho):
    """Alinea palabras del guion con palabras dichas (Needleman-Wunsch).

    Se alinea del final al principio para que, si una frase se repite, cuente la
    última toma. Devuelve, para cada palabra dicha, el índice de la palabra del
    guion con la que se corresponde, o None si sobra.
    """
    g, d = guion[::-1], dicho[::-1]
    HUECO = -0.6
    filas, cols = len(g) + 1, len(d) + 1
    puntos = [[0.0] * cols for _ in range(filas)]
    for i in range(1, filas):
        puntos[i][0] = i * HUECO
    for j in range(1, cols):
        puntos[0][j] = j * HUECO
    for i in range(1, filas):
        for j in range(1, cols):
            p = parecido(g[i - 1], d[j - 1])
            igual = 2 * p - 1 if p >= 0.5 else -1.0
            if d[j - 1] in MULETILLAS:
                igual = -2.0
            puntos[i][j] = max(puntos[i - 1][j - 1] + igual, puntos[i - 1][j] + HUECO, puntos[i][j - 1] + HUECO)
    pareja = [None] * len(d)
    i, j = len(g), len(d)
    while i > 0 and j > 0:
        p = parecido(g[i - 1], d[j - 1])
        igual = 2 * p - 1 if p >= 0.5 else -1.0
        if d[j - 1] in MULETILLAS:
            igual = -2.0
        if puntos[i][j] == puntos[i - 1][j - 1] + igual:
            pareja[j - 1] = i - 1
            i, j = i - 1, j - 1
        elif puntos[i][j] == puntos[i - 1][j] + HUECO:
            i -= 1
        else:
            j -= 1
    # Deshace el orden invertido
    n_g = len(g)
    return [None if x is None else n_g - 1 - x for x in pareja[::-1]]


def transcripciones(tarjeta):
    """Lista de transcripciones (una por grabación) o None si falta alguna."""
    lista = []
    for archivo in archivos_de_voz(tarjeta):
        json_ = archivo.with_name(archivo.name + ".json")
        if not json_.exists():
            return None
        palabras = json.loads(json_.read_text(encoding="utf-8"))["palabras"]
        # «quitar: {audio: [[inicio, fin], ...]}» descarta a mano tramos de la grabación
        # (por ejemplo, un intento fallido que el programa no distingue solo).
        for inicio, fin in (tarjeta.get("quitar") or {}).get(archivo.name, []):
            palabras = [w for w in palabras if not inicio <= (w["inicio"] + w["fin"]) / 2 <= fin]
        lista.append(palabras)
    return lista


def rasgos_sonido(muestras):
    """Rasgos del sonido cada 10 ms (energía por bandas, como el oído)."""
    import numpy as np
    x = np.frombuffer(muestras, dtype="<i2").astype(float) / 32768
    n, salto = int(0.025 * FM_VOZ), int(0.010 * FM_VOZ)
    tramas = np.lib.stride_tricks.sliding_window_view(x, n)[::salto] * np.hanning(n)
    espectro = np.abs(np.fft.rfft(tramas, axis=1)) ** 2
    frec = np.fft.rfftfreq(n, 1 / FM_VOZ)
    mel = 2595 * np.log10(1 + frec / 700)
    bordes = np.linspace(2595 * np.log10(1 + 80 / 700), 2595 * np.log10(1 + 7000 / 700), 26)
    bandas = np.stack([espectro[:, (mel >= bordes[i]) & (mel < bordes[i + 2])].sum(1) for i in range(24)], 1)
    rasgos = np.log(bandas + 1e-9)
    return rasgos - rasgos.mean(0)


def distancia(a, b):
    """Parecido entre dos sonidos (DTW): cuanto más bajo, más se parecen."""
    import numpy as np
    coste = np.linalg.norm(a[:, None] - b[None], axis=2)
    D = np.full((len(a) + 1, len(b) + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            D[i, j] = coste[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return D[-1, -1] / (len(a) + len(b))


def tartamudeos_internos(textos, fuentes, diapositiva_palabra):
    """Busca repeticiones dentro de una misma palabra ("com… compártelo").

    Whisper a veces escribe la palabra una sola vez aunque se haya dicho a trozos.
    Se sospecha de las palabras que duran mucho más de lo que tocan por sus sílabas
    y tienen una pausa dentro; si el trozo de antes de la pausa suena igual que lo
    que viene después, es un arranque en falso. Devuelve los tramos a quitar
    (grabación, inicio, fin).
    """
    import numpy as np
    claves = [c for c in diapositiva_palabra]
    silabas_total = sum(silabas(textos[g][k]["palabra"]) for g, k in claves)
    segundos_total = sum(textos[g][k]["fin"] - textos[g][k]["inicio"] for g, k in claves)
    ritmo = segundos_total / max(silabas_total, 1)
    cortes = []
    for g, muestras in enumerate(fuentes):
        rasgos = None
        con_voz = tramos_con_voz(muestras)
        for k, p in enumerate(textos[g]):
            if (g, k) not in diapositiva_palabra:
                continue
            dura = p["fin"] - p["inicio"]
            if dura < 0.7 or dura < 1.6 * ritmo * silabas(p["palabra"]):
                continue
            # Partes con voz dentro de la palabra (separadas por pausas de al menos 0,1 s)
            partes = [(max(a, p["inicio"]), min(b, p["fin"])) for a, b in con_voz
                      if b > p["inicio"] and a < p["fin"]]
            if len(partes) < 2:
                continue
            if rasgos is None:
                rasgos = rasgos_sonido(muestras)
            trozo = lambda a, b: rasgos[int(a * 100):int(b * 100)]
            primero = partes[0]
            largo = min(0.45, primero[1] - primero[0])
            if largo < 0.12:
                continue
            A = trozo(primero[0], primero[0] + largo)
            # Referencia: cuánto se parece A a palabras que no tienen nada que ver
            rng = np.random.default_rng(k)
            otros = [d for d in textos[g] if abs(d["inicio"] - p["inicio"]) > 1.5 and d["fin"] - d["inicio"] > largo]
            if len(otros) < 3:
                continue
            referencia = np.median([distancia(A, trozo(d["inicio"], d["inicio"] + largo))
                                    for d in rng.choice(otros, min(8, len(otros)), replace=False)])
            mejor, donde = math.inf, None
            t = primero[1] + 0.1
            while t < p["fin"] + 0.2:
                d = distancia(A, trozo(t, t + largo))
                if d < mejor:
                    mejor, donde = d, t
                t += 0.03
            if donde is not None and mejor < 0.65 * referencia:
                cortes.append((g, primero[0] - 0.02, donde - 0.03))
    return cortes


def alargamientos(muestras, tramos):
    """Busca «eeeh», «mmm» y vocales alargadas («yyy», «queee») dentro de los tramos.

    Whisper no suele escribirlos. Se reconocen porque el sonido se queda quieto
    (mismo timbre) mucho más tiempo que una vocal normal. Se deja el principio,
    para que la palabra no quede cortada, y se quita el resto. Devuelve los
    tramos a quitar (inicio, fin).
    """
    import numpy as np
    rasgos = rasgos_sonido(muestras)
    x = np.frombuffer(muestras, dtype="<i2").astype(float) / 32768
    n, salto = int(0.025 * FM_VOZ), int(0.010 * FM_VOZ)
    energia = 20 * np.log10(np.sqrt((np.lib.stride_tricks.sliding_window_view(x, n)[::salto] ** 2).mean(1)) + 1e-9)
    cambio = np.r_[np.linalg.norm(rasgos[4:] - rasgos[:-4], axis=1), np.full(4, np.inf)]
    voz = energia > np.percentile(energia, 98) - 30
    quieto = voz & (cambio < np.percentile(cambio[voz], 25))
    cortes, t = [], 0
    while t < len(quieto):
        if not quieto[t]:
            t += 1
            continue
        u = t
        while u < len(quieto) and quieto[u]:
            u += 1
        inicio, fin = t * 0.01, u * 0.01 + 0.04
        if fin - inicio >= ALARGAMIENTO and any(a <= inicio and fin <= b for a, b in tramos):
            cortes.append((inicio + 0.10, fin - 0.03))
        t = u
    return cortes


def pausas_internas(con_voz, tramos):
    """Silencios largos dentro de un trozo (dudas a mitad de frase): se quitan y al
    montar se pone una pausa corta y regular."""
    cortes = []
    for a, b in tramos:
        dentro = [(x, y) for x, y in con_voz if y > a and x < b]
        for (_, fin), (inicio, _) in zip(dentro, dentro[1:]):
            if inicio - fin > PAUSA_FRASE + 0.1:
                cortes.append((fin + 0.06, inicio - 0.04))
    return cortes


def preparar_voz_con_texto(tarjeta, textos):
    diapositivas = tarjeta["diapositivas"]
    # Palabras del guion, con su diapositiva
    guion, diapositiva_de = [], []
    for i, d in enumerate(diapositivas):
        for palabra in normalizar(d["dice"]):
            guion.append(palabra)
            diapositiva_de.append(i)
    # Palabras dichas (una palabra de Whisper puede dar varias, p. ej. "250")
    dicho, origen = [], []
    for g, palabras in enumerate(textos):
        for k, p in enumerate(palabras):
            for trozo in normalizar(p["palabra"]) or ["?"]:
                dicho.append(trozo)
                origen.append((g, k))  # (grabación, palabra); al juntar se encadenan
    # Palabras que Whisper separa y el guion junta ("ciclo motor" / "ciclomotor")
    del_guion = set(guion)
    j = 0
    while j + 1 < len(dicho):
        junta = dicho[j] + dicho[j + 1]
        if junta in del_guion and dicho[j] not in del_guion:
            dicho[j:j + 2] = [junta]
            origen[j:j + 2] = [origen[j] + origen[j + 1]]
        else:
            j += 1
    pareja = alinear(guion, dicho)
    # Una palabra dicha se queda si alguna de sus partes está en el guion
    diapositiva_palabra = {}
    for claves, par in zip(origen, pareja):
        for g, k in zip(claves[::2], claves[1::2]):
            if par is not None and (g, k) not in diapositiva_palabra:
                diapositiva_palabra[(g, k)] = diapositiva_de[par]

    # Arranques en falso: si dentro de una frase hay un trocito (1-2 palabras)
    # y después se vuelve a empezar con la misma palabra, sobra el trocito.
    orden = [(g, k) for g, palabras in enumerate(textos) for k in range(len(palabras))]
    tandas, actual = [], []
    for clave in orden:
        if clave in diapositiva_palabra:
            actual.append(clave)
        elif actual:
            tandas.append(actual)
            actual = []
    if actual:
        tandas.append(actual)
    palabra = lambda c: " ".join(normalizar(textos[c[0]][c[1]]["palabra"]))
    for n, tanda in enumerate(tandas[:-1]):
        siguiente = tandas[n + 1]
        if (len(tanda) <= 2 and diapositiva_palabra[tanda[0]] == diapositiva_palabra[siguiente[0]]
                and any(parecido(palabra(tanda[0]), palabra(c)) >= 0.7 for c in siguiente[:3])):
            for clave in tanda:
                del diapositiva_palabra[clave]
    if len({v for v in diapositiva_palabra.values()}) < len(diapositivas):
        return None  # no se ha reconocido alguna frase: se usa el método por pausas

    if os.environ.get("REELS_DETALLE"):
        for i in range(len(diapositivas)):
            print(f"      {i + 1}: " + " ".join(textos[g][k]["palabra"] for g, k in orden
                                            if diapositiva_palabra.get((g, k)) == i))
    fuentes = [pcm(a) for a in archivos_de_voz(tarjeta)]
    sobran = [(textos[g][k]["palabra"]) for g, palabras in enumerate(textos)
              for k in range(len(palabras)) if (g, k) not in diapositiva_palabra]
    if sobran:
        print(f"   ✂️  {tarjeta['nombre']}: quitado «{' '.join(sobran)}»")

    # Trozos de audio: palabras seguidas que se quedan, en la misma grabación
    trozos = []  # (grabación, inicio, fin, diapositiva)
    for g, palabras in enumerate(textos):
        for k, p in enumerate(palabras):
            if (g, k) not in diapositiva_palabra:
                continue
            anterior_fin = palabras[k - 1]["fin"] if k > 0 else 0.0
            siguiente_ini = palabras[k + 1]["inicio"] if k + 1 < len(palabras) else p["fin"] + 1.0
            # Margen para no comerse consonantes, sin invadir palabras vecinas
            ini = max(p["inicio"] - 0.05, (anterior_fin + p["inicio"]) / 2 if k > 0 else 0.0)
            fin = min(p["fin"] + 0.08, (p["fin"] + siguiente_ini) / 2)
            diap = diapositiva_palabra[(g, k)]
            seguido = k > 0 and (g, k - 1) in diapositiva_palabra
            palabra_ = (p["inicio"], p["fin"])
            if trozos and seguido and trozos[-1][0] == g and trozos[-1][3] == diap:
                trozos[-1][2] = fin
                trozos[-1][5] = palabra_
            else:
                # [grabación, inicio, fin, diapositiva, primera palabra, última palabra, pegado]
                # (pegado: va justo detrás del anterior, sin pausa, porque se ha quitado un sonido alargado)
                trozos.append([g, ini, fin, diap, palabra_, palabra_, False])

    # Ajuste fino con la energía del sonido: Whisper a veces adelanta o alarga
    # las palabras; se recorta el silencio que haya en los bordes de cada trozo.
    # Además, si junto a un corte se ha quitado una palabra, el corte se lleva al
    # silencio más cercano: así no se oye el final o el principio de lo quitado.
    # Solo se mueve si la palabra que se queda está casi toda al otro lado del
    # silencio; si va pegada a lo quitado, se respeta (mejor que comérsela).
    con_voz = [tramos_con_voz(f) for f in fuentes]
    for trozo in trozos:
        g, ini, fin = trozo[0], trozo[1], trozo[2]
        dentro = [(a, b) for a, b in con_voz[g] if b > ini and a < fin]
        if not dentro:
            continue
        mitad_primera = (trozo[4][0] + trozo[4][1]) / 2
        mitad_ultima = (trozo[5][0] + trozo[5][1]) / 2
        if dentro[0][0] < ini and len(dentro) > 1 and dentro[1][0] <= mitad_primera:
            dentro = dentro[1:]  # empieza a mitad de un sonido que era de lo quitado
            ini = dentro[0][0] - 0.05
        if dentro[-1][1] > fin + 0.08 and len(dentro) > 1 and dentro[-2][1] >= mitad_ultima:
            dentro = dentro[:-1]  # acaba a mitad de un sonido que era de lo quitado
            fin = dentro[-1][1] + 0.08
        trozo[1] = max(ini, dentro[0][0] - 0.05)
        trozo[2] = min(fin, dentro[-1][1] + 0.08)

    # Tartamudeos dentro de una palabra, «eeeh» y sonidos alargados que Whisper no
    # escribe, y silencios largos a mitad de frase: se parte el trozo y se quita.
    cortes = [(g, a, b, "tartamudeo") for g, a, b in tartamudeos_internos(textos, fuentes, diapositiva_palabra)]
    for g, muestras in enumerate(fuentes):
        tramos_g = [(t[1], t[2]) for t in trozos if t[0] == g]
        cortes += [(g, a, b, "«eeeh» o sonido alargado") for a, b in alargamientos(muestras, tramos_g)]
        cortes += [(g, a, b, "pausa larga") for a, b in pausas_internas(con_voz[g], tramos_g)]
    for g, desde, hasta, motivo in sorted(cortes, key=lambda c: (c[0], c[1])):
        print(f"   ✂️  {tarjeta['nombre']}: quitado {motivo} ({hasta - desde:.2f} s en el segundo {desde:.1f})")
        nuevos = []
        for trozo in trozos:
            if trozo[0] == g and trozo[1] < desde < trozo[2]:
                nuevos.append([g, trozo[1], desde] + trozo[3:])
                if hasta < trozo[2]:
                    nuevos.append([g, hasta, trozo[2]] + trozo[3:6] + [motivo.startswith("«eeeh»")])
            else:
                nuevos.append(trozo)
        trozos = nuevos

    salida, inicios, posicion = bytearray(), [], 0.0
    fundido = int(0.012 * FM_VOZ)  # 12 ms de fundido en cada corte, sin chasquidos
    for n, (g, ini, fin, diap, _, _, _) in enumerate(trozos):
        if len(inicios) <= diap:
            inicios.append(posicion)
        muestras = fuentes[g]
        desde = max(0, int(ini * FM_VOZ)) * 2
        hasta = min(len(muestras), int(fin * FM_VOZ) * 2)
        trozo = array("h", muestras[desde:hasta])
        for i in range(min(fundido, len(trozo) // 2)):
            f = i / fundido
            trozo[i] = int(trozo[i] * f)
            trozo[-1 - i] = int(trozo[-1 - i] * f)
        salida += trozo.tobytes()
        posicion += len(trozo) / FM_VOZ
        if n + 1 < len(trozos):
            siguiente = trozos[n + 1]
            if siguiente[3] != diap:
                hueco = PAUSA_DIAPOSITIVA
            elif siguiente[6]:
                hueco = 0.0
            elif siguiente[0] == g:
                hueco = min(PAUSA_FRASE, max(0.04, siguiente[1] - fin))
            else:
                hueco = PAUSA_FRASE
            salida += bytes(int(hueco * FM_VOZ) * 2)
            posicion += hueco
    return limpiar_voz(salida, tarjeta.get("limpieza") == "fuerte"), inicios, posicion


def preparar_voz(tarjeta):
    """Monta y limpia la pista de voz. Devuelve (archivo, inicio de cada diapositiva, duración)."""
    textos = transcripciones(tarjeta)
    if textos and all(d.get("dice") for d in tarjeta["diapositivas"]):
        resultado = preparar_voz_con_texto(tarjeta, textos)
        if resultado:
            return resultado
    # Se colocan todas las grabaciones en una línea de tiempo común; el paso de
    # una grabación a otra cuenta como una pausa larga (buen sitio para cortar).
    tramos, origen, desplazamiento = [], {}, 0.0
    for archivo in archivos_de_voz(tarjeta):
        muestras = pcm(archivo)
        propios = tramos_con_voz(muestras)
        for a, b in propios:
            tramo = (desplazamiento + a, desplazamiento + b)
            tramos.append(tramo)
            origen[tramo] = (a, b, muestras)  # tiempos dentro de su grabación
        if propios:
            desplazamiento += propios[-1][1] + 2.0
    grupos = [[origen[t] for t in grupo] for grupo in repartir(tramos, tarjeta["diapositivas"])]
    usados = sum(len(g) for g in grupos)
    if usados < len(tramos):
        print(f"   ✂️  {tarjeta['nombre']}: {len(tramos) - usados} titubeo(s) quitado(s)")

    # Nueva pista: cada tramo con su margen y pausas cortas y regulares
    salida, inicios, posicion = bytearray(), [], 0.0
    for g, grupo in enumerate(grupos):
        inicios.append(posicion)
        for j, (a, b, muestras) in enumerate(grupo):
            desde = max(0, int((a - MARGEN_TRAMO[0]) * FM_VOZ)) * 2
            hasta = min(len(muestras), int((b + MARGEN_TRAMO[1]) * FM_VOZ) * 2)
            salida += muestras[desde:hasta]
            posicion += (hasta - desde) / 2 / FM_VOZ
            if j < len(grupo) - 1:
                siguiente = grupo[j + 1][0]
                hueco = min(PAUSA_FRASE, max(0.0, siguiente - b - sum(MARGEN_TRAMO)))
                if grupo[j + 1][2] is not muestras:  # cambio de grabación
                    hueco = PAUSA_FRASE
            elif g < len(grupos) - 1:
                hueco = PAUSA_DIAPOSITIVA
            else:
                hueco = 0.0
            salida += bytes(int(hueco * FM_VOZ) * 2)
            posicion += hueco

    return limpiar_voz(salida, tarjeta.get("limpieza") == "fuerte"), inicios, posicion


def limpiar_voz(salida, fuerte=False):
    """Aplica la limpieza de voz a la pista montada y la guarda en un archivo temporal."""
    crudo = CONTENIDO / ".voz-cruda.raw"
    limpio = CONTENIDO / ".voz-limpia.wav"
    crudo.write_bytes(bytes(salida))
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-f", "s16le", "-ar", str(FM_VOZ), "-ac", "1", "-i", str(crudo),
                    "-af", (LIMPIEZA_FUERTE if fuerte else "") + LIMPIEZA_VOZ, "-ar", str(FM_VOZ), "-ac", "2", str(limpio)], check=True)
    crudo.unlink()
    return limpio


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
        transcripcion = archivo.with_name(archivo.name + ".json")
        if transcripcion.exists():
            h.update(transcripcion.read_bytes())
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

    # Borra los reels que ya no están en tarjetas.yaml (las versiones -tiktok son de gancho_tiktok.py).
    for sobrante in CONTENIDO.glob("reel-*.mp4"):
        if sobrante.name not in nuevas and not sobrante.stem.endswith("-tiktok"):
            sobrante.unlink()
            print(f"🗑️  {sobrante.name}")
    HUELLAS.write_text(json.dumps(nuevas, indent=2) + "\n")


if __name__ == "__main__":
    main()
