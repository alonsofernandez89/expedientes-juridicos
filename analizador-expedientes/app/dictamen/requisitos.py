"""Extracción de requisitos normativos por reglas (sin IA).

A partir del texto de una normativa (ley, decreto, reglamento, pliego),
detecta las oraciones que imponen una obligación ("deberá", "es
obligatorio", "se requiere", etc.) y las asocia al artículo del que
provienen. Es determinístico y auditable: cada requisito conserva la
oración original y el artículo, para que el usuario pueda verificar la
extracción contra el texto legal.
"""

import re
from dataclasses import dataclass, field

from app.analisis.documentos import TIPOS_DOCUMENTO

_MARCADORES_OBLIGACION = [
    r"deber[áa]n?\b",
    r"es\s+obligatori[oa]",
    r"se\s+requiere",
    r"resulta\s+indispensable",
    r"corresponde\s+acompa[ñn]ar",
    r"deber[áa]\s+constar",
    r"deber[áa]\s+contener",
    r"es\s+necesario",
    r"deber[áa]\s+acompa[ñn]ar",
    r"exigir[áa]",
    r"no\s+podr[áa]\s+.*sin",
]
_RE_OBLIGACION = re.compile("|".join(_MARCADORES_OBLIGACION), re.IGNORECASE)

# Línea que anuncia el inicio de un artículo (posiblemente seguida de su texto)
_RE_ARTICULO = re.compile(
    r"(?im)^\s*art(?:[íi]culo)?\.?\s*(\d+)\s*[°ºo]?\.?\s*[-–—:]?\s*"
)

_RE_SEPARADOR_ORACIONES = re.compile(r"(?<=[.;])\s+")

_PALABRAS_VACIAS = {
    "para", "cuando", "sobre", "entre", "desde", "hasta", "todo", "toda",
    "todos", "todas", "este", "esta", "estos", "estas", "cual", "cuales",
    "donde", "dicho", "dicha", "dichos", "dichas", "conforme", "acuerdo",
    "presente", "artículo", "articulo", "expediente", "administrativo",
}

MAXIMO_PALABRAS_CLAVE = 6
MINIMO_PALABRAS_ORACION = 4
LARGO_MAXIMO_ANUNCIO_ARTICULO = 60


@dataclass
class Requisito:
    indice: int
    articulo: str
    texto: str
    palabras_clave: list[str] = field(default_factory=list)
    tipo_documento: str | None = None


def _dividir_oraciones(texto: str) -> list[str]:
    return [o.strip() for o in _RE_SEPARADOR_ORACIONES.split(texto) if o.strip()]


def _palabras_clave(oracion: str, maximo: int = MAXIMO_PALABRAS_CLAVE) -> list[str]:
    palabras = re.findall(r"[a-záéíóúñ]{5,}", oracion.lower())
    vistas, resultado = set(), []
    for p in palabras:
        if p in _PALABRAS_VACIAS or p in vistas:
            continue
        vistas.add(p)
        resultado.append(p)
        if len(resultado) >= maximo:
            break
    return resultado


def _detectar_tipo_documento(oracion: str) -> str | None:
    for tipo, patrones in TIPOS_DOCUMENTO.items():
        if any(re.search(p, oracion, re.IGNORECASE) for p in patrones):
            return tipo
    return None


def _bloques_por_articulo(texto: str) -> list[tuple[str, str]]:
    """Divide el texto en tramos, cada uno asociado al artículo vigente."""
    posiciones = [(m.start(), m.group(1)) for m in _RE_ARTICULO.finditer(texto)]
    if not posiciones:
        return [("s/n", texto)]
    bloques = []
    for i, (inicio, numero) in enumerate(posiciones):
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(texto)
        bloques.append((f"Art. {numero}", texto[inicio:fin]))
    return bloques


def extraer_requisitos(texto: str) -> list[Requisito]:
    """Devuelve los requisitos detectados en el texto de la normativa."""
    if not texto or not texto.strip():
        return []
    texto = texto.replace("\r\n", "\n")
    requisitos: list[Requisito] = []
    for articulo, bloque in _bloques_por_articulo(texto):
        bloque_plano = re.sub(r"\s+", " ", bloque).strip()
        for oracion in _dividir_oraciones(bloque_plano):
            if len(oracion.split()) < MINIMO_PALABRAS_ORACION:
                continue
            if not _RE_OBLIGACION.search(oracion):
                continue
            requisitos.append(Requisito(
                indice=len(requisitos),
                articulo=articulo,
                texto=oracion,
                palabras_clave=_palabras_clave(oracion),
                tipo_documento=_detectar_tipo_documento(oracion),
            ))
    return requisitos
