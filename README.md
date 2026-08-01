# expedientes-juridicos

App de gestión de expedientes de la Dirección General de Asuntos Jurídicos. Es un único `index.html` (HTML + CSS + JS vanilla, sin build) que lee y escribe en Google Sheets a través de un Web App de Google Apps Script (`SCRIPT_URL`).

## Hojas que usa el backend

| Hoja | Uso |
|---|---|
| `expedientes` | registro principal (expte., iniciador, ingreso, reparto, resp. asig, tema, salio) |
| `agentes` | lista de agentes (columnas: `nombre`, `cumple_mes`, `cumple_dia` — mes y dia de cumpleaños en columnas numericas separadas, **no** una sola columna de fecha: Sheets reconoce texto tipo "05-03" como fecha y lo reinterpreta segun el idioma de la planilla, invirtiendo dia y mes. **Ademas** estas columnas se guardan como texto (string), no como numero: si la celda tiene formato Fecha, un numero como `5` se coerce al serial de fecha `1900-01-04` y se pierde el mes; guardar `"5"` evita esa coercion y "cura" el formato. La lectura ademas ignora valores fuera de rango (1-12 / 1-31) por si quedo algun valor corrupto de antes; y `clave_hash` — hash SHA-256 de la contraseña de cada agente para "Mi Panel", ver abajo) |
| `programas` | pares programa/expediente para la pestaña Programas. También guarda, en la fila placeholder de cada programa (`expte` vacío), la columna `palabras_clave` (separadas por coma): si el tema de un expediente nuevo menciona alguna, se asigna solo a ese programa. Requiere agregar la columna `palabras_clave` a la hoja. |
| `licencias` | licencias por agente (agente, tipo, desde, hasta, obs) |
| `dictamenes` | búsqueda de PDFs en Drive por número de expediente (solo GET) |
| `inventario` | bienes de la oficina (columnas: `bien`, `categoria`, `cantidad`, `estado`, `ubicacion`, `obs`) |
| `pedidos` | pedidos de insumos (columnas: `fecha`, `insumo`, `cantidad`, `solicitante`, `estado`, `obs`) |
| `log` | auditoría/trazabilidad: una fila por cada alta/edición/baja (columnas: `fecha`, `accion`, `hoja`, `datos`). Solo lectura desde el frontend (botón "🕘 Ver historial" en Registro); la escribe el propio Apps Script en cada `doPost` exitoso. |
| `normativas` | **no es una hoja de Sheets**: `hoja=normativas` en el GET devuelve, del lado del Apps Script, el listado de archivos de una carpeta de Drive con una subcarpeta por categoría (`Programas`, `Contrataciones`, `Dictámenes Fiscalía`, `Legal y Técnica`). Solo lectura (igual que `dictamenes`): subir/editar/borrar un archivo se hace directo en Drive, no desde la app. |

> **Para activar la pestaña Inventario**: crear en la planilla dos hojas nuevas llamadas exactamente `inventario` y `pedidos`, con los encabezados de la tabla de arriba en la fila 1 (en minúsculas). El Apps Script debe soportar las acciones `agregar`, `editar` y `eliminar` de forma genérica por nombre de hoja (igual que con las hojas existentes).

> **Para activar el historial/trazabilidad**: crear una hoja `log` con los encabezados `fecha`, `accion`, `hoja`, `datos` (en minúsculas), y agregar al `doPost` del Apps Script una llamada a `registrarLog_(accion, hoja, datos)` que guarde una fila en esa hoja después de cada alta/edición/baja exitosa. Sin esa hoja, el botón de historial simplemente muestra "todavía no hay historial" (no rompe nada).

