"""Pruebas de la integración opcional con Claude (sin red)."""

import pytest

from app.claude_api import cliente_claude
from app.claude_api.estimador_tokens import estimar_consulta, estimar_tokens
from app.config.settings import VAR_CLAVE_CLAUDE
from app.utils.errores import ClaveApiFaltante, ErrorAplicacion


def test_estimador_de_tokens():
    assert estimar_tokens("") == 1
    assert estimar_tokens("a" * 3500) == 1000
    est = estimar_consulta("a" * 3500, "claude-opus-4-8", tokens_salida_previstos=1000)
    assert est.tokens_entrada == 1000
    # 1000 in * $5/M + 1000 out * $25/M = $0.03
    assert est.costo_estimado_usd == pytest.approx(0.03)
    assert "Tokens de entrada" in est.resumen()


def test_preparar_envio_solo_datos_destilados():
    envio = cliente_claude.preparar_envio(
        pregunta="¿Hay inconsistencias en los montos?",
        modelo="claude-opus-4-8",
        resumenes_parciales=["resumen bloque 1"],
        resumen_general="resumen general",
        cronologia=[{"fecha_iso": "2023-01-05", "contexto": "inicio", "pagina": 1}],
        documentos=[{"tipo": "Nota", "referencia": "NOTA 1", "pagina": 1}],
    )
    assert "resumen bloque 1" in envio.contenido
    assert "CRONOLOGÍA" in envio.contenido
    assert len(envio.secciones_incluidas) == 4
    assert envio.estimacion.tokens_entrada > 0
    assert envio.confirmado is False  # nunca confirmado por defecto


def test_texto_completo_requiere_autorizacion_expresa():
    with pytest.raises(ErrorAplicacion):
        cliente_claude.preparar_envio(
            pregunta="x",
            modelo="claude-opus-4-8",
            resumen_general="r",
            texto_completo="contenido del pdf",
            permitir_texto_completo=False,
        )
    envio = cliente_claude.preparar_envio(
        pregunta="x",
        modelo="claude-opus-4-8",
        resumen_general="r",
        texto_completo="contenido del pdf",
        permitir_texto_completo=True,
    )
    assert any("TEXTO COMPLETO" in s for s in envio.secciones_incluidas)


def test_preparar_envio_sin_datos_falla():
    with pytest.raises(ErrorAplicacion):
        cliente_claude.preparar_envio(pregunta="x", modelo="claude-opus-4-8")


def test_enviar_exige_confirmacion():
    envio = cliente_claude.preparar_envio(
        pregunta="x", modelo="claude-opus-4-8", resumen_general="r"
    )
    with pytest.raises(ErrorAplicacion, match="confirmado"):
        cliente_claude.enviar(envio)


def test_enviar_exige_clave_en_entorno(monkeypatch):
    monkeypatch.delenv(VAR_CLAVE_CLAUDE, raising=False)
    assert cliente_claude.hay_clave_api() is False
    envio = cliente_claude.preparar_envio(
        pregunta="x", modelo="claude-opus-4-8", resumen_general="r"
    )
    envio.confirmado = True
    with pytest.raises(ClaveApiFaltante):
        cliente_claude.enviar(envio)
