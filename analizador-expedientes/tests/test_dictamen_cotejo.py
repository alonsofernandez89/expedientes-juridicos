"""Pruebas del cotejo determinístico requisito ↔ expediente."""

from app.dictamen.cotejo import (
    CUMPLE,
    FALTA,
    NO_CONSTA,
    cotejar_requisitos,
    resumen_cumplimiento,
)
from app.dictamen.requisitos import Requisito


def _requisito(indice, texto, palabras_clave, tipo_documento=None):
    return Requisito(
        indice=indice, articulo=f"Art. {indice + 1}", texto=texto,
        palabras_clave=palabras_clave, tipo_documento=tipo_documento,
    )


def test_cumple_por_tipo_de_documento_detectado():
    requisito = _requisito(0, "deberá acompañarse informe técnico", [], "Informe técnico")
    documentos = [{"tipo": "Informe técnico", "referencia": "Informe N° 3", "pagina": 7}]
    resultado = cotejar_requisitos([requisito], paginas=[], documentos=documentos)[0]
    assert resultado.estado == CUMPLE
    assert resultado.pagina == 7


def test_falta_si_no_hay_documento_del_tipo_ni_palabras_clave():
    requisito = _requisito(0, "deberá acompañarse dictamen jurídico", [], "Dictamen")
    resultado = cotejar_requisitos([requisito], paginas=["texto sin relación"], documentos=[])[0]
    assert resultado.estado == FALTA
    assert resultado.pagina is None


def test_cumple_por_palabras_clave_cuando_no_hay_tipo_de_documento():
    requisito = _requisito(0, "x", ["presupuesto", "oficial", "estimado"])
    paginas = ["texto irrelevante", "aquí consta el presupuesto oficial estimado del proyecto"]
    resultado = cotejar_requisitos([requisito], paginas, documentos=[])[0]
    assert resultado.estado == CUMPLE
    assert resultado.pagina == 2


def test_no_consta_con_coincidencia_parcial():
    requisito = _requisito(0, "x", ["presupuesto", "oficial", "estimado", "aprobado"])
    paginas = ["se menciona el presupuesto solamente, nada más"]
    resultado = cotejar_requisitos([requisito], paginas, documentos=[])[0]
    assert resultado.estado == NO_CONSTA


def test_falta_sin_ninguna_coincidencia():
    requisito = _requisito(0, "x", ["presupuesto", "oficial"])
    resultado = cotejar_requisitos([requisito], ["texto totalmente distinto"], [])[0]
    assert resultado.estado == FALTA


def test_documento_de_otro_tipo_cae_a_busqueda_por_palabras_clave():
    requisito = _requisito(0, "x", ["dictamen", "previo"], "Dictamen")
    documentos = [{"tipo": "Nota", "referencia": "Nota 1", "pagina": 2}]
    paginas = ["consta el dictamen previo del área jurídica"]
    resultado = cotejar_requisitos([requisito], paginas, documentos)[0]
    assert resultado.estado == CUMPLE
    assert resultado.pagina == 1


def test_resumen_cumplimiento_cuenta_por_estado():
    requisitos = [
        _requisito(0, "a", ["alfa", "beta"]),
        _requisito(1, "b", ["gamma"]),
        _requisito(2, "c", ["delta", "epsilon"]),
    ]
    paginas = ["alfa beta", "no hay nada aquí", "delta"]
    resultados = cotejar_requisitos(requisitos, paginas, [])
    resumen = resumen_cumplimiento(resultados)
    assert resumen["total"] == 3
    assert resumen[CUMPLE] + resumen[NO_CONSTA] + resumen[FALTA] == 3
