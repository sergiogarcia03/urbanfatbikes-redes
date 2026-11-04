"""Guarda publicados.json en GitHub sin perder nada aunque otra ejecución haya subido antes.

Si el push choca, junta el registro de GitHub con el de esta ejecución (lo de las dos)
y lo vuelve a intentar. Lo usa el último paso de «Publicar en redes».
"""

import json
import subprocess
import sys
import time

ARCHIVO = "publicados.json"


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def juntar(base, nuevo):
    for clave, valor in nuevo.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            juntar(base[clave], valor)
        else:
            base.setdefault(clave, valor)
    return base


def main():
    mio = json.load(open(ARCHIVO, encoding="utf-8"))
    for intento in range(5):
        git("fetch", "-q", "origin", "main")
        remoto = json.loads(git("show", f"origin/main:{ARCHIVO}").stdout)
        junto = juntar(remoto, mio)
        if junto == json.loads(git("show", f"origin/main:{ARCHIVO}").stdout):
            print("Nada nuevo que guardar.")
            return
        git("reset", "-q", "--mixed", "origin/main")  # deja los archivos; solo mueve la rama
        with open(ARCHIVO, "w", encoding="utf-8") as f:
            f.write(json.dumps(junto, indent=2, ensure_ascii=False) + "\n")
        git("add", ARCHIVO)
        git("commit", "-q", "-m", "Registrar publicaciones")
        if git("push", "-q", "origin", "HEAD:main", check=False).returncode == 0:
            print("✅ Registro guardado.")
            return
        print(f"El push chocó (intento {intento + 1}); lo junto y vuelvo a probar.")
        time.sleep(5 + 5 * intento)
    sys.exit("❌ No se pudo guardar publicados.json")


if __name__ == "__main__":
    main()
