"""Pruebas de cronología y detección de documentos."""

from app.analisis.cronologia import construir_cronologia, extraer_fechas_de_pagina
from app.analisis.documentos import detectar_documentos, resumen_por_tipo


def test_fechas_numericas_y_literales():
    texto = (
        "Buenos Aires, 15 de marzo de 2023. Visto el expediente iniciado "
        "el 02/01/2023 y la presentación del 28-12-2022..."
    )
    eventos = extraer_fechas_de_pagina(texto, 4)
    fechas = {e["fecha_iso"] for e in eventos}
    assert fechas == {"2023-03-15", "2023-01-02", "2022-12-28"}
    assert all(e["pagina"] == 4 for e in eventos)
    literal = next(e for e in eventos if e["fecha_iso"] == "2023-03-15")
    assert "15 de marzo de 2023" in literal["fecha_texto"]
    assert "expediente" in literal["contexto"]


def test_fechas_invalidas_descartadas():
    texto = "El 45/13/2023 no existe; tampoco 12/03/1810 (fuera de rango)."
    assert extraer_fechas_de_pagina(texto, 1) == []


def test_fecha_anio_dos_digitos():
    eventos = extraer_fechas_de_pagina("presentado el 05/06/19", 2)
    assert eventos[0]["fecha_iso"] == "2019-06-05"


def test_primero_de_mes_con_simbolo_de_grado():
    eventos = extraer_fechas_de_pagina("firmado el 1° de mayo de 2024", 1)
    assert eventos[0]["fecha_iso"] == "2024-05-01"


def test_cronologia_ordena_entre_paginas():
    paginas = [
        "Resolución del 10/06/2024",
        "Nota inicial del 05/01/2023",
    ]
    crono = construir_cronologia(paginas)
    assert [e["fecha_iso"] for e in crono] == ["2023-01-05", "2024-06-10"]
    assert [e["pagina"] for e in crono] == [2, 1]


def test_detecta_documentos_tipicos():
    paginas = [
        "NOTA N° 45/2023\nSe solicita la contratación del servicio.",
        "Se adjunta la factura N° 0001-00001234 y el presupuesto N° 7.",
        "RESOLUCIÓN N° 123/2023\nVISTO el Decreto N° 500/2021...",
        "Dictamen N° 89: no hay objeciones que formular.",
        "Se labra el acta de apertura de ofertas.\nOrden de compra N° 55.",
        "Informe técnico N° 3 de la Dirección de Obras.",
        "Se celebra el convenio marco y se suscribe el contrato de obra.",
    ]
    docs = detectar_documentos(paginas)
    tipos = {d["tipo"] for d in docs}
    for esperado in [
        "Nota", "Factura", "Presupuesto", "Resolución", "Decreto",
        "Dictamen", "Acta", "Orden de compra", "Informe técnico",
        "Convenio", "Contrato",
    ]:
        assert esperado in tipos, f"falta {esperado}"
    resol = next(d for d in docs if d["tipo"] == "Resolución")
    assert resol["pagina"] == 3
    assert "123/2023" in resol["referencia"]


def test_no_detecta_menciones_sueltas():
    """'nota' como verbo o mención casual no debe contarse como documento."""
    docs = detectar_documentos(["se nota una mejora en la obra ejecutada"])
    assert docs == []


def test_resumen_por_tipo_agrupa():
    docs = [
        {"tipo": "Nota", "referencia": "a", "pagina": 1},
        {"tipo": "Nota", "referencia": "b", "pagina": 5},
        {"tipo": "Acta", "referencia": "c", "pagina": 2},
    ]
    grupos = resumen_por_tipo(docs)
    assert len(grupos["Nota"]) == 2
    assert len(grupos["Acta"]) == 1
