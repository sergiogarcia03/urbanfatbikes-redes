# urbanfatbikes-redes

Publicación automática en las redes sociales de urbanfatbikes.
Instagram se publica solo. En TikTok los reels llegan como **borrador** a la app
(TikTok no deja publicar directamente a herramientas propias) y se publican con un toque.

## Cómo funciona

1. Subes las fotos y vídeos a la carpeta [`contenido/`](contenido/).
2. Apuntas cada publicación (fecha, archivos y texto) en [`calendario.yaml`](calendario.yaml).
3. Cada hora, GitHub ejecuta el programa [`publicar.py`](publicar.py), que publica
   lo que ya ha llegado a su fecha.
4. Lo que se publica se apunta en `publicados.json`, para no repetirlo nunca.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `calendario.yaml` | Qué se publica y cuándo. **Es el único archivo que tendrás que tocar a diario.** |
| `contenido/` | Las fotos (.jpg) y vídeos (.mp4) |
| `publicar.py` | El programa que lee el calendario y publica |
| `tarjetas.yaml` y `tarjetas.py` | Las tarjetas de texto con el diseño de la marca: se escriben en `tarjetas.yaml` y el programa crea la imagen |
| `reels.py` | Convierte las tarjetas con `reel: sí` en reels animados (`contenido/reel-<nombre>.mp4`) |
| `musica.py` | Compone por código la música original de los reels (`contenido/musica/`). Se ejecuta a mano |
| `transcribir.py` | Pasa las grabaciones de voz a texto con Whisper (se ejecuta solo en GitHub) |
| `historias.yaml` y `historias.py` | Historias: la de "nuevo post" de cada publicación (1 h después) y las de `historias.yaml` (4 por semana) |
| `adaptar.py` | Adapta las fotos a Instagram (recorte, tamaño, formato) y guarda la copia en `contenido/instagram/` |
| `instagram.py` | La parte que habla con Instagram |
| `renovar_token.py` | Renueva el token de Instagram cada semana para que nunca caduque |
| `tiktok.py` | Sube los reels del calendario a la bandeja de entrada de TikTok y abre un aviso en GitHub con el texto para pegar |
| `herramientas/contactos.html` | Código de la agenda privada de contactos (los datos no están aquí) |
| `CLAUDE.md` | Memoria del proyecto para Claude: normas de la marca, cómo funciona todo y lo pendiente |
| `docs/` | La web de la marca (GitHub Pages): inicio, privacidad, aviso legal y la página de vuelta de TikTok |
| `publicados.json` | Registro automático de lo ya publicado (no editar a mano) |
| `.github/workflows/publicar.yml` | El "reloj" que lanza el programa cada hora en GitHub |

## Configuración (una sola vez)

### 1. Guardar el token de Instagram en GitHub

En GitHub, dentro de este repositorio:
**Settings → Secrets and variables → Actions → New repository secret**

- **Name:** `IG_ACCESS_TOKEN`
- **Secret:** el token que generaste en Meta for Developers

El token nunca se escribe en ningún archivo del repositorio.

### 2. Dónde están las fotos para Instagram

Instagram no acepta archivos subidos directamente: los descarga desde una
dirección web pública. Hay dos opciones:

- **Repositorio público (lo más sencillo):** Instagram descarga las fotos
  directamente del repositorio. No hay que configurar nada más. El token sigue
  a salvo en los Secrets, pero cualquiera podrá ver el código, el calendario y
  las fotos antes de que se publiquen.
- **Repositorio privado:** hay que subir las fotos a un alojamiento público
  (por ejemplo Cloudflare R2) y guardar su dirección en
  **Settings → Secrets and variables → Actions → Variables** con el nombre
  `MEDIA_BASE_URL`.

### 3. Comprobar que todo funciona

En la pestaña **Actions → Publicar en redes → Run workflow**, elige:

- `comprobar`: prueba el token. Debe responder `✅ Conectado a Instagram como @urbanfatbikes`.
- `simular`: revisa el calendario y dice qué publicaría, **sin publicar nada**.
- `publicar`: publica de verdad lo que toque.

### 4. La web (GitHub Pages)

**Settings → Pages → Build and deployment → Source: Deploy from a branch →
Branch: `main`, carpeta `/docs` → Save.** La web queda en
`https://sergiogarcia03.github.io/urbanfatbikes-redes/`.