> **Para activar la pestaña Normativas**: en Drive, crear una carpeta contenedora y adentro 4 subcarpetas con el nombre **exacto** de cada categoría: `Programas`, `Contrataciones`, `Dictámenes Fiscalía`, `Legal y Técnica`. Los archivos que se suban a cada subcarpeta aparecen automáticamente en esa sub-pestaña de la app (nombre del archivo, fecha de última modificación y link para abrirlo) — no hace falta ni hoja de cálculo ni cargar nada desde la app. Hay que agregar al `doGet` del Apps Script el manejo de `hoja === 'normativas'` (mismo patrón que ya usa `dictamenes` para leer una carpeta de Drive), con el ID de la carpeta contenedora en una constante nueva (`CARPETA_NORMATIVAS`).

### Pestaña "Mi Panel" (rendimiento por agente)

Control personal de expedientes de cada agente: elige su nombre en un selector (sin contraseña, para acceso rápido; la elección se recuerda en `localStorage` bajo la clave `panel-agente`). Es una vista enfocada en gestionar los expedientes propios, sin gamificación ni analítica:

- Encabezado con su nombre y estado (total, en la Dirección, resueltos).
- Métricas de control: mis expedientes, en la Dirección, resueltos y cuántos llevan +90 días sin resolver.
- Lista de sus expedientes con **buscador** (número, tema o iniciador) y filtros (Todos / En la Dirección / Resueltos), con acciones de consulta en el portal y ver dictámenes.
- **Vencimiento para dictaminar (opcional)**: no se calcula automáticamente. Cada agente puede cargar, si quiere, una fecha de vencimiento en cualquiera de sus expedientes en la Dirección (un selector de fecha al lado del expediente); a partir de ahí se muestran los días hábiles restantes (chip verde / ámbar "por vencer" / rojo "vencido"), excluyendo fines de semana y feriados nacionales + provinciales de Entre Ríos (usa el mismo `esFeriado()` que el módulo de Licencias). Un expediente sin vencimiento cargado no cuenta en las métricas "Dictamen por vencer" (≤5 días hábiles) ni "Dictamen vencido". Se guarda en la columna `vencimiento` de la hoja `expedientes`.

**Requiere agregar la columna `vencimiento`** a la hoja `expedientes` (el Apps Script ya soporta `editar` escribiendo solo las columnas enviadas, igual que con `cumple_mes`/`cumple_dia`). El resto de "Mi Panel" no requiere hojas ni cambios en el backend (salvo la contraseña, ver abajo): se calcula en el navegador a partir de los datos ya cargados de `expedientes` y `agentes`.

### Contraseña por agente y rol Director

- Cada agente puede tener una **contraseña propia** para ver su panel. Se la puede fijar/cambiar/quitar **el mismo agente** desde "Mi Panel" (botón "Fijar mi contraseña" / "Cambiar mi contraseña" una vez que ya está viendo su panel desbloqueado), o el **Director** desde la pestaña **Agentes** (botón "Asignar/Cambiar clave" en cada fila). Se guarda como **hash SHA-256** en la columna `clave_hash` de la hoja `agentes` (nunca en texto plano).
- **El Director es `Alonso`** (constante `DIRECTOR` en el código). Se autentica con la **clave maestra** (la misma que ya desbloquea la pestaña Agentes, `CLAVE_HASH`) y con eso accede a **todas las pestañas y a todos los paneles** de los agentes, sin necesidad de la contraseña individual de cada uno.
- En "Mi Panel", al elegir un agente con contraseña asignada se pide la clave; una vez validada, queda desbloqueado por esa sesión (`sessionStorage`). Un agente **sin** `clave_hash` tiene el panel abierto (útil para la carga inicial: el Director va asignando las contraseñas).
- **Requisito de backend**: agregar la columna `clave_hash` a la hoja `agentes`. El Apps Script debe permitir `editar` esa hoja escribiendo solo las columnas enviadas (igual que ya hace con `cumple_mes`/`cumple_dia`).

> ⚠️ **Alcance de seguridad**: esta protección es del lado del cliente (un "candado blando"). Sirve para separar vistas entre agentes, pero alguien con conocimientos técnicos podría eludirla desde el navegador. Los hashes son SHA-256 **sin sal**, así que conviene usar contraseñas no triviales. Para una protección real, la validación debe hacerse en el Apps Script (ver la sección de seguridad del backend más abajo).

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
