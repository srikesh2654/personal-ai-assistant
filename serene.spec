# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SERENE — builds a onedir app (dist/SERENE/SERENE.exe).

Run:  .venv\\Scripts\\python.exe -m PyInstaller serene.spec --noconfirm

Notes:
- onedir (not onefile): torch/transformers make onefile huge & slow to start.
- The exe still needs Postgres, Ollama, Chrome and a .env next to it at runtime.
- console=True for now so first-run errors are visible; flip to False later.
"""
from PyInstaller.utils.hooks import collect_all

# Bundle the GUI's HTML, and any package that ships data/binaries PyInstaller
# can't infer on its own.
datas = [("serene/ui/index.html", "serene/ui")]
binaries = []
hiddenimports = ["ollama", "psycopg", "pgvector", "dotenv", "uiautomation",
                 "comtypes", "spotipy", "win32timezone"]

# collect_all pulls in code + data + dynamic libs for packages that are hard to
# trace statically (models, native drivers, namespace packages).
for pkg in ["sentence_transformers", "transformers", "tokenizers",
            "huggingface_hub", "safetensors", "torch", "playwright",
            "webview", "groq", "google.genai", "comtypes", "uiautomation",
            "sklearn", "scipy"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h


a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SERENE",
    console=False,           # windowed app — no console window
    disable_windowed_traceback=False,
    icon="icon.ico",
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="SERENE",
)
