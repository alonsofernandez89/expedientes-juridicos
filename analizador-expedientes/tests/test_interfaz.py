"""Prueba de humo de la interfaz (offscreen, sin display real)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pyside = pytest.importorskip("PySide6", reason="PySide6 no instalado")


@pytest.fixture(scope="module")
def app_qt():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_ventana_principal_se_construye(app_qt, tmp_path, monkeypatch):
    from app.config.settings import Configuracion

    monkeypatch.setattr(
        Configuracion, "ruta_archivo", classmethod(lambda cls: tmp_path / "c.json")
    )
    from app.interfaz.ventana_principal import VentanaPrincipal

    ventana = VentanaPrincipal()
    assert ventana.pestanas.count() == 8
    titulos = [ventana.pestanas.tabText(i) for i in range(ventana.pestanas.count())]
    assert "Cronología" in titulos
    assert "Documentos detectados" in titulos
    assert "Revisión con Claude" in titulos
    # la revisión con Claude arranca deshabilitada
    assert ventana.pestana_claude.habilitar.isChecked() is False
    assert ventana.pestana_claude.boton_revisar.isEnabled() is False
    # esperar a que termine el worker de consulta a Ollama (no disponible acá)
    for w in list(ventana._workers):
        w.wait(15000)
    app_qt.processEvents()
    ventana.close()


def test_pestanas_muestran_datos(app_qt):
    from app.interfaz.pestanas import (
        PestanaCronologia,
        PestanaDocumentos,
        PestanaTexto,
    )

    texto = PestanaTexto()
    texto.actualizar(["página uno", "página dos"], ["uno limpio", ""], [2])
    assert texto._lista.count() == 2
    assert "(vacía)" in texto._lista.item(1).text()

    crono = PestanaCronologia()
    crono.actualizar([
        {"fecha_iso": "2023-01-05", "fecha_texto": "05/01/2023", "contexto": "inicio", "pagina": 1}
    ])
    assert crono._tabla.rowCount() == 1

    docs = PestanaDocumentos()
    docs.actualizar([
        {"tipo": "Nota", "referencia": "NOTA 1", "pagina": 1},
        {"tipo": "Acta", "referencia": "ACTA 2", "pagina": 5},
    ])
    assert docs._tabla.rowCount() == 2
    docs._filtro.setCurrentText("Acta")
    assert docs._tabla.rowCount() == 1
