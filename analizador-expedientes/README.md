# Analizador de Expedientes Administrativos

Aplicación de escritorio para Windows (funciona también en Linux/macOS) destinada al **análisis y resumen de expedientes administrativos escaneados en PDF**. Todo el procesamiento pesado (OCR, resumen, búsqueda semántica) ocurre **localmente**; el uso de APIs externas (Claude) es opcional, está desactivado por defecto y siempre requiere confirmación expresa.

---

## 1. Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Interfaz (PySide6)                            │
│  Pestañas: Procesamiento · Texto por página · Resúmenes ·        │
│  Cronología · Documentos detectados · Preguntas · Revisión Claude│
└──────────────┬──────────────────────────────────────────────────┘
               │  señales Qt / hilos QThread (workers)
┌──────────────┴──────────────────────────────────────────────────┐
│                      Núcleo de procesamiento                     │
│                                                                  │
│  PDF escaneado                                                   │
│     │                                                            │
│     ▼                                                            │
│  [ocr]  OCRmyPDF + Tesseract (spa)  ──►  PDF con capa de texto   │
│     │                                                            │
│     ▼                                                            │
│  [extraccion]  PyMuPDF: texto por página  ──►  TXT + JSON        │
│     │          limpieza: páginas vacías, encabezados/pies        │
│     │          repetidos, membretes, sellos, nº exp. repetidos   │
│     ▼                                                            │
│  [bloques]  división configurable (10–30 páginas)                │
│     │                                                            │
│     ▼                                                            │
│  [resumen]  Ollama (modelo local elegible) por bloque            │
│     │       caché en SQLite: no se reprocesa lo ya resumido      │
│     ▼                                                            │
│  resumen general estructurado (16 secciones, con nº de página)   │
│                                                                  │
│  [analisis]   cronología (fechas) + clasificación de documentos  │
│  [busqueda]   embeddings locales (Ollama) + ChromaDB/FAISS/numpy │
│  [exportacion] DOCX (python-docx) · PDF (ReportLab) · TXT · JSON │
│  [claude_api] revisión opcional: SOLO resúmenes/cronología/datos │
│  [almacenamiento] SQLite: proyectos, páginas, resúmenes, caché   │
└─────────────────────────────────────────────────────────────────┘
```

Principios:

- **Local primero**: OCR, extracción, resumen y búsqueda funcionan sin conexión.
- **Nada sale de la máquina sin permiso**: la integración con Claude es un módulo aislado (`claude_api`) que solo recibe datos ya destilados (resúmenes, cronología, datos estructurados), nunca el PDF ni el texto completo, salvo selección expresa del usuario.
- **Ahorro de tokens**: el texto se limpia (encabezados, sellos, páginas vacías) antes de resumir; los resúmenes parciales se cachean por hash de contenido; antes de cualquier llamada externa se estima el costo en tokens y se muestra qué se enviará.
- **Modularidad**: cada responsabilidad vive en su paquete, sin dependencias circulares. La interfaz solo orquesta.

## 2. Estructura de carpetas

```
analizador-expedientes/
├── main.py                     # punto de entrada (GUI)
├── requirements.txt
├── README.md
├── app/
│   ├── config/                 # configuración y rutas (settings.py)
│   ├── interfaz/               # PySide6: ventana, pestañas, workers en hilos
│   ├── ocr/                    # OCRmyPDF/Tesseract + verificación de dependencias
│   ├── extraccion/             # PyMuPDF: texto por página + limpieza de ruido
│   ├── bloques/                # división en bloques de 10–30 páginas
│   ├── resumen/                # cliente Ollama, prompts, resumidor con caché
│   ├── analisis/               # cronología (fechas) y clasificación de documentos
│   ├── busqueda/               # embeddings + base vectorial (Chroma/FAISS/numpy)
│   ├── exportacion/            # DOCX, PDF, TXT, JSON
│   ├── claude_api/             # integración opcional con Claude + estimador de tokens
│   ├── almacenamiento/         # SQLite: proyectos, páginas, resúmenes, caché
│   └── utils/                  # errores tipados, logging sin contenido sensible
├── tests/                      # pytest (sin GUI, sin red: Ollama/Claude simulados)
└── recursos/                   # íconos y plantillas
```

Los archivos generados por cada expediente se guardan junto al proyecto, en una carpeta de trabajo:

```
<carpeta_de_salida>/<nombre_expediente>/
├── original.pdf          # copia intacta del PDF original
├── ocr.pdf               # PDF con capa de texto OCR
├── texto_completo.txt
├── texto_por_pagina.json
└── proyecto.db           # SQLite con resúmenes, cronología, documentos, caché
```

## 3. Dependencias

### Programas externos (instalar aparte)

| Programa | Uso | Instalación en Windows |
|---|---|---|
| **Tesseract OCR** (≥5) con idioma `spa` | motor de OCR | instalador de UB-Mannheim: <https://github.com/UB-Mannheim/tesseract/wiki> — marcar "Spanish" en idiomas adicionales |
| **Ghostscript** (≥10) | requerido por OCRmyPDF | <https://ghostscript.com/releases/gsdnld.html> |
| **Ollama** | modelos locales de resumen y embeddings | <https://ollama.com/download/windows> — luego `ollama pull llama3.2` (o el modelo preferido) y `ollama pull nomic-embed-text` (embeddings) |

### Paquetes Python (requirements.txt)

- `PySide6` — interfaz gráfica.
- `ocrmypdf` — orquesta Tesseract/Ghostscript y genera el PDF con capa de texto.
- `PyMuPDF` — extracción de texto por página y render de miniaturas.
- `python-docx` — exportación a Word con formato profesional.
- `reportlab` — exportación a PDF.
- `requests` — comunicación con la API HTTP local de Ollama (`http://localhost:11434`).
- `chromadb` *(opcional)* — base vectorial preferida. Si no está, se usa `faiss-cpu`; si tampoco, un almacén propio sobre `numpy` (siempre local).
- `anthropic` *(opcional)* — solo para la "Revisión con Claude".
- `pytest` — pruebas.

