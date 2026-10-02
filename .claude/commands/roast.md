---
description: Pasa una idea de negocio por el consejo (creyente → escéptico → inversionista → juez) y guarda el veredicto en veredictos.md
argument-hint: <la idea de negocio>
---

Pasa esta idea de negocio por el consejo de cuatro subagentes, **uno detrás de otro y en este orden**.
Todo en español.

**Idea:** $ARGUMENTS

Si no se ha escrito ninguna idea, pide al usuario que la escriba y no sigas.

1. Lanza el subagente **creyente** (herramienta Agent, `subagent_type: "creyente"`) con la idea.
2. Cuando termine, lanza el subagente **esceptico** con la idea **y la respuesta completa del creyente**.
3. Cuando termine, lanza el subagente **inversionista** con la idea **y las respuestas completas del creyente y del escéptico**.
4. Cuando termine, lanza el subagente **juez** con la idea **y las tres respuestas completas**. El juez guarda el veredicto en `veredictos.md`.

Espera a que cada uno termine antes de lanzar el siguiente (no en paralelo), porque cada uno lee a los anteriores.

Al final, muestra al usuario:
- Un resumen de 2–3 líneas de cada miembro del consejo (la apuesta clave del creyente, el fallo fatal del escéptico y si el inversionista invertiría).
- El veredicto del juez completo: veredicto, mayor riesgo, prueba de 10 minutos y, si procede, qué cambiar.
- Que el veredicto se ha guardado en `veredictos.md`. Recuerda que el repositorio es público.
