# Precios Madryn

Página que compara los precios de alimentos y bebidas en los supermercados de Puerto Madryn.

## De dónde salen los precios

De la **base oficial SEPA (Precios Claros)** que publica el Gobierno en
https://datos.produccion.gob.ar/dataset/sepa-precios. Las cadenas grandes (La Anónima, Carrefour,
ChangoMás, etc.) están obligadas a informar ahí todos sus precios, por sucursal, todos los días.
No hace falta "scrapear" las páginas de cada súper.

`actualizar_precios.py`:
1. Baja el último archivo SEPA publicado (un zip grande con un zip por cadena).
2. Se queda solo con las sucursales de **La Anónima, Vea, Carrefour y ChangoMás** en Puerto Madryn
   (por localidad o a menos de 10 km del centro). Las cadenas se cambian en `CADENAS`, al principio del script.
3. Descarta lo que no es comestible (limpieza, perfumería, mascotas…) y clasifica por categoría.
4. Guarda todo en `data/precios.json`, que es lo que lee la página.

Los productos se comparan entre cadenas por código de barras (EAN). Los que no tienen EAN
(pan, fiambre por kilo, etc.) aparecen solo en su cadena.

## Cómo usarlo

```bash
python actualizar_precios.py       # Python 3.9+, sin dependencias
python -m http.server 8000         # y abrir http://localhost:8000
```

Si abrís `index.html` directo (sin servidor) o todavía no existe `data/precios.json`,
la página muestra **datos de ejemplo inventados** con un aviso amarillo.

## Publicarlo gratis con actualización diaria

1. Subir esta carpeta a un repositorio de GitHub.
2. Activar GitHub Pages (Settings → Pages → rama `main`, carpeta raíz).
3. El workflow `.github/workflows/actualizar.yml` corre todos los días, baja precios nuevos y los publica.
