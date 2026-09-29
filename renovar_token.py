"""Renueva el token de Instagram antes de que caduque (dura 60 días).

Instagram deja renovar un token de larga duración si tiene más de 24 horas y
todavía no ha caducado; el nuevo vuelve a durar 60 días. Se ejecuta cada semana
(ver .github/workflows/renovar-token.yml) y guarda el token nuevo en el secret
IG_ACCESS_TOKEN con el GH_PAT (token de GitHub con permiso para cambiar Secrets).

Uso:
  python renovar_token.py
"""

import os
import subprocess
import sys

import requests

URL = "https://graph.instagram.com/refresh_access_token"


def main():
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("Falta el secret IG_ACCESS_TOKEN.")
    token_github, repo = os.environ.get("GH_PAT"), os.environ.get("GITHUB_REPOSITORY")
    if not token_github or not repo:
        sys.exit("Falta el secret GH_PAT: sin él no se puede guardar el token nuevo (ver README).")

    try:
        datos = requests.get(URL, params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60).json()
    except (requests.RequestException, ValueError) as error:
        sys.exit(f"❌ No se pudo conectar con Instagram ({type(error).__name__})")
    nuevo = datos.get("access_token")
    if not nuevo:
        error = datos.get("error") or {}
        sys.exit(f"❌ Instagram no renovó el token: {error.get('message') or datos}")
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{nuevo}")

    resultado = subprocess.run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", repo],
                               input=nuevo, text=True, capture_output=True,
                               env={**os.environ, "GH_TOKEN": token_github})
    if resultado.returncode != 0:
        sys.exit(f"❌ No se pudo guardar el token en GitHub: {resultado.stderr.strip()}")
    dias = int(datos.get("expires_in", 0)) // 86400
    print(f"✅ Token de Instagram renovado: vale otros {dias} días.")


if __name__ == "__main__":
    main()
