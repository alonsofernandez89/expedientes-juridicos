"""Pruebas de bloques y resumidor (Ollama simulado, sin red)."""

from unittest.mock import MagicMock

import pytest

from app.almacenamiento.base_datos import BaseDatosProyecto
from app.bloques.divisor import dividir_en_bloques
from app.resumen.cliente_ollama import ClienteOllama
from app.resumen.resumidor import Resumidor
from app.utils.errores import ModeloNoInstalado, OllamaNoDisponible


def _paginas(n):
    return [f"Texto de la página {i}" for i in range(1, n + 1)]


def test_dividir_en_bloques_basico():
    bloques = dividir_en_bloques(_paginas(35), 15)
    assert len(bloques) == 3
    assert (bloques[0].pagina_desde, bloques[0].pagina_hasta) == (1, 15)
    assert (bloques[2].pagina_desde, bloques[2].pagina_hasta) == (31, 35)
    assert "[Página 31]" in bloques[2].texto
    assert "Bloque 3" in bloques[2].etiqueta


def test_dividir_respeta_limites_configurables():
    # fuera de rango: se ajusta a 10–30
    assert dividir_en_bloques(_paginas(20), 5)[0].pagina_hasta == 10
    assert dividir_en_bloques(_paginas(90), 100)[0].pagina_hasta == 30


def test_dividir_omite_paginas_vacias_sin_romper_numeracion():
    bloques = dividir_en_bloques(_paginas(12), 10, paginas_vacias={2, 3})
    assert "[Página 2]" not in bloques[0].texto
    assert "[Página 4]" in bloques[0].texto
    # el segundo bloque sigue arrancando en la página 11
    assert bloques[1].pagina_desde == 11


def test_dividir_descarta_bloques_totalmente_vacios():
    paginas = ["" for _ in range(10)] + ["contenido real"]
    bloques = dividir_en_bloques(paginas, 10)
    assert len(bloques) == 1
    assert bloques[0].pagina_desde == 11


def _cliente_simulado():
    cliente = MagicMock(spec=ClienteOllama)
    cliente.generar.side_effect = lambda modelo, prompt, sistema="": (
        f"RESUMEN({prompt[:30]}...)"
    )
    return cliente


def test_resumidor_usa_cache(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        cliente = _cliente_simulado()
        r = Resumidor(cliente, db, "llama3.2")
        bloques = dividir_en_bloques(_paginas(25), 10)
        avisos = []
        primera = r.resumir_bloques(bloques, progreso=lambda i, t, c: avisos.append(c))
        assert len(primera) == 3
        assert cliente.generar.call_count == 3
        assert avisos == [False, False, False]

        # segunda pasada: todo sale de caché, sin llamadas nuevas
        avisos.clear()
        segunda = r.resumir_bloques(bloques, progreso=lambda i, t, c: avisos.append(c))
        assert segunda == primera
        assert cliente.generar.call_count == 3
        assert avisos == [True, True, True]


def test_resumidor_cambiar_modelo_invalida_cache(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        bloques = dividir_en_bloques(_paginas(10), 10)
        cliente = _cliente_simulado()
        Resumidor(cliente, db, "llama3.2").resumir_bloques(bloques)
        Resumidor(cliente, db, "mistral").resumir_bloques(bloques)
        assert cliente.generar.call_count == 2


def test_resumidor_cancelacion(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        cliente = _cliente_simulado()
        r = Resumidor(cliente, db, "llama3.2")
        bloques = dividir_en_bloques(_paginas(30), 10)
        hechos = r.resumir_bloques(bloques, cancelado=lambda: cliente.generar.call_count >= 1)
        assert len(hechos) == 1  # se detuvo pero conservó lo hecho


def test_resumen_general_se_persiste(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        cliente = _cliente_simulado()
        r = Resumidor(cliente, db, "llama3.2")
        texto = r.resumen_general(["parcial 1", "parcial 2"])
        assert texto.startswith("RESUMEN(")
        assert db.leer_resumen_general() == texto


def test_cliente_ollama_no_disponible():
    cliente = ClienteOllama("http://127.0.0.1:1")  # puerto cerrado
    assert cliente.esta_activo() is False
    with pytest.raises(OllamaNoDisponible):
        cliente.listar_modelos()


def test_cliente_ollama_modelo_faltante(monkeypatch):
    cliente = ClienteOllama()
    monkeypatch.setattr(cliente, "listar_modelos", lambda: ["llama3.2:latest"])
    # el modelo base coincide aunque el tag sea :latest → no debe fallar acá
    cliente._verificar_modelo("llama3.2")
    with pytest.raises(ModeloNoInstalado):
        cliente._verificar_modelo("mistral")
