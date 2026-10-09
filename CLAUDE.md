# urbanfatbikes: memoria del proyecto

Léelo al empezar cualquier sesión. Resume lo que Sergio y Claude han decidido.

## Quién y qué
- **Sergio García Bensusan** (dueño, principiante con la tecnología). Vive en Países Bajos y vuelve a
  España hacia marzo de 2028. Habla español: **responde siempre en español** y con pasos muy concretos.
- **urbanfatbikes**: marca de fatbikes eléctricas legales para España, aún sin empresa ni ventas.
- Modelo: **urbanfatbikes V8**, versión de 250 W (motor trasero en el buje, acelerador limitado),
  con informe **TÜV Rheinland según EN 15194**. Proveedor: Kai Ren (fotos marcadas «ZEROGO»).
  Sergio ya tiene 3 bicis (una dañada en un accidente).
- Quiere que Claude lleve las redes al 100 % y le autoriza a **unir las PR** él mismo.
- Objetivo y plan: `OBJETIVOS.md` (20 bicis vendidas en junio de 2028).
- **Claude decide solo** el contenido y la estrategia de redes (temas, formatos, fechas, qué foto o vídeo
  usar), sin preguntarle cada cosa, teniendo en cuenta al consumidor español, la competencia y la
  actualidad (normativa, noticias, temporada). A Sergio solo se le pide lo que solo él puede hacer
  (grabar voz o vídeo, responder comentarios, mensajes a terceros) y se le informa con un resumen corto.
- **Ciudad de lanzamiento: Valencia** (2028). Orientar parte del contenido a Valencia para que los seguidores
  sean de allí (lo pidió el consejo: medir demanda real, no solo seguidores).
- **Objetivo ahora: que nos conozca gente (alcance).** Priorizar lo que se comparte y se reenvía,
  ganchos en los 3 primeros segundos, reels para descubrir y carruseles para guardar. Sin repetir la
  misma foto en muchas publicaciones.

## Cómo trabajamos: como una agencia de redes
- Sergio pidió que Claude actúe **como una empresa que gestiona sus redes de arriba abajo**:
  plan y horario fijos, lo mejor posible en cada pieza, y **sentido común**.
- **Todo con gancho**: la portada o los 3 primeros segundos dan un motivo para parar
  (pregunta, dato sorprendente, error común). Nada de frases obvias o de relleno: **nunca
  «así es de lado», «así es una…», «aquí tienes…»**. Si un texto suena flojo, se reescribe.
- **Textos de los posts**: la primera línea (lo que se ve antes del «…más», ~125 caracteres) lleva un dato
  concreto (cifra o nombre); **una sola petición** por post: en reels «Mándaselo a quien…» (los envíos dan
  alcance), en carruseles «Guárdalo», o una pregunta para comentar. Nunca dos a la vez.
- Revisar antes de programar: ganchos, faltas, datos contrastados y que la foto esté perfecta.
  **Nada con la bici dañada** (la del accidente) ni retoques que haya que esconder con IA.
- Material del proveedor (fotos/vídeo): **Sergio autorizó usarlo (06/10/2026)**, siempre sin el logo
  «ZEROGO» ni rótulos en inglés (`v8-estudio.webp` ya limpia; vídeo montado con `herramientas/detalles_v8.py`).
- Ante una duda de verdad (algo que afecte a la marca, dinero o terceros), preguntar a Sergio: no pasa nada.

## Normas de la marca (siempre)
- Tono profesional y de confianza, **solo en español**.
- **Nada de imágenes ni voces realistas hechas con IA** (no quiere la etiqueta de IA).
- Datos de la V8 **solo** del informe TÜV y de la ficha del proveedor. **No inventar precios ni ofertas.**
- Nunca decir «homologada»: «ensayada según la norma europea EN 15194». Más de 250 W / 25 km/h /
  6 km/h sin pedalear = «vehículo de motor (L1e)». Lo legal, solo si está contrastado.
- Sergio quiere **fotos y vídeos reales** (la bici de verdad, sus manos, su cara, la calle), no todo con
  tarjetas de fondo azul. Las tarjetas solo para datos sueltos; en cuanto haya grabaciones reales, van
  primero. Su voz debe ir con su imagen o con su nombre («Soy Sergio, de urbanfatbikes»).
- Música propia compuesta por código (`musica.py`): urban-1/2 (electrónica), inspira-1/2 (de inspiración,
  va creciendo), tranquila-1 (consejos). **Variar**: no repetir la misma pista en reels seguidos.
- Máximo 5 hashtags, siempre #urbanfatbikes; nunca #v8 ni #ouxiv8. Decir «urbanfatbikes V8», nunca «Ouxi».
- Los mensajes que Sergio tenga que mandar a terceros: **en español e inglés**.
- No publicar precios del proveedor ni datos personales en este repositorio: **es público**.

## Cómo funciona (ver README.md)
- Instagram: `publicar.py` cada hora (workflow «Publicar en redes»). Calendario en `calendario.yaml`,
  tarjetas y reels en `tarjetas.yaml` (`tarjetas.py`, `reels.py` con voz editada y música propia),
  historias en `historias.yaml` (+ «nuevo post» automática 1 h después).
