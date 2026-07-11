"""Pestañas de la ventana principal.

Cada pestaña es un widget autónomo con un método `actualizar(...)` que la
ventana principal invoca cuando hay datos nuevos. Las acciones que requieren
trabajo pesado o red se piden por señales; la ventana principal las ejecuta
en workers.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

_AVISO_SIN_DATOS = "Todavía no hay datos: procesá un expediente en la pestaña Procesamiento."


class PestanaTexto(QWidget):
    """Texto extraído por página, con vista cruda o limpia."""

    def __init__(self):
        super().__init__()
        self._crudas: list[str] = []
        self._limpias: list[str] = []
        self._vacias: set[int] = set()

        self._lista = QListWidget()
        self._lista.setMaximumWidth(180)
        self._texto = QPlainTextEdit()
        self._texto.setReadOnly(True)
        self._ver_limpio = QCheckBox("Ver texto limpio (sin encabezados ni sellos)")
        self._ver_limpio.setChecked(True)

        divisor = QSplitter()
        divisor.addWidget(self._lista)
        divisor.addWidget(self._texto)
        divisor.setStretchFactor(1, 1)

        capa = QVBoxLayout(self)
        capa.addWidget(self._ver_limpio)
        capa.addWidget(divisor)

        self._lista.currentRowChanged.connect(self._mostrar)
        self._ver_limpio.toggled.connect(lambda _: self._mostrar(self._lista.currentRow()))

    def actualizar(self, crudas: list[str], limpias: list[str], vacias: list[int]):
        self._crudas, self._limpias = crudas, limpias
        self._vacias = set(vacias)
        self._lista.clear()
        for i in range(1, len(crudas) + 1):
            etiqueta = f"Página {i}"
            if i in self._vacias:
                etiqueta += "  (vacía)"
            self._lista.addItem(etiqueta)
        if crudas:
            self._lista.setCurrentRow(0)

    def _mostrar(self, fila: int):
        if fila < 0 or fila >= len(self._crudas):
            self._texto.setPlainText("")
            return
        fuente = self._limpias if (self._ver_limpio.isChecked() and self._limpias) else self._crudas
        texto = fuente[fila]
        if not texto.strip():
            texto = "(página sin texto tras la limpieza)"
        self._texto.setPlainText(texto)


class PestanaResumenes(QWidget):
    """Resumen general estructurado + resúmenes parciales por bloque."""

    def __init__(self):
        super().__init__()
        self._general = QTextBrowser()
        self._parciales = QTextBrowser()
        divisor = QSplitter(Qt.Vertical)
        divisor.addWidget(self._envolver("Resumen general del expediente", self._general))
        divisor.addWidget(self._envolver("Resúmenes parciales por bloque", self._parciales))
        capa = QVBoxLayout(self)
        capa.addWidget(divisor)
        self._general.setPlaceholderText(_AVISO_SIN_DATOS)

    @staticmethod
    def _envolver(titulo: str, widget) -> QWidget:
        caja = QWidget()
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(0, 0, 0, 0)
        etiqueta = QLabel(f"<b>{titulo}</b>")
        capa.addWidget(etiqueta)
        capa.addWidget(widget)
        return caja

    def actualizar(self, general: str, parciales: list[str]):
        self._general.setMarkdown(general or "")
        self._parciales.setMarkdown("\n\n---\n\n".join(parciales))


class PestanaCronologia(QWidget):
    """Hechos y documentos ordenados por fecha."""

    def __init__(self):
        super().__init__()
        self._tabla = QTableWidget(0, 3)
        self._tabla.setHorizontalHeaderLabels(["Fecha", "Hecho / contexto", "Página"])
        self._tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("Cronología del expediente (fechas detectadas automáticamente):"))
        capa.addWidget(self._tabla)

    def actualizar(self, eventos: list[dict]):
        self._tabla.setRowCount(len(eventos))
        for fila, e in enumerate(eventos):
            fecha = e.get("fecha_texto") or e.get("fecha_iso", "")
            self._tabla.setItem(fila, 0, QTableWidgetItem(str(fecha)))
            self._tabla.setItem(fila, 1, QTableWidgetItem(e.get("contexto", "")))
            self._tabla.setItem(fila, 2, QTableWidgetItem(str(e.get("pagina", ""))))


class PestanaDocumentos(QWidget):
    """Documentos detectados, con filtro por tipo."""

    def __init__(self):
        super().__init__()
        self._documentos: list[dict] = []
        self._filtro = QComboBox()
        self._filtro.addItem("Todos los tipos")
        self._tabla = QTableWidget(0, 3)
        self._tabla.setHorizontalHeaderLabels(["Tipo", "Referencia", "Página"])
        self._tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)

        fila_filtro = QHBoxLayout()
        fila_filtro.addWidget(QLabel("Filtrar:"))
        fila_filtro.addWidget(self._filtro)
        fila_filtro.addStretch()

        capa = QVBoxLayout(self)
        capa.addLayout(fila_filtro)
        capa.addWidget(self._tabla)
        self._filtro.currentTextChanged.connect(lambda _: self._refrescar())

    def actualizar(self, documentos: list[dict]):
        self._documentos = documentos
        tipos = sorted({d["tipo"] for d in documentos})
        self._filtro.blockSignals(True)
        self._filtro.clear()
        self._filtro.addItem("Todos los tipos")
        self._filtro.addItems(tipos)
        self._filtro.blockSignals(False)
        self._refrescar()

    def _refrescar(self):
        tipo = self._filtro.currentText()
        visibles = [
            d for d in self._documentos
            if tipo == "Todos los tipos" or d["tipo"] == tipo
        ]
        self._tabla.setRowCount(len(visibles))
        for fila, d in enumerate(visibles):
            self._tabla.setItem(fila, 0, QTableWidgetItem(d["tipo"]))
            self._tabla.setItem(fila, 1, QTableWidgetItem(d["referencia"]))
            self._tabla.setItem(fila, 2, QTableWidgetItem(str(d["pagina"])))


class PestanaPreguntas(QWidget):
    """Preguntas sobre el expediente con búsqueda semántica local."""

    indexar_pedido = Signal()
    pregunta_enviada = Signal(str)

    def __init__(self):
        super().__init__()
        self._pregunta = QLineEdit()
        self._pregunta.setPlaceholderText("Ej.: ¿qué montos se adjudicaron y en qué página constan?")
        self.boton_preguntar = QPushButton("Preguntar")
        self.boton_indexar = QPushButton("Indexar expediente")
        self._respuesta = QTextBrowser()
        self._respuesta.setPlaceholderText(
            "La búsqueda es 100 % local (embeddings de Ollama). Primero indexá "
            "el expediente; después hacé preguntas y vas a recibir respuestas "
            "con las páginas de origen."
        )
        self.estado = QLabel("Índice: no generado")

        fila = QHBoxLayout()
        fila.addWidget(self._pregunta, 1)
        fila.addWidget(self.boton_preguntar)
        capa = QVBoxLayout(self)
        fila_indice = QHBoxLayout()
        fila_indice.addWidget(self.boton_indexar)
        fila_indice.addWidget(self.estado)
        fila_indice.addStretch()
        capa.addLayout(fila_indice)
        capa.addLayout(fila)
        capa.addWidget(self._respuesta)

        self.boton_indexar.clicked.connect(self.indexar_pedido.emit)
        self.boton_preguntar.clicked.connect(self._enviar)
        self._pregunta.returnPressed.connect(self._enviar)

    def _enviar(self):
        texto = self._pregunta.text().strip()
        if texto:
            self.pregunta_enviada.emit(texto)

    def mostrar_respuesta(self, resultado: dict):
        partes = [f"**Respuesta:**\n\n{resultado['respuesta']}"]
        if resultado["pasajes"]:
            partes.append("\n\n---\n\n**Pasajes utilizados:**\n")
            for pagina, texto, puntaje in resultado["pasajes"]:
                partes.append(f"- *(pág. {pagina}, similitud {puntaje:.2f})* {texto[:300]}…")
        self._respuesta.setMarkdown("\n".join(partes))


class PestanaClaude(QWidget):
    """Revisión con Claude: opcional, desactivada por defecto, con
    advertencia previa de qué se envía y estimación de tokens."""

    revisar_pedido = Signal(str, dict)   # pregunta, opciones de inclusión

    def __init__(self):
        super().__init__()
        self.habilitar = QCheckBox(
            "Habilitar la Revisión con Claude (servicio externo de Anthropic)"
        )
        self.habilitar.setChecked(False)  # SIEMPRE desactivado por defecto

        aviso = QLabel(
            "⚠ Esta función envía datos a la API de Claude (Anthropic). "
            "Por defecto SOLO se envían los resúmenes, la cronología y los "
            "datos estructurados — nunca el PDF ni el texto completo. Antes "
            "de cada envío se muestra exactamente qué se transmitirá y su "
            "costo estimado en tokens, y se pide confirmación."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color:#8a5a00; background:#fff6e0; padding:8px; border-radius:6px;")

        self.inc_resumen_general = QCheckBox("Incluir resumen general")
        self.inc_parciales = QCheckBox("Incluir resúmenes parciales")
        self.inc_cronologia = QCheckBox("Incluir cronología")
        self.inc_documentos = QCheckBox("Incluir documentos detectados")
        self.inc_texto_completo = QCheckBox(
            "⚠ Incluir TEXTO COMPLETO del expediente (no recomendado)"
        )
        for c in (self.inc_resumen_general, self.inc_parciales,
                  self.inc_cronologia, self.inc_documentos):
            c.setChecked(True)
        self.inc_texto_completo.setChecked(False)

        self._pregunta = QLineEdit()
        self._pregunta.setPlaceholderText(
            "Consulta para Claude, p. ej.: revisá posibles inconsistencias del trámite"
        )
        self.boton_revisar = QPushButton("Calcular envío y revisar…")
        self._respuesta = QTextBrowser()
        self._respuesta.setPlaceholderText(
            "La respuesta de la revisión aparecerá acá."
        )

        capa = QVBoxLayout(self)
        capa.addWidget(aviso)
        capa.addWidget(self.habilitar)
        for c in (self.inc_resumen_general, self.inc_parciales,
                  self.inc_cronologia, self.inc_documentos, self.inc_texto_completo):
            capa.addWidget(c)
        fila = QHBoxLayout()
        fila.addWidget(self._pregunta, 1)
        fila.addWidget(self.boton_revisar)
        capa.addLayout(fila)
        capa.addWidget(self._respuesta)

        self._habilitar_controles(False)
        self.habilitar.toggled.connect(self._habilitar_controles)
        self.boton_revisar.clicked.connect(self._pedir)

    def _habilitar_controles(self, activo: bool):
        for w in (self.inc_resumen_general, self.inc_parciales, self.inc_cronologia,
                  self.inc_documentos, self.inc_texto_completo, self._pregunta,
                  self.boton_revisar):
            w.setEnabled(activo)

    def _pedir(self):
        pregunta = self._pregunta.text().strip()
        if not pregunta:
            pregunta = "Revisá el expediente y señalá inconsistencias, documentación faltante y riesgos."
        self.revisar_pedido.emit(pregunta, {
            "resumen_general": self.inc_resumen_general.isChecked(),
            "parciales": self.inc_parciales.isChecked(),
            "cronologia": self.inc_cronologia.isChecked(),
            "documentos": self.inc_documentos.isChecked(),
            "texto_completo": self.inc_texto_completo.isChecked(),
        })

    def mostrar_respuesta(self, texto: str):
        self._respuesta.setMarkdown(texto)


class PestanaExportar(QWidget):
    """Exportación del informe a DOCX, PDF, TXT y JSON."""

    exportar_pedido = Signal(str)  # "docx" | "pdf" | "txt" | "json"

    def __init__(self):
        super().__init__()
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel(
            "Exportá el informe completo (resumen estructurado, cronología, "
            "documentos detectados y resúmenes por bloque):"
        ))
        descripciones = {
            "docx": "Word (.docx) — formato profesional con carátula, índice, "
                    "encabezado, pie con numeración y tablas",
            "pdf": "PDF — informe final con carátula y tablas",
            "txt": "Texto plano (.txt)",
            "json": "JSON estructurado (para otros sistemas)",
        }
        for formato, descripcion in descripciones.items():
            boton = QPushButton(f"Exportar a {formato.upper()}")
            boton.setMinimumHeight(36)
            boton.clicked.connect(lambda _=False, f=formato: self.exportar_pedido.emit(f))
            capa.addWidget(boton)
            etiqueta = QLabel(descripcion)
            etiqueta.setStyleSheet("color:#666; margin-left: 6px;")
            capa.addWidget(etiqueta)
        capa.addStretch()
