#!/usr/bin/env python3
"""
Busca una foto para cada producto de data/precios.json usando su código de barras (EAN)
y guarda el resultado en data/imagenes.json ({ean: url}).

Fuentes, en orden: Open Food Facts y los catálogos online de Carrefour, Vea y ChangoMás.
Solo guarda el link a la foto, no la descarga. Lo ya buscado queda en caché y no se repite.

Uso:
    python buscar_imagenes.py                 # busca las que faltan (hasta 45 minutos)
    python buscar_imagenes.py --minutos 5     # corrida corta
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).parent / "data"
HEADERS = {
    "User-Agent": "PreciosMadryn/1.0 (comparador de precios de Puerto Madryn)",
    "Accept": "application/json",
}
OFF = "https://world.openfoodfacts.org/api/v2/product/{ean}.json?fields=image_front_small_url,image_front_url"
TIENDAS = [
    "https://www.carrefour.com.ar",
    "https://www.vea.com.ar",
    "https://www.masonline.com.ar",
]


def pedir_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except Exception:
        return None


def achicar_vtex(url):
    # Las tiendas VTEX permiten pedir la foto en otro tamaño: .../ids/123456/x.jpg -> .../ids/123456-200-200/x.jpg
    return re.sub(r"/ids/(\d+)(-\d+-\d+)?/", r"/ids/\1-200-200/", url, count=1)


def buscar(ean):
    d = pedir_json(OFF.format(ean=ean))
    if d and d.get("status") == 1:
        p = d.get("product", {})
        url = p.get("image_front_small_url") or p.get("image_front_url")
        if url:
            return url
    for tienda in TIENDAS:
        q = urllib.parse.quote(f"alternateIds_Ean:{ean}")
        d = pedir_json(f"{tienda}/api/catalog_system/pub/products/search?fq={q}")
        try:
            return achicar_vtex(d[0]["items"][0]["images"][0]["imageUrl"])
        except (TypeError, LookupError, KeyError):
            continue
    return ""


def guardar(cache, ruta):
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    tmp.replace(ruta)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutos", type=float, default=45)
    ap.add_argument("--hilos", type=int, default=8)
    args = ap.parse_args()

    productos = json.loads((BASE / "precios.json").read_text(encoding="utf-8"))["productos"]
    ruta = BASE / "imagenes.json"
    cache = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}

    # Primero los productos que están en más supermercados.
    pendientes = sorted(
        (p for p in productos if p["ean"] and re.fullmatch(r"\d{8,14}", p["id"]) and p["id"] not in cache),
        key=lambda p: -len(p["precios"]),
    )
    eans = list(dict.fromkeys(p["id"] for p in pendientes))
    print(f"{len(cache)} en caché, {len(eans)} por buscar")

    fin = time.time() + args.minutos * 60
    hechos = encontrados = 0
    with ThreadPoolExecutor(args.hilos) as pool:
        it = iter(eans)
        futuros = {pool.submit(buscar, e): e for e in [next(it) for _ in range(min(args.hilos * 2, len(eans)))]}
        while futuros:
            for f in as_completed(list(futuros)):
                ean = futuros.pop(f)
                cache[ean] = f.result()
                hechos += 1
                encontrados += bool(cache[ean])
                if hechos % 250 == 0:
                    guardar(cache, ruta)
                    print(f"  {hechos} buscados, {encontrados} con foto")
                if time.time() < fin:
                    siguiente = next(it, None)
                    if siguiente:
                        futuros[pool.submit(buscar, siguiente)] = siguiente
                break
    guardar(cache, ruta)
    print(f"Listo: {hechos} buscados ahora, {encontrados} con foto. Total en caché: {len(cache)}")


if __name__ == "__main__":
    main()
