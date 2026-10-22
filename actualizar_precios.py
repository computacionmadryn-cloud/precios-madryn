#!/usr/bin/env python3
"""
Descarga la base oficial SEPA (Precios Claros) y genera data/precios.json
con los precios de alimentos y bebidas de los supermercados de Puerto Madryn.

Uso:
    python actualizar_precios.py                 # baja el último archivo publicado
    python actualizar_precios.py --zip sepa.zip  # usa un zip ya descargado

Solo usa la biblioteca estándar de Python 3.9+.
"""
import argparse
import csv
import io
import json
import math
import re
import sys
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

CKAN = "https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios"
MADRYN = (-42.7692, -65.0385)  # centro de Puerto Madryn
RADIO_KM = 10

# Cadenas que se incluyen. Se reconocen por bandera, razón social o web (texto normalizado).
CADENAS = {
    "La Anónima": r"\banonima\b|importadora y exportadora de la patagonia",
    "Vea": r"\bvea\b",
    "Carrefour": r"carrefour|\binc s\.?a\b",
    "ChangoMás": r"chango ?mas|\bdorinka\b|masonline",
}
RE_CADENAS = {nombre: re.compile(rx) for nombre, rx in CADENAS.items()}


def cadena_de(comercio):
    texto = normalizar(" ".join(comercio.get(k, "") for k in (
        "comercio_bandera_nombre", "comercio_razon_social", "comercio_bandera_url")))
    return next((nombre for nombre, rx in RE_CADENAS.items() if rx.search(texto)), None)

# Productos que NO son comestibles (SEPA no trae categorías, se filtra por nombre).
NO_COMESTIBLES = [
    "detergente", "lavandina", "suavizante", "jabon", "shampoo", "champu", "acondicionador",
    "desodorante", "antitranspirante", "papel higienico", "rollo de cocina", "servilleta",
    "panal", "toallita", "toalla femenina", "protector diario", "tampon", "afeitar", "maquina de afeitar",
    "pasta dental", "crema dental", "cepillo", "enjuague bucal", "insecticida", "limpiador",
    "desinfectante", "aromatizante", "desengrasante", "cera ", "lustramuebles", "esponja",
    "bolsa de residuo", "bolsas residuo", "pila", "lampara", "encendedor", "fosforo",
    "alimento para perro", "alimento para gato", "perro", "gato", "piedras sanitarias",
    "crema corporal", "crema facial", "protector solar", "tintura", "coloracion", "algodon",
    "hisopo", "preservativo", "quitaesmalte", "talco", "gel fijador", "cotonete", "trapo",
    "rejilla", "escoba", "balde", "film", "papel aluminio", "vela", "carbon", "lavavajilla",
    "jabon en polvo", "quitamanchas", "apresto", "blanqueador", "repelente", "colonia", "perfume",
]

CATEGORIAS = [
    ("Bebidas", ["gaseosa", "agua ", "agua mineral", "jugo", "cerveza", "vino", "fernet", "sidra",
                 "soda", "aperitivo", "energizante", "isotonica", "whisky", "vodka", "gin ", "licor", "espumante"]),
    ("Lácteos", ["leche", "yogur", "queso", "manteca", "crema de leche", "dulce de leche", "postre",
                 "flan", "ricota", "muzzarella", "mozzarella"]),
    ("Carnes y fiambres", ["carne", "pollo", "cerdo", "milanesa", "hamburguesa", "salchicha", "jamon",
                           "salame", "mortadela", "paleta", "chorizo", "bondiola", "pescado", "merluza", "atun"]),
    ("Panadería y galletitas", ["pan ", "pan de", "galletita", "bizcocho", "tostada", "budin", "alfajor",
                                "magdalena", "grisin", "prepizza", "tapa de empanada", "tapas para"]),
    ("Desayuno", ["cafe", "yerba", "te ", "mate cocido", "cacao", "cereal", "azucar", "edulcorante",
                  "mermelada", "miel", "avena"]),
    ("Almacén", ["arroz", "fideo", "harina", "aceite", "vinagre", "sal ", "pure", "lenteja", "poroto",
                 "arveja", "garbanzo", "polenta", "mayonesa", "ketchup", "mostaza", "salsa", "caldo",
                 "sopa", "conserva", "enlatado", "choclo", "durazno en almibar", "gelatina", "bizcochuelo",
                 "levadura", "especia", "oregano", "pimienta"]),
    ("Frutas y verduras", ["papa ", "tomate", "cebolla", "lechuga", "zanahoria", "manzana", "banana",
                           "naranja", "limon", "zapallo", "batata", "fruta", "verdura"]),
    ("Congelados", ["congelad", "helado", "papas fritas", "bastones", "nuggets", "patitas"]),
    ("Snacks y golosinas", ["chocolate", "caramelo", "chicle", "papas", "snack", "mani", "chizito",
                            "palitos", "turron", "golosina", "barra de cereal"]),
]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def patron(claves):
    # Cada clave matchea al inicio de una palabra; si termina en espacio, debe ser la palabra entera.
    partes = [r"\b" + re.escape(c.strip()) + (r"\b" if c.endswith(" ") else "") for c in claves]
    return re.compile("|".join(partes))


RE_NO_COMESTIBLE = patron(NO_COMESTIBLES)
RE_CATEGORIAS = [(cat, patron(claves)) for cat, claves in CATEGORIAS]


def es_comestible(nombre):
    return not RE_NO_COMESTIBLE.search(normalizar(nombre))


def categoria(nombre):
    n = normalizar(nombre)
    for cat, regex in RE_CATEGORIAS:
        if regex.search(n):
            return cat
    return "Otros alimentos"


