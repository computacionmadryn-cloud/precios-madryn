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

## Publicación

La página está en GitHub Pages: https://computacionmadryn-cloud.github.io/precios-madryn/

### Actualización diaria (en una PC en Argentina)

El portal de datos del Gobierno **bloquea las conexiones desde fuera de Argentina**, así que los
servidores de GitHub no pueden bajar los precios. La actualización corre en una PC de Windows en Argentina:

1. Instalar [Python](https://www.python.org/downloads/) (marcar "Add python.exe to PATH") y
   [Git para Windows](https://git-scm.com/download/win).
2. Abrir "Símbolo del sistema" y clonar el repo:
   `git clone https://github.com/computacionmadryn-cloud/precios-madryn C:\precios-madryn`
3. Correr una vez `C:\precios-madryn\actualizar.bat` (la primera vez Git pide iniciar sesión en GitHub).
4. Programarlo todos los días a las 9:
   `schtasks /create /tn "Precios Madryn" /tr "C:\precios-madryn\actualizar.bat" /sc daily /st 09:00`

## Fotos de los productos

`buscar_imagenes.py` busca la foto de cada producto por su código de barras en Open Food Facts y en los
catálogos online de Carrefour, Vea y ChangoMás, y guarda solo los links en `data/imagenes.json`.
Corre solo todos los días en GitHub Actions (workflow "Buscar imágenes"). Los productos sin foto
muestran un ícono de su categoría.

## Publicidades

Los avisos se cargan en `data/publicidades.json` (vacío = no se muestra nada). Cada aviso:

```json
[{ "imagen": "publicidad/panaderia.jpg", "link": "https://wa.me/549280...", "texto": "Panadería X" }]
```

Las imágenes van en la carpeta `publicidad/` (ideal 1200×140 px, en .webp o .jpg). Se muestra uno arriba
de la lista y otro cada 10 productos, en orden aleatorio.
