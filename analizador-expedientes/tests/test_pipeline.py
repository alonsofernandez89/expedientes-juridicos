"""Prueba integral del pipeline (OCR y Ollama simulados)."""

import shutil
from unittest.mock import MagicMock, patch

import fitz

from app.config.settings import Configuracion
from app.pipeline import ProcesadorExpediente


def _crear_pdf(ruta, n=12):
    doc = fitz.open()
    for i in range(1, n + 1):
        pagina = doc.new_page()
        pagina.insert_text(
            (72, 72),
            f"MINISTERIO DE PRUEBAS\nNota N° {i}/2023 del 0{(i % 9) + 1}/03/2023\n"
            f"Contenido particular de la página {i} con detalles del trámite.",
        )
    doc.save(str(ruta))
    doc.close()


def _ocr_simulado(entrada, salida, idioma="spa", progreso=None):
    shutil.copy2(entrada, salida)  # el PDF de prueba ya tiene texto


def test_pipeline_completo(tmp_path):
    pdf = tmp_path / "expediente 4567-2023.pdf"
    _crear_pdf(pdf)
    config = Configuracion(
        carpeta_salida=str(tmp_path / "salida"), paginas_por_bloque=10
    )
    mensajes = []
    proc = ProcesadorExpediente(config, progreso=mensajes.append)

    with patch("app.pipeline.ejecutar_ocr", side_effect=_ocr_simulado):
        resultado = proc.procesar_hasta_texto(pdf)

    carpeta = resultado.carpeta
    assert (carpeta / "original.pdf").exists()
    assert (carpeta / "ocr.pdf").exists()
    assert (carpeta / "texto_completo.txt").exists()
    assert (carpeta / "texto_por_pagina.json").exists()
    assert (carpeta / "proyecto.db").exists()
    assert resultado.total_paginas == 12
    assert len(resultado.bloques) == 2
    assert resultado.cronologia  # fechas detectadas
    assert any(d["tipo"] == "Nota" for d in resultado.documentos)
    assert mensajes  # hubo avisos de progreso

    # resumen con Ollama simulado
    with patch("app.pipeline.ClienteOllama") as MockCliente:
        instancia = MagicMock()
        instancia.generar.side_effect = (
            lambda modelo, prompt, sistema="": f"RESUMEN({len(prompt)})"
        )
        MockCliente.return_value = instancia
        resultado = proc.resumir(resultado)

    assert len(resultado.resumenes_parciales) == 2
    assert resultado.resumen_general.startswith("RESUMEN(")

    # reapertura del proyecto sin reprocesar
    recargado = ProcesadorExpediente.cargar_proyecto(carpeta)
    assert recargado.total_paginas == 12
    assert recargado.resumen_general == resultado.resumen_general
    assert len(recargado.resumenes_parciales) == 2
    assert recargado.cronologia


def test_cargar_proyecto_inexistente(tmp_path):
    assert ProcesadorExpediente.cargar_proyecto(tmp_path) is None
