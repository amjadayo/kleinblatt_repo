#!/usr/bin/env python3
# Datei: make_zip.py
import os, re, sys, zipfile

# 1. Version aus main.py auslesen
MAIN_PY = "main.py"
with open(MAIN_PY, "r") as f:
    content = f.read()
m = re.search(r'^VERSION\s*=\s*"([^"]+)"', content, re.MULTILINE)
if not m:
    print("Fehler: VERSION nicht in main.py gefunden")
    sys.exit(1)
version = m.group(1)

# 2. Pfade definieren
src = "Kleinblatt.app"
dst = f"Kleinblatt-{version}.zip"

# 3. ZIP anlegen
with zipfile.ZipFile(dst, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        for file in files:
            path = os.path.join(root, file)
            # relativ zum übergeordneten Ordner packen, damit .app im ZIP drin bleibt
            arcname = os.path.relpath(path, os.path.dirname(src))
            zf.write(path, arcname)

print(f"✔ Archiv erstellt: {dst}")
