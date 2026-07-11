"""Errores tipados de la aplicación.

Cada error lleva un mensaje pensado para el usuario final, con la causa
y el paso concreto para resolverla. La interfaz los muestra tal cual.
"""


class ErrorAplicacion(Exception):
    """Base de todos los errores esperables de la aplicación."""

    titulo = "Error"

    def __init__(self, mensaje: str, detalle: str = ""):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


class TesseractNoInstalado(ErrorAplicacion):
    titulo = "Tesseract no está instalado"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "No se encontró Tesseract OCR en el sistema.\n\n"
            "Instalalo desde https://github.com/UB-Mannheim/tesseract/wiki "
            "y marcá el idioma español (spa) durante la instalación. "
            "Luego reiniciá la aplicación.",
            detalle,
        )


class IdiomaEspanolFaltante(ErrorAplicacion):
    titulo = "Falta el idioma español en Tesseract"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "Tesseract está instalado pero no tiene el paquete de idioma "
            "español (spa).\n\nReinstalá Tesseract marcando 'Spanish' en la "
            "lista de idiomas adicionales, o copiá spa.traineddata a la "
            "carpeta tessdata.",
            detalle,
        )


class OcrmypdfNoInstalado(ErrorAplicacion):
    titulo = "OCRmyPDF no está disponible"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "El paquete ocrmypdf no está instalado en este entorno de "
            "Python.\n\nEjecutá:  pip install ocrmypdf",
            detalle,
        )


class OllamaNoDisponible(ErrorAplicacion):
    titulo = "Ollama no está funcionando"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "No se pudo conectar con Ollama en http://localhost:11434.\n\n"
            "Abrí la aplicación Ollama (o ejecutá 'ollama serve' en una "
            "terminal) y volvé a intentar.",
            detalle,
        )


class ModeloNoInstalado(ErrorAplicacion):
    titulo = "Falta el modelo local"

    def __init__(self, modelo: str, detalle: str = ""):
        super().__init__(
            f"El modelo '{modelo}' no está instalado en Ollama.\n\n"
            f"Descargalo con:  ollama pull {modelo}",
            detalle,
        )
        self.modelo = modelo


class PdfProtegido(ErrorAplicacion):
    titulo = "PDF protegido"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "El PDF está protegido con contraseña y no puede procesarse.\n\n"
            "Desbloquealo (por ejemplo, imprimiéndolo a un PDF nuevo o "
            "quitando la contraseña con la clave que corresponda) y volvé "
            "a cargarlo.",
            detalle,
        )


class PdfDanado(ErrorAplicacion):
    titulo = "PDF dañado"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "El archivo no pudo abrirse como PDF: está dañado o no es un "
            "PDF válido.\n\nProbá abrirlo en un visor de PDF; si tampoco "
            "abre allí, habrá que volver a escanear o recuperar el archivo.",
            detalle,
        )


class OcrSinTexto(ErrorAplicacion):
    titulo = "El OCR no detectó texto"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "El OCR terminó pero no se detectó texto legible en el "
            "documento.\n\nEl escaneo puede tener muy baja resolución o "
            "contraste. Probá re-escanear a 300 dpi o más, en escala de "
            "grises.",
            detalle,
        )


class MemoriaInsuficiente(ErrorAplicacion):
    titulo = "Memoria insuficiente"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "El sistema se quedó sin memoria durante el procesamiento.\n\n"
            "Cerrá otras aplicaciones, reducí el tamaño de bloque en la "
            "configuración o usá un modelo local más liviano (por ejemplo "
            "llama3.2:1b).",
            detalle,
        )


class ClaveApiFaltante(ErrorAplicacion):
    titulo = "Falta la clave de API"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "No se encontró la variable de entorno ANTHROPIC_API_KEY.\n\n"
            "Definila (setx ANTHROPIC_API_KEY \"sk-ant-...\" en Windows) y "
            "reiniciá la aplicación. La clave nunca se guarda en archivos "
            "del programa.",
            detalle,
        )