### 5. TikTok

1. En [TikTok for Developers](https://developers.tiktok.com/) crea una app con
   **Login Kit** y **Content Posting API** (permisos `user.info.basic` y
   `video.upload`, sin «Direct Post»). Dirección de vuelta (Redirect URI):
   `https://sergiogarcia03.github.io/urbanfatbikes-redes/tiktok/`.
2. Guarda en los Secrets `TIKTOK_CLIENT_KEY` y `TIKTOK_CLIENT_SECRET`, y un
   token de GitHub (fine-grained, solo este repositorio, permiso *Secrets: Read
   and write*) como `GH_PAT`.
3. **Actions → Conectar TikTok → Run workflow → `enlace`**: abre el enlace del
   resumen y acepta. La web te da un código: pégalo con el modo `conectar`.

A partir de ahí, cada reel del calendario llega a la bandeja de TikTok a su hora
y GitHub abre un aviso (issue) con el texto. Opciones en `calendario.yaml`:
`tiktok: no` (no subirlo), `texto_tiktok:` (otro texto) y `fecha_tiktok:`
(otra hora). Si existe `contenido/<reel>-tiktok.mp4`, se sube ese vídeo.

## Cosas a tener en cuenta

- **El token caduca a los 60 días**, pero el workflow «Renovar token de Instagram»
  lo renueva solo cada lunes (necesita el Secret `GH_PAT`, ver TikTok). Si alguna
  vez llega a caducar, genera uno nuevo en Meta for Developers y sustitúyelo en
  el Secret `IG_ACCESS_TOKEN`.
- Instagram permite como máximo unas 50 publicaciones por API cada 24 horas.
- Las fotos pueden ser JPG, PNG, WEBP o HEIC (iPhone). Al subirlas, GitHub crea
  sola una copia adaptada a Instagram en `contenido/instagram/`: la recorta por
  el centro si es demasiado alargada, la reduce si es muy grande y le quita los
  datos ocultos (como la ubicación GPS). Mira esa copia para ver cómo quedará.
- **Ojo:** el repositorio es público y las fotos originales de `contenido/`
  conservan sus datos ocultos. Desactiva la ubicación en la cámara del móvil
  antes de hacer fotos que vayas a subir.
- Los reels tienen que ser **MP4** o **MOV**.
- **Voz en los reels:** graba el guion con la app de notas de voz (en uno o
  varios audios) y mándalo. Los audios van a `contenido/voz/` y a la tarjeta en
  `tarjetas.yaml` (`voz: [audio-1, audio-2]`, con la frase de cada diapositiva
  en `dice`). Al subir un audio, el workflow «Transcribir voz» lo pasa a texto
  palabra a palabra con Whisper (`contenido/voz/<audio>.json`). Con eso el
  programa compara lo dicho con el guion y quita lo que sobra (lo dicho antes
  de empezar, repeticiones, arranques en falso, muletillas, «eeeh», vocales
  alargadas y pausas largas a mitad de frase); si una frase se
  repite, se queda la última toma. Después limpia la voz (ruido, golpes, eses,
  volumen), acorta las pausas y baja la música mientras se habla.
  Opciones de la tarjeta: `quitar: {audio: [[inicio, fin]]}` corta tramos a
  mano (en segundos) y `limpieza: fuerte` quita más ruido de fondo (RNNoise,
  modelo en `contenido/voz/quitar-ruido.rnnn`; solo quita ruido, no cambia la voz).
- Las horas del calendario son **hora de España**.
- Horarios de más actividad en España: **reels a las 19:00**, fotos y carruseles
  a las 13:30 (máximo 5 hashtags por publicación), historias extra martes y jueves a las 21:00 y fines de semana a
  las 12:30. Cada publicación lleva su historia "nuevo post" una hora después.
- Una publicación con `borrador: sí` no se publica hasta que se quita esa línea.
- Si la fecha de una publicación pasó hace más de 24 horas sin publicarse
  (por ejemplo, porque el calendario se aprobó tarde), no sale sola: hay que
  ponerle una fecha nueva. Así nunca salen varias publicaciones atrasadas de golpe.
- Todo el contenido debe ser real o diseño propio: no publicamos imágenes
  realistas hechas con IA.