- **TikTok es la prioridad (08/10/2026)**: 5 reels por semana, de lunes a viernes a las 19:00 (mar y jue: serie
  «Normas en 10 segundos»). Responder comentarios con vídeo («Responder con vídeo») cuando pregunten por una bici:
  datos solo de la ficha pública de la tienda, sin criticar marcas ni usar sus fotos. En las respuestas TikTok tapa arriba (pegatina
  del comentario) y abajo (comentarios): `texto_y: 720`, `tiempos: 4` (≈2 s por golpe), sin avatar abajo (ver `ek30-v2`). Avisos al móvil: los issues de
  «📲 TikTok: publica…» se asignan a @sergiogarcia03 (app de GitHub); comentarios, con las notificaciones de TikTok e IG.
  **Historias de TikTok**: las de `historias.yaml` (no las de «nuevo post») abren a su hora un aviso «📲 TikTok: sube la
  historia…» con la imagen, porque la API de TikTok no permite subir historias; Sergio la sube a mano.
- Horarios (hora de España): 3 publicaciones/semana (lun/mié/vie). **Mientras haya pocos seguidores (<~500), en el
  feed solo reels** (lo único que llega a quien no nos sigue), todos a las 19:00; los carruseles se convierten en
  reels (`reel: sí` + música en `tarjetas.yaml`). Fotos y carruseles, 13:30. Historias extra: mar y jue 21:00, sáb y dom 12:30.
- Token de Instagram: se renueva solo cada lunes (`renovar_token.py`, secret `GH_PAT`).
- TikTok (`tiktok.py`): los reels llegan como **borrador** a la bandeja de TikTok y GitHub abre un aviso
  (issue) con el texto. App de TikTok en **sandbox**, enviada a revisión el 30/09/2026; cuando la
  aprueben: cambiar `TIKTOK_CLIENT_KEY`/`SECRET` por las de producción y volver a conectar
  (workflow «Conectar TikTok»: enlace de autorización con la clave → código de la web → modo conectar).
  TikTok puede tardar horas en pasar un borrador a la bandeja. TikTok pide **muy visual y gancho fuerte**:
  cada reel lleva versión `-tiktok` con 3 s de fotos de la bici + frase gancho (`gancho_tiktok.py`, `ganchos_tiktok.yaml`);
  **Instagram usa también esa versión** (en `calendario.yaml` van los `reel-*-tiktok.mp4`).
- **Formato de los reels (desde el 07/10/2026): «reels rápidos»** (`reels_rapidos.py` + `reels_rapidos.yaml`):
  **5-7 s (5 golpes)**, un golpe nuevo cada 2 tiempos de la música con zoom, destello y «whoosh», texto que entra palabra
  a palabra, cifras gigantes, ✅/❌. **Muchas imágenes y variadas**: tomas del vídeo del proveedor sin rótulos, foto de
  estudio, escenas dibujadas de «Mi historia» (Holanda, Sergio en fatbike, legal vs trucada, mapa…), iconos animados
  (velocímetro, multa, matrícula, auriculares, cerveza, batería…) y el avatar de Sergio (dibujado, no realista).
  **4 estilos** (neon, aviso, claro, caja) que se alternan para que no todos tengan la misma base. Sergio pidió
  **nada de «presentación»**: como mucho un fondo liso por reel, gancho en el primer golpe y una sola petición al final. Los reels de tarjetas (`reels.py`) quedan solo para los
  que lleven su voz.
- **Web de la marca (la del perfil de Instagram): https://urbanfatbikes.github.io** (organización `urbanfatbikes`,
  repositorio `urbanfatbikes.github.io`). Copia plana de `docs/` (sin carpeta `recursos/`) que **Sergio sube a mano**
  porque Claude aún no tiene permiso en esa organización (falta conectar GitHub desde la cuenta de Claude, que es de
  su padre). Si cambia `docs/`, mandarle los archivos para subirlos.
- Web técnica (GitHub Pages desde `docs/`, la usa la app de TikTok): https://sergiogarcia03.github.io/urbanfatbikes-redes/ con privacidad,
  aviso legal y la página de vuelta de TikTok. Contacto: info.urbanfatbikes@gmail.com.
- Agenda de contactos (privada, en Claude): https://claude.ai/artifact/3e9TFCyMgwTbwW9Eeho5Y9 — su código
  está en `herramientas/contactos.html`; los datos viven en su base de datos, no en el repositorio.

- Skills de Instagram (`/ig-reel`, `/ig-caption`, `/ig-plan`, `/ig-profile`, `/ig-viral`…, 13 en total) en
  `.claude/skills/ig-*`: copia de github.com/Jakeschincariol/instagram-agent-skill (MIT, revisada: no se conecta a
  nada ni pide contraseñas), adaptada al español; leen `.claude/instagram/voice.md`. Solo ayudan a escribir:
  publicar sigue siendo cosa de `publicar.py`. Si chocan con estas normas, mandan estas normas.
- Consejo de ideas de negocio: `/roast <idea>` ejecuta en orden los subagentes de `.claude/agents/`
  (creyente → esceptico → inversionista → juez); el juez guarda el veredicto en `veredictos.md` (público).

## Rutina
- Cada miércoles (tarea programada) se prepara la primera semana sin contenido, se comprueba todo con
  `publicar.py --modo simular`, se une la PR y se mandan vistas previas y guiones de voz.
- Informes privados (no están en el repositorio): «Estrategia redes fatbikes España» y
  «Modelo de negocio fatbikes España».

## Pendiente
- Respuesta de TikTok a la revisión de la app.
- 11/01/2027: preguntas a proveedores (importador UE, precios por cantidad, recambios, sin marca Ouxi).
- Con unos 100 seguidores: pedir el permiso de estadísticas de Instagram para ajustar horarios.
- Lista de fundadores en la web (ene–mar 2027), gratis y sin cobrar nada hasta tener empresa.