## 4. Instalación

```bat
:: 1. Instalar Python 3.12 desde python.org (marcar "Add to PATH")
:: 2. Instalar Tesseract (con español), Ghostscript y Ollama (ver tabla)

:: 3. Clonar y preparar el entorno
cd analizador-expedientes
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

:: 4. (Opcional) base vectorial e integración con Claude
pip install chromadb anthropic

:: 5. Descargar modelos locales
ollama pull llama3.2
ollama pull nomic-embed-text

:: 6. Ejecutar
python main.py
```

La clave de API de Claude (opcional) **nunca** se escribe en el código ni en archivos del proyecto: se lee de la variable de entorno `ANTHROPIC_API_KEY`:

```bat
setx ANTHROPIC_API_KEY "sk-ant-..."
```

## 5. Flujo de procesamiento

1. **Carga**: el usuario arrastra o selecciona un PDF. Se valida que no esté dañado ni protegido con contraseña (mensajes claros en cada caso) y se copia el original a la carpeta del proyecto.
2. **OCR**: OCRmyPDF ejecuta Tesseract en español (`--language spa`). Si el PDF ya tiene capa de texto se aprovecha (`--skip-text`). Genera `ocr.pdf`.
3. **Extracción**: PyMuPDF extrae el texto página por página → `texto_completo.txt` y `texto_por_pagina.json`.
4. **Limpieza**: se detectan y descartan páginas vacías, encabezados y pies repetidos, membretes, números de expediente repetidos y sellos/textos duplicados. Se conserva registro de qué se eliminó (auditable), y el texto original queda intacto en los archivos del paso 3.
5. **División en bloques**: el texto limpio se agrupa en bloques de tamaño configurable (10–30 páginas).
6. **Resumen por bloque (local)**: cada bloque se envía a Ollama con un prompt que exige citar el número de página de cada dato. El resultado se guarda en SQLite indexado por hash del contenido del bloque + modelo: si el bloque no cambió, no se vuelve a procesar.
7. **Resumen general**: los resúmenes parciales se consolidan (también con Ollama) en la estructura de 16 secciones (carátula, organismo, objeto, antecedentes, …, conclusión), manteniendo las citas de página.
8. **Análisis**: en paralelo se construye la **cronología** (extracción de fechas con contexto, ordenadas) y el listado de **documentos detectados** (notas, resoluciones, decretos, contratos, convenios, dictámenes, informes, presupuestos, facturas, órdenes de compra, actas, documentación contable).
9. **Búsqueda semántica**: las páginas se indexan con embeddings locales (Ollama `nomic-embed-text`) en ChromaDB/FAISS/numpy. Las preguntas del usuario recuperan los pasajes más relevantes y, opcionalmente, Ollama redacta la respuesta citando páginas.
10. **Exportación**: DOCX profesional (carátula, índice, encabezado/pie, numeración, tablas de fechas/montos/documentos), PDF, TXT y JSON.
11. **Revisión con Claude (opcional)**: desactivada por defecto. Al activarla se muestra exactamente qué se enviará (solo resúmenes, cronología y datos estructurados), la estimación de tokens, y se pide confirmación expresa. El PDF completo jamás se envía salvo selección manual y advertida.

