# expedientes-juridicos

App de gestión de expedientes de la Dirección General de Asuntos Jurídicos. Es un único `index.html` (HTML + CSS + JS vanilla, sin build) que lee y escribe en Google Sheets a través de un Web App de Google Apps Script (`SCRIPT_URL`).

## Hojas que usa el backend

| Hoja | Uso |
|---|---|
| `expedientes` | registro principal (expte., iniciador, ingreso, reparto, resp. asig, tema, salio) |
| `agentes` | lista de agentes (columnas: `nombre`, `cumple_mes`, `cumple_dia` — mes y dia de cumpleaños en columnas numericas separadas, **no** una sola columna de fecha: Sheets reconoce texto tipo "05-03" como fecha y lo reinterpreta segun el idioma de la planilla, invirtiendo dia y mes; y `clave_hash` — hash SHA-256 de la contraseña de cada agente para "Mi Panel", ver abajo) |
| `programas` | pares programa/expediente para la pestaña Programas |
| `licencias` | licencias por agente (agente, tipo, desde, hasta, obs) |
| `dictamenes` | búsqueda de PDFs en Drive por número de expediente (solo GET) |
| `inventario` | bienes de la oficina (columnas: `bien`, `categoria`, `cantidad`, `estado`, `ubicacion`, `obs`) |
| `pedidos` | pedidos de insumos (columnas: `fecha`, `insumo`, `cantidad`, `solicitante`, `estado`, `obs`) |

> **Para activar la pestaña Inventario**: crear en la planilla dos hojas nuevas llamadas exactamente `inventario` y `pedidos`, con los encabezados de la tabla de arriba en la fila 1 (en minúsculas). El Apps Script debe soportar las acciones `agregar`, `editar` y `eliminar` de forma genérica por nombre de hoja (igual que con las hojas existentes).

### Pestaña "Mi Panel" (rendimiento por agente)

Control personal de expedientes de cada agente: elige su nombre en un selector (sin contraseña, para acceso rápido; la elección se recuerda en `localStorage` bajo la clave `panel-agente`). Es una vista enfocada en gestionar los expedientes propios, sin gamificación ni analítica:

- Encabezado con su nombre y estado (total, en la Dirección, resueltos).
- Métricas de control: mis expedientes, en la Dirección, resueltos y cuántos llevan +90 días sin resolver.
- Lista de sus expedientes con **buscador** (número, tema o iniciador) y filtros (Todos / En la Dirección / Resueltos), con acciones de consulta en el portal y ver dictámenes.
- **Plazo para dictaminar**: cada expediente en la Dirección muestra su fecha de vencimiento y los días hábiles restantes (chip verde / ámbar "por vencer" / rojo "vencido"). Son 20 días hábiles contados desde el día siguiente al ingreso, excluyendo fines de semana y feriados nacionales + provinciales de Entre Ríos (usa el mismo `esFeriado()` que el módulo de Licencias; el plazo `DIAS_DICTAMEN` y los feriados se editan en el código). Las métricas incluyen "Dictamen por vencer" (≤5 días hábiles) y "Dictamen vencido".

**No requiere hojas ni cambios en el backend** (salvo la contraseña, ver abajo): todo se calcula en el navegador a partir de los datos ya cargados de `expedientes` y `agentes`.

### Contraseña por agente y rol Director

- Cada agente puede tener una **contraseña propia** para ver su panel. La asigna el **Director** desde la pestaña **Agentes** (botón "Asignar/Cambiar clave" en cada fila). Se guarda como **hash SHA-256** en la columna `clave_hash` de la hoja `agentes` (nunca en texto plano).
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
