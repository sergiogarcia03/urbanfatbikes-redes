"""Transcribe las grabaciones de voz palabra a palabra, con su tiempo exacto.

Para cada audio de contenido/voz/ sin transcripción, crea contenido/voz/<audio>.json
con cada palabra y el segundo en que empieza y termina. reels.py lo usa para
quitar titubeos, repeticiones y muletillas comparando lo dicho con el guion.

Usa Whisper (faster-whisper), un reconocedor de voz libre que funciona en el
propio ordenador. Se ejecuta en GitHub Actions (workflow "Transcribir voz"),
porque necesita descargar el modelo la primera vez.

Uso:
  pip install faster-whisper
  python transcribir.py
"""

import json
from pathlib import Path

VOZ = Path(__file__).parent / "contenido" / "voz"
EXTENSIONES = {".aac", ".m4a", ".mp3", ".wav", ".ogg", ".opus", ".mp4", ".mov", ".amr", ".3gp"}
# Un texto de ejemplo con titubeos anima a Whisper a transcribirlos tal cual,
# en lugar de "limpiarlos", que es justo lo que necesitamos para poder quitarlos.
PISTA = "Eh... pues, mmm, la la bici, o sea, esto es, eh, una fat- fatbike."


def main():
    pendientes = [a for a in sorted(VOZ.glob("*")) if a.suffix.lower() in EXTENSIONES
                  and not a.with_name(a.name + ".json").exists()]
    if not pendientes:
        print("No hay grabaciones nuevas que transcribir")
        return
    from faster_whisper import WhisperModel

    modelo = WhisperModel("small", device="cpu", compute_type="int8")
    for audio in pendientes:
        segmentos, _ = modelo.transcribe(
            str(audio), language="es", word_timestamps=True, beam_size=5,
            initial_prompt=PISTA, condition_on_previous_text=False, vad_filter=False)
        palabras = [{"palabra": p.word.strip(), "inicio": round(p.start, 3), "fin": round(p.end, 3),
                     "confianza": round(p.probability, 3)}
                    for s in segmentos for p in (s.words or []) if p.word.strip()]
        destino = audio.with_name(audio.name + ".json")
        destino.write_text(json.dumps({"audio": audio.name, "palabras": palabras},
                                      indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"✅ {audio.name}: " + " ".join(p["palabra"] for p in palabras))


if __name__ == "__main__":
    main()
