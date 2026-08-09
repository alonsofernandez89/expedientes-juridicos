"""Pruebas de extracción (con PDFs generados al vuelo) y de limpieza."""

import json

import fitz
import pytest

from app.extraccion.extractor import (
    extraer_paginas,
    guardar_json,
    guardar_txt,
    verificar_texto_detectado,
)
from app.extraccion.limpieza import limpiar_paginas
from app.ocr.motor_ocr import validar_pdf
from app.utils.errores import OcrSinTexto, PdfDanado


def _crear_pdf(ruta, textos):
    doc = fitz.open()
    for t in textos:
        pagina = doc.new_page()
        pagina.insert_text((72, 72), t)
    doc.save(str(ruta))
    doc.close()


def test_validar_y_extraer_pdf(tmp_path):
    ruta = tmp_path / "doc.pdf"
    _crear_pdf(ruta, ["Primera página", "Segunda página"])
    assert validar_pdf(ruta) == 2
    paginas = extraer_paginas(ruta)
    assert len(paginas) == 2
    assert "Primera" in paginas[0]
    assert "Segunda" in paginas[1]


def test_pdf_danado(tmp_path):
    ruta = tmp_path / "roto.pdf"
    ruta.write_bytes(b"esto no es un pdf")
    with pytest.raises(PdfDanado):
        validar_pdf(ruta)


def test_ocr_sin_texto():
    with pytest.raises(OcrSinTexto):
        verificar_texto_detectado(["", "  ", "\n"])
    verificar_texto_detectado(["texto suficiente para pasar la validación"])


def test_guardar_txt_y_json(tmp_path):
    paginas = ["uno", "dos"]
    txt, js = tmp_path / "t.txt", tmp_path / "t.json"
    guardar_txt(paginas, txt)
    guardar_json(paginas, js)
    contenido = txt.read_text(encoding="utf-8")
    assert "===== Página 1 =====" in contenido and "dos" in contenido
    datos = json.loads(js.read_text(encoding="utf-8"))
    assert datos["total_paginas"] == 2
    assert datos["paginas"][1] == {"numero": 2, "texto": "dos"}


def _paginas_con_ruido(n=10):
    """Simula un expediente con encabezado, pie, sello y nº de expediente."""
    paginas = []
    for i in range(1, n + 1):
        paginas.append(
            "MINISTERIO DE OBRAS PÚBLICAS\n"
            "Dirección General de Asuntos Jurídicos\n"
            f"EXPTE. N° 4567/2023\n"
            f"Contenido único de la página {i}: se informa sobre el avance "
            f"de la obra en la etapa {i} con novedades particulares.\n"
            "ES COPIA FIEL DEL ORIGINAL\n"
            f"Folio {i}\n"
            "Av. Siempreviva 742 - Tel 555-0123"
        )
    return paginas


def test_limpieza_detecta_encabezados_pies_y_sellos():
    resultado = limpiar_paginas(_paginas_con_ruido())
    limpia = resultado.paginas_limpias[0]
    assert "MINISTERIO" not in limpia
    assert "Siempreviva" not in limpia
    assert "ES COPIA FIEL" not in limpia
    assert "EXPTE" not in limpia
    assert "Contenido único de la página 1" in limpia
    assert resultado.patrones_detectados["encabezados"]
    assert resultado.patrones_detectados["pies"]
    # lo eliminado queda registrado para auditoría
    assert any("MINISTERIO" in l for l in resultado.eliminadas_por_pagina[0])


def test_limpieza_detecta_paginas_vacias():
    paginas = _paginas_con_ruido(8)
    # página que solo tiene ruido → debe quedar marcada como vacía
    paginas.append("MINISTERIO DE OBRAS PÚBLICAS\nES COPIA FIEL DEL ORIGINAL")
    paginas.append("")
    resultado = limpiar_paginas(paginas)
    assert 9 in resultado.paginas_vacias
    assert 10 in resultado.paginas_vacias
    assert 1 not in resultado.paginas_vacias


def test_limpieza_conservadora_con_pocas_paginas():
    """Con 2 páginas nada alcanza el umbral: no se elimina contenido."""
    paginas = ["Nota al director sobre el tema A", "Respuesta del director"]
    resultado = limpiar_paginas(paginas)
    assert resultado.paginas_limpias == paginas
    assert resultado.eliminadas_por_pagina == [[], []]


def test_limpieza_documento_vacio():
    resultado = limpiar_paginas([])
    assert resultado.paginas_limpias == []
