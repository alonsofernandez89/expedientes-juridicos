"""Ventana principal: orquesta las pestañas, los workers y la configuración."""

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.busqueda.buscador import BuscadorSemantico
from app.almacenamiento.base_datos import BaseDatosProyecto
from app.claude_api import cliente_claude
from app.config.settings import (
    BLOQUE_PAGINAS_MAX,
    BLOQUE_PAGINAS_MIN,
    Configuracion,
    VERSION_APP,
)
from app.exportacion.datos_informe import Informe
from app.exportacion.exportar_docx import exportar_docx
from app.exportacion.exportar_pdf import exportar_pdf
from app.exportacion.exportar_texto import exportar_json, exportar_txt
from app.interfaz.pestanas import (
    PestanaClaude,
    PestanaCronologia,
    PestanaDocumentos,
    PestanaExportar,
    PestanaPreguntas,
    PestanaResumenes,
    PestanaTexto,
)
from app.interfaz.widgets import ZonaArrastre
from app.interfaz.workers import Worker
from app.pipeline import ProcesadorExpediente, ResultadoProcesamiento
from app.resumen.cliente_ollama import ClienteOllama
from app.utils.registro import obtener_logger

log = obtener_logger("interfaz")


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Analizador de Expedientes v{VERSION_APP} — procesamiento local")
        self.resize(1150, 780)

        self.config = Configuracion.cargar()
        self.resultado: ResultadoProcesamiento | None = None
        self._workers: list[Worker] = []
        self._buscador: BuscadorSemantico | None = None

        self._armar_interfaz()
        self._refrescar_modelos_ollama()

    # ------------------------------------------------------------------ UI
    def _armar_interfaz(self):
        central = QWidget()
        capa = QVBoxLayout(central)

        # --- zona de carga y opciones ---
        self.zona = ZonaArrastre()
        self.zona.pdf_recibido.connect(self._procesar_pdf)
        self.zona.clic.connect(self._elegir_pdf)
        capa.addWidget(self.zona)

        opciones = QHBoxLayout()
        opciones.addWidget(QLabel("Modelo local (Ollama):"))
        self.combo_modelo = QComboBox()
        self.combo_modelo.setMinimumWidth(180)
        opciones.addWidget(self.combo_modelo)
        self.boton_refrescar = QPushButton("↻")
        self.boton_refrescar.setToolTip("Volver a consultar los modelos instalados en Ollama")
        self.boton_refrescar.setFixedWidth(34)
        self.boton_refrescar.clicked.connect(self._refrescar_modelos_ollama)
        opciones.addWidget(self.boton_refrescar)

        opciones.addSpacing(16)
        opciones.addWidget(QLabel("Páginas por bloque:"))
        self.spin_bloque = QSpinBox()
        self.spin_bloque.setRange(BLOQUE_PAGINAS_MIN, BLOQUE_PAGINAS_MAX)
        self.spin_bloque.setValue(self.config.paginas_por_bloque)
        opciones.addWidget(self.spin_bloque)

        self.check_limpiar = QCheckBox("Eliminar encabezados/sellos repetidos")
        self.check_limpiar.setChecked(self.config.limpiar_ruido)
        opciones.addWidget(self.check_limpiar)
        opciones.addStretch()

        self.boton_abrir = QPushButton("Abrir proyecto existente…")
        self.boton_abrir.clicked.connect(self._abrir_proyecto)
        opciones.addWidget(self.boton_abrir)
        capa.addLayout(opciones)

        # --- progreso ---
        fila_progreso = QHBoxLayout()
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.etiqueta_estado = QLabel("Listo. Todo el procesamiento es local.")
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.clicked.connect(self._cancelar_workers)
        fila_progreso.addWidget(self.barra, 1)
        fila_progreso.addWidget(self.boton_cancelar)
        capa.addLayout(fila_progreso)
        capa.addWidget(self.etiqueta_estado)

        # --- pestañas ---
        self.pestanas = QTabWidget()
        self.bitacora = QPlainTextEdit()
        self.bitacora.setReadOnly(True)
        self.pestana_texto = PestanaTexto()
        self.pestana_resumenes = PestanaResumenes()
        self.pestana_cronologia = PestanaCronologia()
        self.pestana_documentos = PestanaDocumentos()
        self.pestana_preguntas = PestanaPreguntas()
        self.pestana_claude = PestanaClaude()
        self.pestana_exportar = PestanaExportar()

        self.pestanas.addTab(self.bitacora, "Procesamiento")
        self.pestanas.addTab(self.pestana_texto, "Texto por página")
        self.pestanas.addTab(self.pestana_resumenes, "Resúmenes")
        self.pestanas.addTab(self.pestana_cronologia, "Cronología")
        self.pestanas.addTab(self.pestana_documentos, "Documentos detectados")
        self.pestanas.addTab(self.pestana_preguntas, "Preguntas")
        self.pestanas.addTab(self.pestana_claude, "Revisión con Claude")
        self.pestanas.addTab(self.pestana_exportar, "Exportar")
        capa.addWidget(self.pestanas, 1)

        self.pestana_preguntas.indexar_pedido.connect(self._indexar)
        self.pestana_preguntas.pregunta_enviada.connect(self._preguntar)
        self.pestana_claude.revisar_pedido.connect(self._revisar_con_claude)
        self.pestana_exportar.exportar_pedido.connect(self._exportar)

        self.setCentralWidget(central)

    # ------------------------------------------------------------ utilidades
    def _guardar_config(self):
        self.config.paginas_por_bloque = self.spin_bloque.value()
        self.config.limpiar_ruido = self.check_limpiar.isChecked()
        if self.combo_modelo.currentText():
            self.config.modelo_resumen = self.combo_modelo.currentText()
        self.config.guardar()

    def _avisar(self, mensaje: str):
        self.etiqueta_estado.setText(mensaje)
        self.bitacora.appendPlainText(mensaje)

    def _mostrar_error(self, titulo: str, mensaje: str, detalle: str = ""):
        self._avisar(f"✖ {titulo}")
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Warning)
        caja.setWindowTitle(titulo)
        caja.setText(mensaje)
        if detalle:
            caja.setDetailedText(detalle)
        caja.exec()
        self._fin_trabajo()

    def _lanzar_worker(self, funcion, *args, al_terminar=None, ocupado=True, **kwargs) -> Worker:
        worker = Worker(funcion, *args, **kwargs)
        worker.progreso.connect(self._avisar)
        worker.progreso_parcial.connect(self._progreso_parcial)
        worker.fallo.connect(self._mostrar_error)
        if al_terminar:
            worker.terminado.connect(al_terminar)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        worker.finished.connect(self._fin_trabajo)
        self._workers.append(worker)
        if ocupado:
            self.barra.setRange(0, 0)  # modo indeterminado
            self.boton_cancelar.setEnabled(True)
        worker.start()
        return worker

    def _progreso_parcial(self, actual: int, total: int, etapa: str):
        self.barra.setRange(0, total)
        self.barra.setValue(actual)
        nombres = {"resumen": "Bloques resumidos", "indice": "Fragmentos indexados"}
        self._avisar(f"{nombres.get(etapa, etapa)}: {actual}/{total}")

    def _fin_trabajo(self):
        if not self._workers:
            self.barra.setRange(0, 100)
            self.barra.setValue(0)
            self.boton_cancelar.setEnabled(False)

    def _cancelar_workers(self):
        for w in self._workers:
            w.cancelar()
        self._avisar("Cancelando… se conserva lo ya procesado.")

    def _exigir_resultado(self) -> bool:
        if self.resultado is None:
            QMessageBox.information(
                self, "Sin expediente",
                "Primero cargá y procesá un PDF (o abrí un proyecto existente).",
            )
            return False
        return True

    # ------------------------------------------------------------ modelos
    def _refrescar_modelos_ollama(self):
        def consultar():
            cliente = ClienteOllama()
            if not cliente.esta_activo():
                return []
            return cliente.listar_modelos()

        def listo(modelos):
            self.combo_modelo.clear()
            if modelos:
                self.combo_modelo.addItems(modelos)
                indice = self.combo_modelo.findText(self.config.modelo_resumen)
                if indice < 0:
                    # probar por nombre base (llama3.2 vs llama3.2:latest)
                    for i in range(self.combo_modelo.count()):
                        if self.combo_modelo.itemText(i).split(":")[0] == self.config.modelo_resumen.split(":")[0]:
                            indice = i
                            break
                self.combo_modelo.setCurrentIndex(max(0, indice))
                self._avisar(f"Ollama activo: {len(modelos)} modelos disponibles.")
            else:
                self.combo_modelo.addItem("(Ollama no disponible)")
                self._avisar(
                    "Ollama no está corriendo: el resumen local no va a funcionar "
                    "hasta que lo inicies (abrí la app Ollama o 'ollama serve')."
                )

        self._lanzar_worker(consultar, al_terminar=listo, ocupado=False)

    # ------------------------------------------------------------ pipeline
    def _elegir_pdf(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegir PDF escaneado", str(Path.home()), "Documentos PDF (*.pdf)"
        )
        if ruta:
            self._procesar_pdf(ruta)

    def _procesar_pdf(self, ruta: str):
        if self._workers:
            QMessageBox.information(self, "Procesando", "Ya hay un procesamiento en curso.")
            return
        self._guardar_config()
        procesador = ProcesadorExpediente(self.config)

        def tarea(progreso=None, progreso_parcial=None, cancelado=None):
            procesador._progreso = progreso or procesador._progreso
            procesador._parcial = progreso_parcial or procesador._parcial
            procesador._cancelado = cancelado or procesador._cancelado
            resultado = procesador.procesar_hasta_texto(Path(ruta))
            if not (cancelado and cancelado()):
                resultado = procesador.resumir(resultado)
            return resultado

        self._avisar(f"Procesando: {ruta}")
        self._lanzar_worker(tarea, al_terminar=self._mostrar_resultado)

    def _abrir_proyecto(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir la carpeta del proyecto", self.config.carpeta_salida
        )
        if not carpeta:
            return
        resultado = ProcesadorExpediente.cargar_proyecto(Path(carpeta))
        if resultado is None:
            QMessageBox.warning(
                self, "Proyecto inválido",
                "Esa carpeta no contiene un proyecto procesado (falta proyecto.db).",
            )
            return
        self._avisar(f"Proyecto reabierto: {carpeta} (sin repetir OCR ni resúmenes)")
        self._mostrar_resultado(resultado)

    def _mostrar_resultado(self, resultado: ResultadoProcesamiento):
        self.resultado = resultado
        self._buscador = None  # el índice se regenera o restaura a pedido
        self.pestana_texto.actualizar(
            resultado.paginas, resultado.paginas_limpias, resultado.paginas_vacias
        )
        self.pestana_resumenes.actualizar(
            resultado.resumen_general, resultado.resumenes_parciales
        )
        self.pestana_cronologia.actualizar(resultado.cronologia)
        self.pestana_documentos.actualizar(resultado.documentos)
        self._avisar(
            f"Expediente listo: {resultado.total_paginas} páginas, "
            f"{len(resultado.cronologia)} fechas, {len(resultado.documentos)} documentos detectados."
        )

    # ------------------------------------------------------------ búsqueda
    def _crear_buscador(self) -> BuscadorSemantico:
        db = BaseDatosProyecto(self.resultado.carpeta / "proyecto.db")
        return BuscadorSemantico(ClienteOllama(), db, self.config.modelo_embeddings)

    def _indexar(self):
        if not self._exigir_resultado():
            return
        buscador = self._crear_buscador()

        def tarea(progreso_parcial=None, cancelado=None):
            if buscador.cargar_indice_guardado():
                return buscador
            paginas = self.resultado.paginas_limpias or self.resultado.paginas
            buscador.indexar(
                paginas,
                progreso=lambda a, t: progreso_parcial and progreso_parcial(a, t, "indice"),
                cancelado=cancelado,
            )
            return buscador

        def listo(b):
            self._buscador = b
            self.pestana_preguntas.estado.setText(
                f"Índice: listo ({b.almacen.nombre}, {len(b.almacen)} fragmentos)"
            )
            self._avisar("Búsqueda semántica lista.")

        self._avisar("Indexando el expediente con embeddings locales…")
        self._lanzar_worker(tarea, al_terminar=listo)

    def _preguntar(self, pregunta: str):
        if not self._exigir_resultado():
            return
        if self._buscador is None or not self._buscador.esta_indexado:
            QMessageBox.information(
                self, "Falta el índice",
                "Primero presioná 'Indexar expediente' para generar el índice semántico local.",
            )
            return
        modelo = self.combo_modelo.currentText() or self.config.modelo_resumen

        def tarea():
            return self._buscador.preguntar(pregunta, modelo)

        self._avisar(f"Buscando: {pregunta}")
        self._lanzar_worker(tarea, al_terminar=self.pestana_preguntas.mostrar_respuesta)

    # ------------------------------------------------------------ Claude
    def _revisar_con_claude(self, pregunta: str, opciones: dict):
        if not self._exigir_resultado():
            return
        r = self.resultado
        try:
            envio = cliente_claude.preparar_envio(
                pregunta=pregunta,
                modelo=self.config.modelo_claude,
                resumen_general=r.resumen_general if opciones["resumen_general"] else None,
                resumenes_parciales=r.resumenes_parciales if opciones["parciales"] else None,
                cronologia=r.cronologia if opciones["cronologia"] else None,
                documentos=r.documentos if opciones["documentos"] else None,
                texto_completo=(
                    "\n\n".join(r.paginas) if opciones["texto_completo"] else None
                ),
                permitir_texto_completo=opciones["texto_completo"],
            )
        except Exception as e:
            titulo = getattr(e, "titulo", "No se pudo preparar el envío")
            self._mostrar_error(titulo, str(e))
            return

        detalle = (
            "SE ENVIARÁ A LA API DE CLAUDE (Anthropic):\n\n- "
            + "\n- ".join(envio.secciones_incluidas)
            + f"\n- Consulta: {envio.pregunta}\n\n{envio.estimacion.resumen()}\n\n"
            "No se envía el PDF" + (
                "." if not opciones["texto_completo"]
                else " — PERO SELECCIONASTE INCLUIR EL TEXTO COMPLETO."
            )
        )
        confirmacion = QMessageBox(self)
        confirmacion.setIcon(QMessageBox.Question)
        confirmacion.setWindowTitle("Confirmar envío a Claude")
        confirmacion.setText(
            "¿Confirmás el envío de esta información a un servicio externo?"
        )
        confirmacion.setInformativeText(detalle)
        confirmacion.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        confirmacion.button(QMessageBox.Yes).setText("Enviar a Claude")
        confirmacion.button(QMessageBox.Cancel).setText("Cancelar")
        if confirmacion.exec() != QMessageBox.Yes:
            self._avisar("Envío a Claude cancelado por el usuario.")
            return

        envio.confirmado = True
        self._avisar("Consultando a Claude… (solo datos destilados)")
        self._lanzar_worker(
            cliente_claude.enviar, envio,
            al_terminar=self.pestana_claude.mostrar_respuesta,
        )

    # ------------------------------------------------------------ exportar
    def _exportar(self, formato: str):
        if not self._exigir_resultado():
            return
        r = self.resultado
        if not r.resumen_general:
            QMessageBox.information(
                self, "Falta el resumen",
                "Generá primero el resumen (procesando el expediente con Ollama activo).",
            )
            return
        nombre = r.carpeta.name
        ruta, _ = QFileDialog.getSaveFileName(
            self, f"Guardar informe {formato.upper()}",
            str(r.carpeta / f"informe_{nombre}.{formato}"),
            f"Archivo {formato.upper()} (*.{formato})",
        )
        if not ruta:
            return
        informe = Informe(
            titulo="Análisis de expediente administrativo",
            expediente=nombre,
            resumen_general=r.resumen_general,
            resumenes_parciales=r.resumenes_parciales,
            cronologia=r.cronologia,
            documentos=r.documentos,
            metadatos={
                "fecha_analisis": date.today().isoformat(),
                "total_paginas": r.total_paginas,
                "modelo": self.config.modelo_resumen,
            },
        )
        exportadores = {
            "docx": exportar_docx, "pdf": exportar_pdf,
            "txt": exportar_txt, "json": exportar_json,
        }

        def tarea():
            exportadores[formato](informe, Path(ruta))
            return ruta

        self._lanzar_worker(
            tarea,
            al_terminar=lambda destino: self._avisar(f"✔ Informe exportado: {destino}"),
        )
