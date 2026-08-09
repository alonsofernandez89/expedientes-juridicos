"""Verificación de dependencias externas del OCR (Tesseract, idioma spa)."""

import shutil
import subprocess

from app.utils.errores import (
    IdiomaEspanolFaltante,
    OcrmypdfNoInstalado,
    TesseractNoInstalado,
)


def ruta_tesseract() -> str | None:
    return shutil.which("tesseract")


def idiomas_tesseract() -> list[str]:
    """Idiomas instalados en Tesseract. Lanza TesseractNoInstalado si falta."""
    exe = ruta_tesseract()
    if not exe:
        raise TesseractNoInstalado()
    try:
        salida = subprocess.run(
            [exe, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as e:
        raise TesseractNoInstalado(detalle=str(e))
    # La primera línea es un encabezado ("List of available languages...")
    lineas = (salida.stdout + salida.stderr).strip().splitlines()
    return [l.strip() for l in lineas if l.strip() and ":" not in l]


def verificar_ocr(idioma: str = "spa") -> None:
    """Verifica toda la cadena de OCR; lanza un error tipado si algo falta."""
    try:
        import ocrmypdf  # noqa: F401
    except ImportError as e:
        raise OcrmypdfNoInstalado(detalle=str(e))
    idiomas = idiomas_tesseract()
    if idioma not in idiomas:
        raise IdiomaEspanolFaltante(detalle=f"Idiomas instalados: {', '.join(idiomas)}")
