"""Workers en QThread: mantienen la GUI fluida durante OCR y resúmenes."""

from PySide6.QtCore import QThread, Signal

from app.utils.errores import ErrorAplicacion
from app.utils.registro import obtener_logger

log = obtener_logger("interfaz")


class Worker(QThread):
    """Ejecuta `funcion(*args, progreso=?, progreso_parcial=?, cancelado=?)`
    en un hilo. La función decide qué callbacks aceptar (se inyectan solo
    los que su firma admite)."""

    progreso = Signal(str)
    progreso_parcial = Signal(int, int, str)
    terminado = Signal(object)
    fallo = Signal(str, str, str)  # titulo, mensaje, detalle

    def __init__(self, funcion, *args, **kwargs):
        super().__init__()
        self._funcion = funcion
        self._args = args
        self._kwargs = kwargs
        self._cancelar = False

    def cancelar(self) -> None:
        self._cancelar = True

    @property
    def cancelado(self) -> bool:
        return self._cancelar

    def run(self) -> None:
        import inspect

        try:
            parametros = set(inspect.signature(self._funcion).parameters)
            extras = {}
            if "progreso" in parametros:
                extras["progreso"] = self.progreso.emit
            if "progreso_parcial" in parametros:
                extras["progreso_parcial"] = self.progreso_parcial.emit
            if "cancelado" in parametros:
                extras["cancelado"] = lambda: self._cancelar
            resultado = self._funcion(*self._args, **self._kwargs, **extras)
            self.terminado.emit(resultado)
        except ErrorAplicacion as e:
            log.warning("Operación fallida: %s (%s)", e.titulo, e.detalle or "sin detalle")
            self.fallo.emit(e.titulo, e.mensaje, e.detalle)
        except MemoryError as e:
            from app.utils.errores import MemoriaInsuficiente

            err = MemoriaInsuficiente(detalle=str(e))
            self.fallo.emit(err.titulo, err.mensaje, err.detalle)
        except Exception as e:  # inesperado: mostrarlo sin matar la app
            log.exception("Error inesperado en worker")
            self.fallo.emit("Error inesperado", str(e), "")