def distancia_km(lat1, lon1, lat2, lon2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def numero(valor):
    try:
        v = float(str(valor).replace(",", "."))
        return round(v, 2) if v > 0 else None
    except (TypeError, ValueError):
        return None


def leer_csv(zf, sufijo):
    """Lee el CSV (separado por '|') cuyo nombre termina en `sufijo` dentro de un zip."""
    nombre = next((n for n in zf.namelist() if n.lower().endswith(sufijo)), None)
    if not nombre:
        return []
    texto = zf.read(nombre).decode("utf-8-sig", errors="replace")
    filas = []
    for fila in csv.DictReader(io.StringIO(texto), delimiter="|"):
        # El SEPA agrega una línea final tipo "Última actualización: ..." que no es un dato.
        if fila.get("id_comercio") and str(fila["id_comercio"]).strip().isdigit():
            filas.append({k.strip(): (v or "").strip() for k, v in fila.items() if k})
    return filas


def descargar_ultimo_zip(destino):
    print("Consultando el portal de datos abiertos…")
    with urllib.request.urlopen(CKAN, timeout=60) as r:
        paquete = json.load(r)["result"]
    recursos = [x for x in paquete["resources"] if x.get("url", "").lower().endswith(".zip")]
    recursos.sort(key=lambda x: x.get("last_modified") or x.get("created") or "", reverse=True)
    if not recursos:
        sys.exit("No encontré archivos .zip en el dataset SEPA.")
    url = recursos[0]["url"]
    print(f"Descargando {url} (puede pesar varios cientos de MB)…")
    urllib.request.urlretrieve(url, destino)
    return destino


def procesar(zip_path):
    sucursales, productos = {}, {}
    with zipfile.ZipFile(zip_path) as externo:
        internos = [n for n in externo.namelist() if n.lower().endswith(".zip")]
        for nombre in internos:
            try:
                zf = zipfile.ZipFile(io.BytesIO(externo.read(nombre)))
            except zipfile.BadZipFile:
                continue
            procesar_comercio(zf, sucursales, productos)
        if not internos:  # zip "plano" con los CSV adentro
            procesar_comercio(externo, sucursales, productos)
    return sucursales, productos


def procesar_comercio(zf, sucursales, productos):
    comercios = {(c["id_comercio"], c["id_bandera"]): c for c in leer_csv(zf, "comercio.csv")}
    locales = {}
    for s in leer_csv(zf, "sucursales.csv"):
        lat, lon = numero(s.get("sucursales_latitud")), s.get("sucursales_longitud")
        try:
            lon = float(lon)
        except ValueError:
            lon = None
        cerca = lat is not None and lon is not None and distancia_km(lat, lon, *MADRYN) <= RADIO_KM
        com = comercios.get((s["id_comercio"], s["id_bandera"]), {})
        cadena = cadena_de(com)
        if cadena and ("madryn" in normalizar(s.get("sucursales_localidad")) or cerca):
            key = (s["id_comercio"], s["id_bandera"], s["id_sucursal"])
            sid = "-".join(key)
            locales[key] = sid
            sucursales[sid] = {
                "id": sid,
                "cadena": cadena,
                "nombre": s.get("sucursales_nombre", "").title(),
                "direccion": f'{s.get("sucursales_calle", "").title()} {s.get("sucursales_numero", "")}'.strip(),
                "lat": lat, "lon": lon,
                "actualizado": com.get("comercio_ultima_actualizacion", ""),
            }
    if not locales:
        return
    for p in leer_csv(zf, "productos.csv"):
        sid = locales.get((p["id_comercio"], p["id_bandera"], p["id_sucursal"]))
        if not sid or not es_comestible(p.get("productos_descripcion")):
            continue
        lista = numero(p.get("productos_precio_lista"))
        if lista is None:
            continue
        promos = [x for x in (numero(p.get("productos_precio_unitario_promo1")),
                              numero(p.get("productos_precio_unitario_promo2")))
                  if x and x < lista and x > lista * 0.3]
        ean = p.get("productos_ean") == "1"
        pid = p["id_producto"] if ean else f'{p["id_comercio"]}-{p["id_producto"]}'
        prod = productos.setdefault(pid, {
            "id": pid,
            "nombre": p.get("productos_descripcion", "").strip(),
            "marca": p.get("productos_marca", "").title(),
            "presentacion": f'{p.get("productos_cantidad_presentacion", "")} {p.get("productos_unidad_medida_presentacion", "")}'.strip(),
            "categoria": categoria(p.get("productos_descripcion")),
            "ean": ean,
            "precios": {},
        })
        prod["precios"][sid] = [lista, min(promos)] if promos else [lista]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", help="zip SEPA ya descargado")
    ap.add_argument("--salida", default=str(Path(__file__).parent / "data" / "precios.json"))
    args = ap.parse_args()

    zip_path = args.zip or descargar_ultimo_zip("sepa.zip")
    sucursales, productos = procesar(zip_path)
    if not sucursales:
        sys.exit("No encontré sucursales en Puerto Madryn en este archivo.")
    salida = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "fuente": "SEPA - Precios Claros (datos.produccion.gob.ar)",
        "ejemplo": False,
        "sucursales": sorted(sucursales.values(), key=lambda s: (s["cadena"], s["nombre"])),
        "productos": sorted(productos.values(), key=lambda p: p["nombre"]),
    }
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Listo: {len(sucursales)} sucursales y {len(productos)} productos -> {args.salida}")
    for s in salida["sucursales"]:
        print(f'  · {s["cadena"]} — {s["nombre"]} ({s["direccion"]})')
    faltan = sorted(set(CADENAS) - {s["cadena"] for s in salida["sucursales"]})
    if faltan:
        print("  Sin sucursales en Puerto Madryn en este archivo: " + ", ".join(faltan))


if __name__ == "__main__":
    main()
