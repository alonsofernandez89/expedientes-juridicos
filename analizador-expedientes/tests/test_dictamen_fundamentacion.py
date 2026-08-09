"""Pruebas de la redacción del dictamen con Ollama (simulado, sin red)."""

from unittest.mock import MagicMock

from app.almacenamiento.base_datos import BaseDatosProyecto
from app.dictamen.cotejo import cotejar_requisitos
from app.dictamen.fundamentacion import generar_redaccion
from app.dictamen.requisitos import Requisito
from app.resumen.cliente_ollama import ClienteOllama


def _resultados():
    requisitos = [
        Requisito(0, "Art. 5", "deberá constar informe técnico", ["informe", "tecnico"], "Informe técnico"),
        Requisito(1, "Art. 8", "es obligatorio el dictamen previo", ["dictamen", "previo"], "Dictamen"),
    ]
    documentos = [{"tipo": "Informe técnico", "referencia": "Informe 1", "pagina": 4}]
    return cotejar_requisitos(requisitos, paginas=["nada relevante"], documentos=documentos)


def _cliente_simulado():
    cliente = MagicMock(spec=ClienteOllama)
    cliente.generar.side_effect = lambda modelo, prompt, sistema="": f"TEXTO({prompt[-40:]})"
    return cliente


def test_generar_redaccion_devuelve_considerando_y_resuelve(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        cliente = _cliente_simulado()
        redaccion = generar_redaccion(cliente, db, "llama3.2", _resultados())
        assert "considerando" in redaccion and "resuelve" in redaccion
        assert cliente.generar.call_count == 2


def test_generar_redaccion_usa_cache(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        cliente = _cliente_simulado()
        resultados = _resultados()
        primera = generar_redaccion(cliente, db, "llama3.2", resultados)
        segunda = generar_redaccion(cliente, db, "llama3.2", resultados)
        assert primera == segunda
        assert cliente.generar.call_count == 2  # no se llamó de nuevo


def test_generar_redaccion_no_inventa_datos_fuera_del_cotejo():
    from app.dictamen.fundamentacion import prompt_considerando

    resultados = _resultados()
    prompt = prompt_considerando(resultados)
    assert "informe técnico" in prompt.lower() or "informe tecnico" in prompt.lower()
    assert "pág. 4" in prompt
    assert "NO CUMPLE" in prompt or "NO SE ENCONTRÓ" in prompt
