"""Widgets auxiliares: zona de arrastrar/soltar PDF."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel


class ZonaArrastre(QLabel):
    """Área que acepta un PDF arrastrado o un clic para elegir archivo."""

    pdf_recibido = Signal(str)
    clic = Signal()

    def __init__(self):
        super().__init__(
            "Arrastrá un PDF escaneado acá\no hacé clic para elegir el archivo"
        )
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #8a8a8a; border-radius: 10px;"
            " color: #555; font-size: 14px; padding: 12px; }"
            "QLabel:hover { border-color: #2d6cdf; color: #2d6cdf; }"
        )

    def dragEnterEvent(self, evento):
        urls = evento.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
            evento.acceptProposedAction()

    def dropEvent(self, evento):
        ruta = evento.mimeData().urls()[0].toLocalFile()
        if Path(ruta).suffix.lower() == ".pdf":
            self.pdf_recibido.emit(ruta)

    def mousePressEvent(self, evento):
        self.clic.emit()
