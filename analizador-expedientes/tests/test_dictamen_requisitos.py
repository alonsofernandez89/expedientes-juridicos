"""Pruebas de extracción de requisitos normativos."""

from app.dictamen.requisitos import extraer_requisitos

NORMATIVA = """
Artículo 1°. Objeto. La presente reglamenta el procedimiento de contrataciones.

Artículo 5°. Documentación obligatoria. El expediente deberá contener el
informe técnico previo a la adjudicación. Asimismo, es obligatorio acompañar
el presupuesto oficial estimado. La simple mención del organismo no genera
obligaciones adicionales.

Artículo 8°. Dictamen jurídico. Se requiere dictamen jurídico previo a todo
acto administrativo que comprometa fondos públicos. No podrá dictarse
resolución sin dictamen jurídico previo.

Artículo 12°. Disposiciones generales. El presente reglamento entrará en
vigencia a partir de su publicación.
"""


def test_extraer_requisitos_detecta_obligaciones():
    requisitos = extraer_requisitos(NORMATIVA)
    textos = [r.texto for r in requisitos]
    assert any("informe técnico" in t.lower() for t in textos)
    assert any("presupuesto oficial" in t.lower() for t in textos)
    assert any("dictamen jurídico previo" in t.lower() for t in textos)
    # el artículo puramente declarativo (1° y 12°) no genera requisitos
    assert not any("entrará en vigencia" in t.lower() for t in textos)
    assert not any("reglamenta el procedimiento" in t.lower() for t in textos)


def test_requisitos_asocian_el_articulo_correcto():
    requisitos = extraer_requisitos(NORMATIVA)
    por_informe = next(r for r in requisitos if "informe técnico" in r.texto.lower())
    assert por_informe.articulo == "Art. 5"
    por_dictamen = next(r for r in requisitos if "todo\nacto" in r.texto.lower() or "todo acto" in r.texto.lower())
    assert por_dictamen.articulo == "Art. 8"


def test_requisitos_detectan_tipo_de_documento():
    requisitos = extraer_requisitos(NORMATIVA)
    por_informe = next(r for r in requisitos if "informe técnico" in r.texto.lower())
    assert por_informe.tipo_documento == "Informe técnico"
    por_presupuesto = next(r for r in requisitos if "presupuesto oficial" in r.texto.lower())
    assert por_presupuesto.tipo_documento == "Presupuesto"


def test_requisitos_tienen_palabras_clave():
    requisitos = extraer_requisitos(NORMATIVA)
    for r in requisitos:
        assert r.palabras_clave  # ninguna oración de obligación queda sin claves


def test_extraer_requisitos_texto_vacio():
    assert extraer_requisitos("") == []
    assert extraer_requisitos("   ") == []


def test_extraer_requisitos_sin_articulos_numerados():
    texto = "El interesado deberá presentar nota de solicitud dirigida al organismo."
    requisitos = extraer_requisitos(texto)
    assert len(requisitos) == 1
    assert requisitos[0].articulo == "s/n"
