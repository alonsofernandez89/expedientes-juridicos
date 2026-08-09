"""Detección de tipos de documentos dentro del expediente.

Clasificación por reglas: se buscan menciones al inicio de línea o con
número de instrumento (p. ej. "Resolución N° 123/2024"), que es como los
documentos se identifican a sí mismos dentro de un expediente.
"""

import re

# tipo → patrones. Se compilan con inicio flexible: comienzo de línea o
# tras "la/el", y admiten abreviaturas usuales.
TIPOS_DOCUMENTO: dict[str, list[str]] = {
    "Nota": [r"\bnota\b"],
    "Resolución": [r"\bresoluci[oó]n\b", r"\bres\.\s*n"],
    "Decreto": [r"\bdecretos?\b", r"\bdec\.\s*n"],
    "Contrato": [r"\bcontratos?\b"],
    "Convenio": [r"\bconvenios?\b"],
    "Dictamen": [r"\bdict[aá]men(?:es)?\b"],
    "Informe técnico": [r"\binformes?\s+t[eé]cnicos?\b", r"\binformes?\b"],
    "Presupuesto": [r"\bpresupuestos?\b"],
    "Factura": [r"\bfacturas?\b"],
    "Orden de compra": [r"\b[oó]rden(?:es)?\s+de\s+compra\b", r"\bo\.?c\.?\s*n[°ºo]"],
    "Acta": [r"\bactas?\b"],
    "Documentación contable": [
        r"\brecibos?\b", r"\bbalances?\b", r"\basientos?\s+contables?\b",
        r"\brendici[oó]n(?:es)?\s+de\s+cuentas?\b", r"\bcomprobantes?\b",
    ],
}

# Un documento "se presenta" si el tipo aparece al inicio de línea, o
# acompañado de un número de instrumento, o de un verbo de incorporación.
_NUMERO = r"(?:\s+n[°ºo.]*\s*[\w./-]*\d)"
_VERBOS = (
    r"(?:se\s+(?:adjunta|incorpora|agrega|acompaña|eleva|emite|suscribe|celebra|labra)\s+"
    r"(?:a\s+fs\.?\s*\d+\s+)?(?:el|la|los|las)?\s*)"
)

_PATRONES: list[tuple[str, re.Pattern]] = []
for tipo, bases in TIPOS_DOCUMENTO.items():
    for base in bases:
        _PATRONES.append((
            tipo,
            re.compile(
                rf"(?:^\s*{base}{_NUMERO}?|^\s*{base}\s*:|{base}{_NUMERO}|{_VERBOS}{base})",
                re.IGNORECASE | re.MULTILINE,
            ),
        ))

# "Informe técnico" tiene un patrón genérico ("informe"); si matchea el
# específico no queremos duplicar con el genérico en la misma línea.
LARGO_REFERENCIA = 120


def detectar_documentos_en_pagina(texto: str, pagina: int) -> list[dict]:
    """Documentos {tipo, referencia, pagina} detectados en una página."""
    detectados = []
    lineas_por_tipo: dict[str, set[str]] = {}
    for tipo, patron in _PATRONES:
        for m in patron.finditer(texto):
            # línea completa donde se detectó, como referencia legible
            inicio_linea = texto.rfind("\n", 0, m.start()) + 1
            fin_linea = texto.find("\n", m.end())
            if fin_linea == -1:
                fin_linea = len(texto)
            linea = " ".join(texto[inicio_linea:fin_linea].split())
            linea = linea[:LARGO_REFERENCIA]
            if linea in lineas_por_tipo.setdefault(tipo, set()):
                continue
            lineas_por_tipo[tipo].add(linea)
            detectados.append({"tipo": tipo, "referencia": linea, "pagina": pagina})
    return detectados


def detectar_documentos(paginas: list[str]) -> list[dict]:
    """Recorre todo el expediente y devuelve los documentos detectados."""
    documentos = []
    for i, texto in enumerate(paginas, start=1):
        documentos.extend(detectar_documentos_en_pagina(texto, i))
    return documentos


def resumen_por_tipo(documentos: list[dict]) -> dict[str, list[dict]]:
    """Agrupa los documentos por tipo (para la pestaña y la exportación)."""
    grupos: dict[str, list[dict]] = {}
    for doc in documentos:
        grupos.setdefault(doc["tipo"], []).append(doc)
    return grupos
