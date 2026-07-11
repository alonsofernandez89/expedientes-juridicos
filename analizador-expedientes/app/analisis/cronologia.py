"""Cronología: extracción de fechas con contexto, ordenadas.

Detección por reglas (regex), determinista y sin costo de tokens. Formatos
usuales en documentos administrativos argentinos:

- 12/03/2024, 12-03-2024, 12.03.2024 (y años de 2 dígitos)
- 12 de marzo de 2024 / 1° de marzo del 2024
- Buenos Aires, 12 de marzo de 2024
"""

import re
from datetime import date

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_RE_NUMERICA = re.compile(
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b"
)
_RE_LITERAL = re.compile(
    r"\b(\d{1,2})[°º]?\s+de\s+(" + "|".join(MESES) + r")\s+(?:de[l]?\s+)?(\d{4})\b",
    re.IGNORECASE,
)

# Rango razonable para expedientes; descarta falsos positivos del OCR
ANIO_MIN, ANIO_MAX = 1950, date.today().year + 2

LARGO_CONTEXTO = 160


def _normalizar_anio(anio: int) -> int | None:
    if anio < 100:
        anio += 2000 if anio <= (date.today().year % 100) + 1 else 1900
    return anio if ANIO_MIN <= anio <= ANIO_MAX else None


def _crear_fecha(dia: int, mes: int, anio: int) -> date | None:
    anio_ok = _normalizar_anio(anio)
    if anio_ok is None:
        return None
    try:
        return date(anio_ok, mes, dia)
    except ValueError:
        return None


def _contexto(texto: str, inicio: int, fin: int) -> str:
    """Fragmento alrededor de la fecha, recortado a límites de palabra."""
    desde = max(0, inicio - LARGO_CONTEXTO // 2)
    hasta = min(len(texto), fin + LARGO_CONTEXTO // 2)
    fragmento = " ".join(texto[desde:hasta].split())
    return fragmento.strip()


def extraer_fechas_de_pagina(texto: str, pagina: int) -> list[dict]:
    """Eventos {fecha_iso, fecha_texto, contexto, pagina} de una página."""
    eventos = []
    vistos = set()

    for m in _RE_NUMERICA.finditer(texto):
        dia, mes, anio = (int(g) for g in m.groups())
        fecha = _crear_fecha(dia, mes, anio)
        if fecha is None:
            # formato mm/dd invertido poco común acá; probamos por las dudas
            fecha = _crear_fecha(mes, dia, anio) if mes <= 12 else None
            if fecha is None:
                continue
        clave = (fecha.isoformat(), m.group(0))
        if clave in vistos:
            continue
        vistos.add(clave)
        eventos.append({
            "fecha_iso": fecha.isoformat(),
            "fecha_texto": m.group(0),
            "contexto": _contexto(texto, m.start(), m.end()),
            "pagina": pagina,
        })

    for m in _RE_LITERAL.finditer(texto):
        dia = int(m.group(1))
        mes = MESES[m.group(2).lower()]
        fecha = _crear_fecha(dia, mes, int(m.group(3)))
        if fecha is None:
            continue
        clave = (fecha.isoformat(), m.group(0))
        if clave in vistos:
            continue
        vistos.add(clave)
        eventos.append({
            "fecha_iso": fecha.isoformat(),
            "fecha_texto": m.group(0),
            "contexto": _contexto(texto, m.start(), m.end()),
            "pagina": pagina,
        })

    return eventos


def construir_cronologia(paginas: list[str]) -> list[dict]:
    """Cronología completa del expediente, ordenada por fecha y página."""
    eventos = []
    for i, texto in enumerate(paginas, start=1):
        eventos.extend(extraer_fechas_de_pagina(texto, i))
    eventos.sort(key=lambda e: (e["fecha_iso"], e["pagina"]))
    return eventos
