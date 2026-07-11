"""Motor de OCR: valida el PDF y ejecuta OCRmyPDF/Tesseract en español.

El PDF original nunca se modifica: se copia intacto a la carpeta del
proyecto y el OCR se escribe en un archivo nuevo (`ocr.pdf`).
"""

import shutil
from pathlib import Path

from app.ocr.dependencias import verificar_ocr
from app.utils.errores import (
    MemoriaInsuficiente,
    PdfDanado,
    PdfProtegido,
)
from app.utils.registro import obtener_logger

log = obtener_logger("ocr")


def validar_pdf(ruta: Path) -> int:
    """Valida que el PDF pueda abrirse y no esté cifrado.

    Devuelve la cantidad de páginas. Lanza PdfDanado o PdfProtegido.
    """
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(str(ruta))
    except Exception as e:
        raise PdfDanado(detalle=str(e))
    try:
        if doc.needs_pass:
            raise PdfProtegido()
        if not doc.is_pdf:
            raise PdfDanado(detalle="El archivo no es un PDF.")
        paginas = doc.page_count
    finally:
        doc.close()
    if paginas == 0:
        raise PdfDanado(detalle="El PDF no tiene páginas.")
    return paginas


def ejecutar_ocr(
    pdf_entrada: Path,
    pdf_salida: Path,
    idioma: str = "spa",
    progreso=None,
) -> None:
    """Ejecuta OCRmyPDF sobre `pdf_entrada` y escribe `pdf_salida`.

    - `--skip-text`: si una página ya tiene texto, se conserva (PDFs mixtos).
    - deskew + rotate: endereza escaneos torcidos o girados.
    - `progreso`: callable(str) opcional para informar estado a la GUI.
    """
    verificar_ocr(idioma)
    import ocrmypdf
    from ocrmypdf.exceptions import (
        EncryptedPdfError,
        InputFileError,
        MissingDependencyError,
    )

    if progreso:
        progreso("Ejecutando OCR (Tesseract, idioma español)…")
    log.info("OCR iniciado: %s (%s)", pdf_entrada.name, idioma)
    try:
        ocrmypdf.ocr(
            str(pdf_entrada),
            str(pdf_salida),
            language=idioma,
            skip_text=True,
            deskew=True,
            rotate_pages=True,
            optimize=1,
            progress_bar=False,
        )
    except EncryptedPdfError as e:
        raise PdfProtegido(detalle=str(e))
    except InputFileError as e:
        raise PdfDanado(detalle=str(e))
    except MissingDependencyError as e:
        # Ghostscript u otra dependencia del sistema ausente
        from app.utils.errores import ErrorAplicacion

        raise ErrorAplicacion(
            "Falta una dependencia del sistema para el OCR (posiblemente "
            "Ghostscript).\n\nInstalala desde "
            "https://ghostscript.com/releases/gsdnld.html y reiniciá.",
            detalle=str(e),
        )
    except MemoryError as e:
        raise MemoriaInsuficiente(detalle=str(e))
    log.info("OCR terminado: %s", pdf_salida.name)


def copiar_original(pdf: Path, carpeta_proyecto: Path) -> Path:
    """Copia el PDF original intacto a la carpeta del proyecto."""
    carpeta_proyecto.mkdir(parents=True, exist_ok=True)
    destino = carpeta_proyecto / "original.pdf"
    shutil.copy2(pdf, destino)
    return destino
