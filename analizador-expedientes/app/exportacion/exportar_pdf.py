"""Exportación del informe a PDF con ReportLab."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.exportacion.datos_informe import (
    Informe,
    montos_desde_resumen,
    separar_secciones,
)

_AZUL = colors.HexColor("#1F3B5C")


def _escapar(texto: str) -> str:
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base["Title"], textColor=_AZUL, fontSize=26
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], textColor=_AZUL, spaceBefore=18
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], textColor=_AZUL, spaceBefore=12
        ),
        "normal": ParagraphStyle(
            "normal", parent=base["BodyText"], fontSize=10.5, leading=14
        ),
        "centrado": ParagraphStyle(
            "centrado", parent=base["BodyText"], alignment=1, fontSize=12
        ),
    }


def _pie_de_pagina(expediente: str):
    def dibujar(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, f"Expediente: {expediente}")
        canvas.drawCentredString(
            A4[0] / 2, 1.2 * cm,
            f"Análisis generado localmente — Página {doc.page}",
        )
        canvas.restoreState()

    return dibujar


def _tabla(encabezados: list[str], filas: list[list[str]], estilos, anchos=None):
    datos = [[
        Paragraph(f'<b><font color="white">{_escapar(e)}</font></b>', estilos["normal"])
        for e in encabezados
    ]]
    for fila in filas:
        datos.append([Paragraph(_escapar(str(c)), estilos["normal"]) for c in fila])
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
    ]))
    return t


def _markdown_simple(texto: str, estilos, flujo: list) -> None:
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        if limpia.startswith(("-", "*", "•")):
            flujo.append(Paragraph(
                "• " + _escapar(limpia.lstrip("-*• ").strip()), estilos["normal"]
            ))
        else:
            flujo.append(Paragraph(_escapar(limpia.replace("**", "")), estilos["normal"]))


def exportar_pdf(informe: Informe, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    estilos = _estilos()
    doc = SimpleDocTemplate(
        str(ruta), pagesize=A4,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        title=informe.titulo,
    )
    flujo: list = []

    # Carátula
    flujo.append(Spacer(1, 6 * cm))
    flujo.append(Paragraph(_escapar(informe.titulo), estilos["titulo"]))
    flujo.append(Spacer(1, 0.8 * cm))
    flujo.append(Paragraph(_escapar(informe.expediente), estilos["centrado"]))
    for clave, etiqueta in (
        ("fecha_analisis", "Fecha de análisis"),
        ("total_paginas", "Páginas del expediente"),
        ("modelo", "Modelo local utilizado"),
    ):
        if clave in informe.metadatos:
            flujo.append(Paragraph(
                f"{etiqueta}: {_escapar(str(informe.metadatos[clave]))}",
                estilos["centrado"],
            ))
    flujo.append(PageBreak())

    # Resumen general
    flujo.append(Paragraph("Resumen general del expediente", estilos["h1"]))
    for titulo, cuerpo in separar_secciones(informe.resumen_general):
        if titulo:
            flujo.append(Paragraph(_escapar(titulo), estilos["h2"]))
        if cuerpo:
            _markdown_simple(cuerpo, estilos, flujo)

    if informe.cronologia:
        flujo.append(Paragraph("Cronología del expediente", estilos["h1"]))
        flujo.append(_tabla(
            ["Fecha", "Hecho / contexto", "Página"],
            [[e.get("fecha_texto") or e.get("fecha_iso", ""),
              e.get("contexto", ""), e.get("pagina", "")] for e in informe.cronologia],
            estilos, anchos=[3.2 * cm, 10.8 * cm, 2 * cm],
        ))

    montos = montos_desde_resumen(informe.resumen_general)
    if montos:
        flujo.append(Paragraph("Montos detectados", estilos["h1"]))
        flujo.append(_tabla(["Monto / concepto"], [[m] for m in montos], estilos))

    if informe.documentos:
        flujo.append(Paragraph("Documentación detectada", estilos["h1"]))
        flujo.append(_tabla(
            ["Tipo", "Referencia", "Página"],
            [[d["tipo"], d["referencia"], d["pagina"]] for d in informe.documentos],
            estilos, anchos=[3.5 * cm, 10.5 * cm, 2 * cm],
        ))

    if informe.resumenes_parciales:
        flujo.append(PageBreak())
        flujo.append(Paragraph("Anexo: resúmenes por bloque", estilos["h1"]))
        for parcial in informe.resumenes_parciales:
            for titulo, cuerpo in separar_secciones(parcial):
                if titulo:
                    flujo.append(Paragraph(_escapar(titulo), estilos["h2"]))
                if cuerpo:
                    _markdown_simple(cuerpo, estilos, flujo)

    doc.build(
        flujo,
        onFirstPage=_pie_de_pagina(informe.expediente),
        onLaterPages=_pie_de_pagina(informe.expediente),
    )
