"""Compone música original para los reels, sintetizada por código.

No usa inteligencia artificial ni canciones de nadie: el programa genera cada
sonido (bombo, palmas, charles, bajo, acordes y arpegio) con fórmulas y los
coloca en el tiempo como en un secuenciador. Por eso no hay derechos de autor
de terceros.

Se ejecuta a mano (no hace falta en GitHub) y guarda las pistas en
contenido/musica/. Necesita numpy:
  pip install numpy
  python musica.py
"""

import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

RAIZ = Path(__file__).parent
MUSICA = RAIZ / "contenido" / "musica"
FM = 44100  # muestras por segundo

# Notas (número MIDI): La menor
NOTAS = {"A": 57, "B": 59, "C": 60, "D": 62, "E": 64, "F": 65, "G": 67}


def frecuencia(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def paso_bajo(x, corte, taps=255):
    """Filtro que deja pasar los graves (suaviza el sonido)."""
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * corte / FM * n) * np.hamming(taps)
    h /= h.sum()
    return np.convolve(x, h, mode="same")


def paso_alto(x, corte, taps=255):
    return x - paso_bajo(x, corte, taps)


def diente_sierra(f, t, fase=0.0):
    return 2 * ((f * t + fase) % 1.0) - 1


def envolvente(n, ataque, caida):
    t = np.arange(n) / FM
    return np.minimum(1.0, t / max(ataque, 1e-4)) * np.exp(-t / caida)


# --- Instrumentos -----------------------------------------------------------


def bombo():
    n = int(0.45 * FM)
    t = np.arange(n) / FM
    f = 48 + 110 * np.exp(-t / 0.035)
    cuerpo = np.sin(2 * np.pi * np.cumsum(f) / FM) * np.exp(-t / 0.28)
    golpe = np.random.default_rng(1).standard_normal(n) * np.exp(-t / 0.004) * 0.3
    return np.tanh(1.6 * (cuerpo + golpe))


def palmas():
    rng = np.random.default_rng(2)
    n = int(0.3 * FM)
    t = np.arange(n) / FM
    ruido = paso_alto(rng.standard_normal(n), 900)
    env = np.exp(-t / 0.09)
    for retardo in (0.0, 0.011, 0.022):  # varias palmas casi a la vez
        env += np.where(t >= retardo, np.exp(-(t - retardo) / 0.008), 0) * 0.8
    return paso_bajo(ruido * env, 6000) * 0.6


def charles(abierto=False):
    rng = np.random.default_rng(3 if abierto else 4)
    n = int((0.25 if abierto else 0.06) * FM)
    ruido = paso_alto(rng.standard_normal(n), 7000)
    return paso_bajo(ruido, 11000) * envolvente(n, 0.001, 0.08 if abierto else 0.018) * 0.18


def bajo(midi, duracion):
    n = int(duracion * FM)
    t = np.arange(n) / FM
    f = frecuencia(midi)
    onda = diente_sierra(f, t) * 0.6 + np.sin(2 * np.pi * f * t) * 0.6
    return paso_bajo(onda, 420) * envolvente(n, 0.004, duracion * 0.9)


def acorde(notas, duracion, desafinar):
    n = int(duracion * FM)
    t = np.arange(n) / FM
    onda = np.zeros(n)
    for midi in notas:
        for d in (-desafinar, 0, desafinar):
            onda += diente_sierra(frecuencia(midi) * (1 + d), t, fase=abs(d) * 37)
    onda = paso_bajo(onda / (3 * len(notas)), 1500)
    ataque = np.minimum(1.0, t / 0.25)
    final = np.minimum(1.0, (duracion - t) / 0.15)
    return onda * ataque * final


def pulso(midi, duracion):
    n = int(duracion * FM)
    t = np.arange(n) / FM
    f = frecuencia(midi)
    onda = diente_sierra(f, t) * 0.5 + np.sign(np.sin(2 * np.pi * f * t)) * 0.3
    return paso_bajo(onda, 2800) * envolvente(n, 0.002, 0.09)


# --- Composición ------------------------------------------------------------


def colocar(pista, sonido, segundo, volumen=1.0):
    i = int(segundo * FM)
    fin = min(len(pista), i + len(sonido))
    if i < len(pista):
        pista[i:fin] += sonido[: fin - i] * volumen


