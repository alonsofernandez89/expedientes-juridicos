# expedientes-juridicos

App de gestión de expedientes de la Dirección General de Asuntos Jurídicos. Es un único `index.html` (HTML + CSS + JS vanilla, sin build) que lee y escribe en Google Sheets a través de un Web App de Google Apps Script (`SCRIPT_URL`).

## Hojas que usa el backend

| Hoja | Uso |
|---|---|
| `expedientes` | registro principal (expte., iniciador, ingreso, reparto, resp. asig, tema, salio) |
| `agentes` | lista de agentes (columna `nombre`) |
| `programas` | pares programa/expediente para la pestaña Programas |
| `licencias` | licencias por agente (agente, tipo, desde, hasta, obs) |
| `dictamenes` | búsqueda de PDFs en Drive por número de expediente (solo GET) |
| `inventario` | bienes de la oficina (columnas: `bien`, `categoria`, `cantidad`, `estado`, `ubicacion`, `obs`) |
| `pedidos` | pedidos de insumos (columnas: `fecha`, `insumo`, `cantidad`, `solicitante`, `estado`, `obs`) |

> **Para activar la pestaña Inventario**: crear en la planilla dos hojas nuevas llamadas exactamente `inventario` y `pedidos`, con los encabezados de la tabla de arriba en la fila 1 (en minúsculas). El Apps Script debe soportar las acciones `agregar`, `editar` y `eliminar` de forma genérica por nombre de hoja (igual que con las hojas existentes).

## ⚠️ Seguridad del backend (pendiente — requiere cambios en el Apps Script)

El frontend ya escapa todo el HTML que renderiza (mitiga XSS), pero **la protección real tiene que estar en el Apps Script**, porque cualquiera que conozca `SCRIPT_URL` puede llamarlo directo con `fetch`/`curl`, sin pasar por esta página. Hoy ese endpoint permite leer, editar y **borrar** expedientes sin autenticación.

Recomendaciones, de más simple a más robusta:

### 1. Restringir el despliegue del Web App
En el editor de Apps Script → **Implementar → Administrar implementaciones**:
- **Ejecutar como**: vos (el dueño de la planilla).
- **Quién tiene acceso**: idealmente *"Cualquier usuario con cuenta de Google"* o usuarios del dominio, en vez de *"Cualquier usuario"*. Ojo: esto rompe el `fetch` anónimo desde la página; ver opción 3.

### 2. Validar en el servidor (mínimo indispensable)
Aunque se mantenga acceso anónimo, el `doPost` debería validar entrada y limitar acciones. Ejemplo:

```js
var HOJAS_PERMITIDAS = ['expedientes', 'agentes', 'programas', 'licencias'];
var ACCIONES = ['agregar', 'editar', 'eliminar'];

function doPost(e) {
  var body = JSON.parse(e.postData.contents);
  if (HOJAS_PERMITIDAS.indexOf(body.hoja) < 0) return error_('hoja invalida');
  if (ACCIONES.indexOf(body.accion) < 0) return error_('accion invalida');
  // Registrar auditoría: quién/cuándo/qué en una hoja "log"
  registrarLog_(body);
  // ... resto de la lógica
}
```

Además:
- **Auditoría**: agregar una hoja `log` donde cada mutación registre fecha, acción, hoja y datos. Con eso un borrado malicioso o accidental deja rastro.
- **Soft-delete**: en vez de `deleteRow`, marcar la fila con una columna `eliminado` y filtrarla en el GET. Permite recuperar datos.
- **Backups**: activar el historial de versiones de la planilla no alcanza; conviene un trigger diario que copie la planilla (`SpreadsheetApp.getActiveSpreadsheet().copy(...)`).

### 3. Opción más robusta: servir la página desde el propio Apps Script
En lugar de hostear `index.html` en GitHub Pages, servirlo con `HtmlService` desde el mismo proyecto de Apps Script y desplegar con acceso *"Cualquier usuario con cuenta de Google"* (o del dominio). Así:
- El acceso queda protegido por la sesión de Google (sin contraseñas propias).
- `Session.getActiveUser().getEmail()` permite autorizar por lista de emails y registrar quién hizo cada cambio.
- Se elimina el problema de tener la URL del endpoint pública en un repo.

> Nota: poner un "token secreto" en este HTML **no sirve** como protección, porque el repo y la página son públicos — cualquier token del lado del cliente es visible.

## Desarrollo local

Es un archivo estático; basta servirlo con cualquier server local:

```sh
npx http-server . -p 8123
```

Los datos vienen del Apps Script real, así que cuidado con las acciones de escritura al probar.
