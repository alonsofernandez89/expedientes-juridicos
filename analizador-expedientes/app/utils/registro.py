"""Logging de acciones SIN contenido sensible.

Regla: se registran acciones y metadatos (nombres de archivo, cantidad de
páginas, duración, modelo usado, códigos de error) pero NUNCA texto del
expediente ni fragmentos de resúmenes.
"""

import logging
import logging.handlers
from pathlib import Path

_NOMBRE = "analizador_expedientes"


def configurar_registro(carpeta_logs: Path) -> logging.Logger:
    """Configura el logger raíz de la app con archivo rotativo y consola."""
    carpeta_logs.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_NOMBRE)
    if logger.handlers:  # ya configurado
        return logger
    logger.setLevel(logging.INFO)

    formato = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"
    )

    archivo = logging.handlers.RotatingFileHandler(
        carpeta_logs / "aplicacion.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    archivo.setFormatter(formato)
    logger.addHandler(archivo)

    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    logger.addHandler(consola)
    return logger


def obtener_logger(modulo: str) -> logging.Logger:
    """Logger hijo por módulo: obtener_logger('ocr') → analizador_expedientes.ocr"""
    return logging.getLogger(f"{_NOMBRE}.{modulo}")
