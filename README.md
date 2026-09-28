# urbanfatbikes-redes

Publicación automática en las redes sociales de urbanfatbikes.
De momento funciona con **Instagram**. TikTok vendrá más adelante.

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
| `adaptar.py` | Adapta las fotos a Instagram (recorte, tamaño, formato) y guarda la copia en `contenido/instagram/` |
| `instagram.py` | La parte que habla con Instagram |
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

## Cosas a tener en cuenta

- **El token caduca a los 60 días.** Antes de que caduque, genera uno nuevo en
  Meta for Developers y sustitúyelo en el Secret `IG_ACCESS_TOKEN`.
- Instagram permite como máximo unas 50 publicaciones por API cada 24 horas.
- Las fotos pueden ser JPG, PNG, WEBP o HEIC (iPhone). Al subirlas, GitHub crea
  sola una copia adaptada a Instagram en `contenido/instagram/`: la recorta por
  el centro si es demasiado alargada, la reduce si es muy grande y le quita los
  datos ocultos (como la ubicación GPS). Mira esa copia para ver cómo quedará.
- **Ojo:** el repositorio es público y las fotos originales de `contenido/`
  conservan sus datos ocultos. Desactiva la ubicación en la cámara del móvil
  antes de hacer fotos que vayas a subir.
- Los reels tienen que ser **MP4** o **MOV**.
- Las horas del calendario son **hora de España**.
- Una publicación con `borrador: sí` no se publica hasta que se quita esa línea.
- Si la fecha de una publicación pasó hace más de 24 horas sin publicarse
  (por ejemplo, porque el calendario se aprobó tarde), no sale sola: hay que
  ponerle una fecha nueva. Así nunca salen varias publicaciones atrasadas de golpe.
- Todo el contenido debe ser real o diseño propio: no publicamos imágenes
  realistas hechas con IA.
