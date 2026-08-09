"""Estructura común del informe que consumen todos los exportadores."""

import re
from dataclasses import dataclass, field


@dataclass
class Informe:
    titulo: str                      # p. ej. "Análisis de expediente"
    expediente: str                  # número/carátula o nombre de archivo
    resumen_general: str             # Markdown con secciones ##
    resumenes_parciales: list[str] = field(default_factory=list)
    cronologia: list[dict] = field(default_factory=list)   # fecha_iso, fecha_texto, contexto, pagina
    documentos: list[dict] = field(default_factory=list)   # tipo, referencia, pagina
    metadatos: dict = field(default_factory=dict)          # total_paginas, modelo, fecha_analisis...


_RE_SECCION = re.compile(r"^\s{0,3}#{2,3}\s+(.+?)\s*$")


def separar_secciones(markdown: str) -> list[tuple[str, str]]:
    """Divide el resumen general en (título de sección, cuerpo).

    Si el texto no tiene encabezados Markdown, devuelve una única sección.
    """
    secciones: list[tuple[str, list[str]]] = []
    actual: list[str] = []
    titulo_actual = None
    for linea in markdown.splitlines():
        m = _RE_SECCION.match(linea)
        if m:
            if titulo_actual is not None or actual:
                secciones.append((titulo_actual or "", actual))
            titulo_actual = m.group(1)
            actual = []
        else:
            actual.append(linea)
    secciones.append((titulo_actual or "", actual))
    resultado = []
    for titulo, lineas in secciones:
        cuerpo = "\n".join(lineas).strip()
        if titulo or cuerpo:
            resultado.append((titulo, cuerpo))
    return resultado


def montos_desde_resumen(markdown: str) -> list[str]:
    """Extrae los ítems de la sección 'Montos' del resumen general."""
    for titulo, cuerpo in separar_secciones(markdown):
        if titulo.strip().lower().startswith("montos"):
            items = [
                l.lstrip("-*• ").strip()
                for l in cuerpo.splitlines()
                if l.strip().startswith(("-", "*", "•"))
            ]
            return [i for i in items if i]
    return []
