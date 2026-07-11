"""Extracción de texto por página con PyMuPDF y generación de TXT/JSON."""

import json
from pathlib import Path

from app.utils.errores import OcrSinTexto, PdfDanado, PdfProtegido
from app.utils.registro import obtener_logger

log = obtener_logger("extraccion")


def extraer_paginas(ruta_pdf: Path) -> list[str]:
    """Devuelve el texto de cada página (lista 0-based; página 1 = índice 0)."""
    import fitz

    try:
        doc = fitz.open(str(ruta_pdf))
    except Exception as e:
        raise PdfDanado(detalle=str(e))
    try:
        if doc.needs_pass:
            raise PdfProtegido()
        paginas = [pagina.get_text("text") for pagina in doc]
    finally:
        doc.close()
    log.info("Texto extraído: %d páginas de %s", len(paginas), ruta_pdf.name)
    return paginas


def verificar_texto_detectado(paginas: list[str], minimo_caracteres: int = 20) -> None:
    """Lanza OcrSinTexto si el documento entero quedó sin texto útil."""
    total = sum(len(p.strip()) for p in paginas)
    if total < minimo_caracteres:
        raise OcrSinTexto(
            detalle=f"Solo se detectaron {total} caracteres en {len(paginas)} páginas."
        )


def guardar_txt(paginas: list[str], ruta: Path) -> None:
    """TXT completo con separadores de página legibles."""
    partes = []
    for i, texto in enumerate(paginas, start=1):
        partes.append(f"===== Página {i} =====\n{texto.rstrip()}\n")
    ruta.write_text("\n".join(partes), encoding="utf-8")


def guardar_json(paginas: list[str], ruta: Path) -> None:
    """JSON con el texto separado por páginas (número 1-based)."""
    datos = {
        "total_paginas": len(paginas),
        "paginas": [
            {"numero": i, "texto": texto} for i, texto in enumerate(paginas, start=1)
        ],
    }
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
