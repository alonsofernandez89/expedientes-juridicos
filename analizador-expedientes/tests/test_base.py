"""Pruebas de config y almacenamiento."""

import json

from app.almacenamiento.base_datos import BaseDatosProyecto, hash_bloque
from app.config.settings import Configuracion


def test_configuracion_valida_rango_de_bloque(tmp_path, monkeypatch):
    monkeypatch.setattr(
        Configuracion, "ruta_archivo", classmethod(lambda cls: tmp_path / "c.json")
    )
    c = Configuracion(paginas_por_bloque=99)
    c.guardar()
    recargada = Configuracion.cargar()
    assert recargada.paginas_por_bloque == 30  # tope superior
    c2 = Configuracion(paginas_por_bloque=2)
    c2.validar()
    assert c2.paginas_por_bloque == 10  # tope inferior


def test_configuracion_claude_desactivado_por_defecto():
    assert Configuracion().revision_claude_habilitada is False


def test_configuracion_ignora_json_corrupto(tmp_path, monkeypatch):
    ruta = tmp_path / "c.json"
    ruta.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(Configuracion, "ruta_archivo", classmethod(lambda cls: ruta))
    c = Configuracion.cargar()
    assert c.modelo_resumen == "llama3.2"


def test_hash_bloque_cambia_con_modelo_y_version():
    h1 = hash_bloque("texto", "llama3.2", 1)
    assert h1 == hash_bloque("texto", "llama3.2", 1)
    assert h1 != hash_bloque("texto", "mistral", 1)
    assert h1 != hash_bloque("texto", "llama3.2", 2)
    assert h1 != hash_bloque("otro", "llama3.2", 1)


def test_base_datos_paginas_y_limpieza(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        db.guardar_paginas(["hola", "", "mundo"])
        db.actualizar_limpieza(2, "", True, ["ENCABEZADO X"])
        paginas = db.leer_paginas()
    assert [p["numero"] for p in paginas] == [1, 2, 3]
    assert paginas[1]["es_vacia"] == 1
    assert paginas[0]["texto"] == "hola"


def test_base_datos_cache_de_resumenes(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        h = hash_bloque("contenido", "llama3.2", 1)
        assert db.buscar_resumen(h) is None
        db.guardar_resumen(h, 0, 1, 15, "llama3.2", "resumen del bloque")
        assert db.buscar_resumen(h) == "resumen del bloque"
        todos = db.leer_resumenes()
    assert len(todos) == 1
    assert todos[0]["pagina_hasta"] == 15


def test_base_datos_cronologia_ordena_por_fecha(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        db.guardar_cronologia([
            {"fecha_iso": "2024-05-01", "fecha_texto": "1/5/2024", "contexto": "b", "pagina": 3},
            {"fecha_iso": "2023-01-15", "fecha_texto": "15/1/2023", "contexto": "a", "pagina": 9},
        ])
        eventos = db.leer_cronologia()
    assert [e["fecha_iso"] for e in eventos] == ["2023-01-15", "2024-05-01"]


def test_base_datos_meta_y_resumen_general(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        db.guardar_meta("nombre", "EXP-123/2024")
        assert db.leer_meta("nombre") == "EXP-123/2024"
        assert db.leer_meta("inexistente", "x") == "x"
        assert db.leer_resumen_general() is None
        db.guardar_resumen_general("llama3.2", "TEXTO FINAL")
        assert db.leer_resumen_general() == "TEXTO FINAL"