## 6. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| **OCRmyPDF sobre Tesseract directo** | maneja rotación, deskew, optimización y produce un PDF/A con capa de texto buscable en un solo paso; Tesseract queda como motor subyacente. |
| **API HTTP de Ollama con `requests`** (sin SDK) | menos dependencias; la API local es estable (`/api/tags`, `/api/generate`, `/api/embeddings`) y permite detectar con precisión "Ollama no está corriendo" vs "falta el modelo". |
| **Caché de resúmenes por hash SHA-256 (contenido del bloque + modelo + versión de prompt)** | evita reprocesar bloques ya analizados aunque cambie la división o se reabra el proyecto; cambiar de modelo invalida la caché sólo de ese modelo. |
| **Limpieza de ruido antes de resumir** | los encabezados/sellos repetidos consumen contexto del modelo local y tokens si se usa Claude; eliminarlos mejora calidad y costo. La detección es por frecuencia (líneas que se repiten en ≥ un umbral de páginas en la zona superior/inferior). |
| **Base vectorial con degradación elegante** (Chroma → FAISS → numpy) | `chromadb` y `faiss` pueden ser pesados de instalar en Windows; el almacén numpy (coseno por fuerza bruta) es suficiente para expedientes de cientos de páginas y garantiza que la búsqueda semántica siempre funcione, 100% local. |
| **Cronología y clasificación de documentos por reglas (regex) y no por LLM** | determinista, instantáneo, sin costo de tokens y auditable; el LLM sólo complementa. Fechas en formatos es-AR: `12/03/2024`, `12 de marzo de 2024`, etc. |
| **SQLite por proyecto** (`proyecto.db`) | portable (se copia la carpeta y viaja todo), sin servidor, transaccional. |
| **Claude aislado en `claude_api/`** | el resto de la app no importa nada de ese paquete; es imposible que un flujo local "toque" la red por accidente. Clave sólo por variable de entorno. |
| **Logging sin contenido sensible** | se registran acciones y metadatos (archivo, páginas, duración, modelo) pero nunca texto del expediente. |
| **Estimación de tokens local** (~1 token ≈ 3,5 caracteres en español) | orden de magnitud suficiente para advertir el costo antes de llamar a Claude, sin depender de tokenizadores externos. |
| **Workers en `QThread`** | OCR y resumen tardan minutos; la GUI permanece fluida y muestra progreso por página/bloque, con posibilidad de cancelar. |

## 7. Manejo de errores previsto

La aplicación muestra mensajes claros y accionables cuando:

- **Tesseract no está instalado** → indica el enlace del instalador y cómo agregar el idioma español.
- **Ollama no está corriendo** → sugiere abrir la aplicación Ollama o ejecutar `ollama serve`.
- **Falta el modelo local** → ofrece el comando exacto `ollama pull <modelo>`.
- **PDF protegido con contraseña** → pide desbloquearlo antes de procesar.
- **PDF dañado** → informa que el archivo no puede abrirse.
- **El OCR no detecta texto** → advierte que el escaneo puede ser ilegible (resolución/contraste).
- **Memoria insuficiente** → sugiere reducir el tamaño de bloque o usar un modelo más liviano.

## 8. Pruebas

```bash
pytest tests/ -v
```

Las pruebas no requieren GUI, Tesseract ni Ollama: los servicios externos se simulan (mocks) y los PDFs de prueba se generan con PyMuPDF al vuelo.
