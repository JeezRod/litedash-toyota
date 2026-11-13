#!/usr/bin/env python3
"""Arma el paquete de un auto (zip) para el catálogo o para ir dentro de la app (assets/).

Entrada: una carpeta con los cuadros del giro ya renderizados, gris neutro (ver docs/ARCHITECTURE.md):
  00.png, 01.png ... (el auto)  y  00-pintura.png, 01-pintura.png ... (máscara: blanco = pintura)
Opcionales por cuadro: NN-sombra y NN-reflejo (si están, hay que dar --floor X,Y,W,H en anchos del auto).
Acepta png/webp/jpg. Salida: <id>.zip con auto.json y giro/NN*.webp, y su SHA-256.

Uso: tools/make-car-package.py FRAMES_DIR --id prius-c-2014 --name "Prius c" --make Toyota --year 2014 \
       --author "..." --license "CC-BY-4.0" --source URL --out app/src/main/assets/prius-c-2014.zip
"""
import argparse, hashlib, io, json, sys, zipfile
from pathlib import Path
from PIL import Image

EXTS = (".png", ".webp", ".jpg", ".jpeg")


def find(d: Path, stem: str):
    for e in EXTS:
        if (d / (stem + e)).exists():
            return d / (stem + e)
    return None


def webp(img: Image.Image, lossless: bool) -> bytes:
    b = io.BytesIO()
    img.save(b, "WEBP", lossless=True) if lossless else img.save(b, "WEBP", quality=88, method=6)
    return b.getvalue()


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("frames"); a.add_argument("--id", required=True); a.add_argument("--name", required=True)
    a.add_argument("--make", required=True); a.add_argument("--year", type=int, required=True)
    a.add_argument("--author", required=True); a.add_argument("--license", required=True); a.add_argument("--source", default="")
    a.add_argument("--gray", type=float, help="brillo medio de la pintura gris (0-1); por defecto se mide con la máscara")
    a.add_argument("--floor", help="X,Y,W,H de la sombra/reflejo en anchos del auto (si hay -sombra/-reflejo)")
    a.add_argument("--out", required=True)
    o = a.parse_args()

    d = Path(o.frames)
    n = 0
    while find(d, "%02d" % n): n += 1
    if n < 8: sys.exit(f"Solo {n} cuadros (00, 01...): el giro necesita varios (el catálogo usa 24).")
    extra = [p.stem for p in d.iterdir() if p.suffix.lower() in EXTS and p.stem[:2].isdigit() and p.stem[:2] >= "%02d" % n and "-" not in p.stem[:2]]
    if extra: sys.exit(f"Cuadros fuera de secuencia: {extra[:3]}")

    files, size, grays, floors = {}, None, [], False
    for i in range(n):
        k = "%02d" % i
        base = Image.open(find(d, k)).convert("RGBA")
        mask = find(d, k + "-pintura")
        if not mask: sys.exit(f"Falta la máscara {k}-pintura")
        m = Image.open(mask).convert("L")
        if size is None: size = base.size
        if base.size != size or m.size != size: sys.exit(f"El cuadro {k} no mide {size[0]}x{size[1]} (todos iguales, y la máscara también)")
        files[f"giro/{k}.webp"] = webp(base, False)
        files[f"giro/{k}-pintura.webp"] = webp(m, True)
        for suf in ("sombra", "reflejo"):
            f = find(d, f"{k}-{suf}")
            if f: floors = True; files[f"giro/{k}-{suf}.webp"] = webp(Image.open(f).convert("RGBA"), False)
        # Brillo de la pintura: luminancia media de los píxeles que la máscara marca como pintura.
        lum, mk = base.convert("L").getdata(), m.getdata()
        sel = [l for l, v in zip(lum, mk) if v > 127]
        if sel: grays.append(sum(sel) / len(sel) / 255)
    gray = o.gray if o.gray is not None else (sum(grays) / len(grays) if grays else 0.45)

    info = {"id": o.id, "nombre": o.name, "marca": o.make, "anio": o.year, "gris": round(gray, 3), "giro": n,
            "autor": o.author, "fuente": o.source, "licencia": o.license}
    if floors:
        if not o.floor: sys.exit("Hay -sombra/-reflejo: da --floor X,Y,W,H (o quítalos)")
        box = [float(v) for v in o.floor.split(",")]
        if len(box) != 4: sys.exit("--floor son 4 números")
        info["piso"] = {f"giro/{'%02d' % i}": box for i in range(n)}

    out = Path(o.out); out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:  # los webp ya vienen comprimidos
        z.writestr("auto.json", json.dumps(info, ensure_ascii=False, indent=1))
        z.writestr("LICENCIA.txt", f"{o.name} ({o.make}, {o.year})\nAutor: {o.author}\nLicencia: {o.license}\nFuente: {o.source}\n")
        for name, data in files.items(): z.writestr(name, data)
    h = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{out}: {n} cuadros de {size[0]}x{size[1]}, gris {gray:.3f}, {out.stat().st_size/1e6:.1f} MB\nsha256 {h}")


main()