def componer(tempo, progresion, compases=16, semilla=0):
    """Crea una pista estéreo. progresion = acordes de 4 compases, p. ej. ["Am", "F", "C", "G"]."""
    np.random.seed(semilla)
    negra = 60 / tempo
    compas = 4 * negra
    total = compases * compas + 1.0
    n = int(total * FM)
    ritmo, graves, izq, der = (np.zeros(n) for _ in range(4))
    golpes = []

    s_bombo, s_palmas = bombo(), palmas()
    s_charles, s_abierto = charles(), charles(abierto=True)

    for c in range(compases):
        nombre = progresion[c % len(progresion)]
        raiz = NOTAS[nombre[0]] - (1 if nombre[1:2] == "b" else 0)  # "Bb" = si bemol
        menor = nombre.endswith("m")
        triada = [raiz, raiz + (3 if menor else 4), raiz + 7]
        inicio = c * compas
        intro = c < 1

        # Acordes de fondo (siempre)
        for canal, desafinar in ((izq, 0.004), (der, 0.006)):
            colocar(canal, acorde(triada, compas, desafinar), inicio, 0.7)

        # Arpegio en semicorcheas
        orden = [0, 1, 2, 1, 0, 2, 1, 2] * 2
        for i, k in enumerate(orden):
            nota = triada[k] + 12
            colocar(izq if i % 2 else der, pulso(nota, negra / 4), inicio + i * negra / 4, 0.22 if not intro else 0.16)

        if intro:
            for b in range(4):  # en la intro, solo charles a contratiempo
                colocar(ritmo, s_charles, inicio + b * negra + negra / 2, 0.6)
            continue

        for b in range(4):
            t = inicio + b * negra
            colocar(ritmo, s_bombo, t, 0.7)
            golpes.append(t)
            if b in (1, 3):
                colocar(ritmo, s_palmas, t, 0.7)
            colocar(ritmo, s_charles, t, 0.35)
            colocar(ritmo, s_abierto if b % 2 else s_charles, t + negra / 2, 0.6)
            # Bajo en corcheas, con salto de octava a contratiempo
            colocar(graves, bajo(raiz - 24, negra / 2 * 0.9), t, 0.55)
            colocar(graves, bajo(raiz - 12, negra / 2 * 0.9), t + negra / 2, 0.4)

    # Los acordes "respiran" con el bombo (efecto de música electrónica actual)
    duck = np.ones(n)
    tt = np.arange(int(negra * FM)) / FM
    curva = 1 - 0.55 * np.exp(-tt / 0.11)
    for g in golpes:
        i = int(g * FM)
        fin = min(n, i + len(curva))
        duck[i:fin] = np.minimum(duck[i:fin], curva[: fin - i])

    mezcla_i = ritmo + graves + izq * duck
    mezcla_d = ritmo + graves + der * duck
    estereo = np.stack([mezcla_i, mezcla_d], axis=1)
    estereo = np.tanh(estereo * 0.8)  # compresión suave
    estereo *= 10 ** (-1 / 20) / np.max(np.abs(estereo))  # pico a -1 dB
    subida = np.minimum(1.0, np.arange(n) / (0.3 * FM))[:, None]
    bajada = np.minimum(1.0, (n - np.arange(n)) / (1.0 * FM))[:, None]
    return estereo * subida * bajada


def guardar(audio, nombre):
    MUSICA.mkdir(parents=True, exist_ok=True)
    temporal = MUSICA / f"{nombre}.wav"
    with wave.open(str(temporal), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(FM)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    destino = MUSICA / f"{nombre}.m4a"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(temporal),
                    # Volumen estándar de redes sociales (-14 LUFS)
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100",
                    "-c:a", "aac", "-b:a", "192k", str(destino)], check=True)
    temporal.unlink()
    print(f"✅ musica/{destino.name}")


def main():
    # Dos pistas distintas para no repetir siempre la misma
    guardar(componer(112, ["Am", "F", "C", "G"], semilla=1), "urban-1")
    guardar(componer(118, ["Dm", "Bb", "F", "C"], semilla=2), "urban-2")


if __name__ == "__main__":
    main()
