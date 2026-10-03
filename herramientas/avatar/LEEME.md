# Avatar animado de Sergio («Mi historia»)

Dibujo vectorial hecho con código (SVG fotograma a fotograma), **sin IA**. La boca, la cabeza y los gestos se
mueven con la voz de Sergio.

- `personaje.py`: la cabeza (cara, pelo, casco) y el movimiento a partir del audio.
- `cuerpo_entero.py`: el cuerpo con articulaciones (sudadera, pantalón, zapatillas).
- `historia.py`: las 7 escenas del vídeo y el montaje (guion en `guion-mi-historia.md`).

Uso (desde esta carpeta; necesita `pip install cairosvg numpy pillow imageio-ffmpeg` y la fuente Montserrat instalada):

```
python historia.py video mi-historia.mp4 <voz.wav o -> 60
python historia.py foto bici 1.0        # una imagen de prueba de una escena
```

Cuando llegue la voz: ajustar la duración de cada escena en `ESCENAS` a las frases de la grabación.
