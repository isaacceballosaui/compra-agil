# App Compra Ágil · Construcción (RM y O'Higgins)

Todo es gratis: GitHub guarda la app y un "robot" (GitHub Actions) descarga cada hora las compras ágiles usando tu ticket, que queda guardado en secreto.

## ⚠️ Primero: pide un ticket nuevo
Pegaste tu ticket en un chat, así que ya no es seguro. Pide uno nuevo (es gratis y toma 2 minutos): https://www.chilecompra.cl/api/ → «Pide tu ticket» → Clave Única. **Nunca lo escribas en ningún archivo**: solo va en el paso 3.

## Paso 1 · Cuenta y repositorio
1. Crea una cuenta en https://github.com (gratis).
2. Arriba a la derecha: **+ → New repository**. Nombre: `compra-agil`. Marca **Public**. Clic en **Create repository**.

## Paso 2 · Subir los archivos
1. En el repositorio nuevo: **Add file → Upload files**.
2. Arrastra **todo el contenido** de la carpeta `app` (no la carpeta en sí): `index.html`, `styles.css`, `manifest.json`, `icon-192.png`, `icon-512.png`, `actualizar.py`, `LEEME.md` y la carpeta `data`.
3. La carpeta `.github` empieza con punto y el Mac/Windows suele ocultarla. Créala a mano: **Add file → Create new file**, y en el nombre escribe `.github/workflows/actualizar.yml`. Pega el contenido de ese archivo y guarda con **Commit changes**.

## Paso 3 · Guardar tu ticket en secreto
**Settings → Secrets and variables → Actions → New repository secret**
- Name: `MP_TICKET`
- Secret: tu ticket nuevo

Luego, en **Settings → Actions → General → Workflow permissions**, elige **Read and write permissions** y guarda.

## Paso 4 · Primera descarga
Pestaña **Actions → Actualizar compras ágiles → Run workflow**. La primera vez puede tardar entre 10 y 40 minutos porque la API de Mercado Público es lenta. Las siguientes son más rápidas, porque reutiliza lo que ya descargó. Después corre sola cada hora.

## Paso 5 · Publicar la app
**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / `(root)` → Save**.
En unos minutos tendrás la dirección `https://TU-USUARIO.github.io/compra-agil/`.

## Paso 6 · Instalar en el iPhone
1. Abre esa dirección en **Safari** (tiene que ser Safari).
2. Toca **Compartir** (el cuadrado con flecha) → **Agregar a pantalla de inicio** → **Agregar**.
3. Listo: el ícono «Compra Ágil» abre la app en pantalla completa.

## Cómo funciona
- **Datos:** compras ágiles *publicadas* en las regiones 13 (RM) y 6 (O'Higgins), filtradas por palabras de construcción y ordenadas por monto.
- **Visita a terreno:** la API no trae un campo propio para esto. El robot busca en la descripción frases como «visita a terreno», «visita técnica» o «visita obligatoria», e intenta sacar la fecha y la hora. En el detalle se muestra además el texto original, para que lo confirmes.
- **Alertas:** las crea la propia app con tus filtros. Te marca las compras nuevas cada vez que la abres. Todavía no envía notificaciones push.
- **Palabras clave:** puedes editarlas en `actualizar.py` (listas `RUBROS` y `EXCLUIR`) directamente en la web de GitHub.

## Si algo sale mal
- En **Actions**, un ❌ rojo significa que la descarga falló. Ábrelo para ver el motivo: un 401/403 es un problema del ticket, y un 500/504 es la API caída (se reintenta sola en la hora siguiente).
- Si aparecen compras con campos vacíos, abre `data/muestra_api.json` en el repositorio y pásame su contenido (no trae tu ticket) para ajustar la lectura de los campos.
