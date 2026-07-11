"""Limpieza de ruido repetitivo en expedientes escaneados.

Detecta por FRECUENCIA (no por contenido) las líneas que se repiten en
muchas páginas y que no aportan al resumen:

- encabezados repetidos (zona superior de la página);
- pies de página repetidos (zona inferior);
- membretes (líneas cortas de organismo repetidas arriba);
- números de expediente estampados en cada página;
- sellos o textos duplicados en cualquier zona.

La detección es conservadora: una línea solo se elimina si su forma
normalizada (sin dígitos ni espacios extra) aparece en una proporción alta
de páginas. El texto original nunca se pierde: la limpieza produce una
versión paralela y registra qué se quitó de cada página (auditable).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

# Zonas de página donde se buscan encabezados/pies
LINEAS_ZONA = 4
# Una línea repetida se considera ruido si aparece en ≥ este % de páginas
UMBRAL_PROPORCION = 0.4
# ...y en al menos esta cantidad absoluta de páginas
UMBRAL_MINIMO_PAGINAS = 3
# Solo líneas cortas pueden ser ruido (membretes, sellos, folios); una línea
# larga es casi seguro contenido real aunque se repita su forma normalizada.
LARGO_MAX_RUIDO = 80
# Una línea que solo se repite al ignorar sus dígitos (p. ej. "Folio 12")
# debe ser además corta en palabras: el contenido real con números (montos,
# fechas dentro de oraciones) suele tener más palabras.
PALABRAS_MAX_RUIDO_CON_DIGITOS = 6
# Una página se considera vacía si tras limpiar queda menos que esto
MINIMO_CARACTERES_PAGINA = 25

_RE_EXPEDIENTE = re.compile(
    r"\b(?:EXP(?:TE|EDIENTE)?\.?\s*(?:N[°ºo\.]*)?\s*[-:]?\s*[\w./-]*\d[\w./-]*)",
    re.IGNORECASE,
)


def _normalizar(linea: str) -> str:
    """Forma canónica para encabezados/pies: sin dígitos (los folios cambian
    por página), minúsculas, espacios colapsados."""
    linea = re.sub(r"\d+", "#", linea.strip().lower())
    return re.sub(r"\s+", " ", linea)


def _normalizar_exacta(linea: str) -> str:
    """Forma canónica para sellos: conserva los dígitos. Un sello verdadero
    ("ES COPIA FIEL DEL ORIGINAL", "EXP. 123/2023") se repite idéntico; las
    líneas de contenido que solo difieren en números NO deben eliminarse."""
    return re.sub(r"\s+", " ", linea.strip().lower())


@dataclass
class ResultadoLimpieza:
    paginas_limpias: list[str] = field(default_factory=list)
    paginas_vacias: list[int] = field(default_factory=list)      # números 1-based
    eliminadas_por_pagina: list[list[str]] = field(default_factory=list)
    patrones_detectados: dict = field(default_factory=dict)


def _zona(no_vacias: list[str]) -> int:
    """Tamaño de la zona de encabezado/pie, acotado en páginas cortas para
    que las dos zonas nunca cubran la página entera."""
    return min(LINEAS_ZONA, max(1, len(no_vacias) // 3))


def _contar_repeticiones(paginas_lineas: list[list[str]]):
    """Cuenta en cuántas páginas aparece cada línea normalizada, por zona."""
    arriba, abajo, cualquiera = Counter(), Counter(), Counter()
    for lineas in paginas_lineas:
        no_vacias = [l for l in lineas if l.strip()]
        z = _zona(no_vacias)
        arriba.update({_normalizar(l) for l in no_vacias[:z]})
        abajo.update({_normalizar(l) for l in no_vacias[-z:]})
        # sellos: repetición EXACTA (con dígitos) en cualquier zona
        cualquiera.update({_normalizar_exacta(l) for l in no_vacias})
    return arriba, abajo, cualquiera


def limpiar_paginas(paginas: list[str]) -> ResultadoLimpieza:
    """Aplica la limpieza a todas las páginas y devuelve el resultado."""
    resultado = ResultadoLimpieza()
    total = len(paginas)
    if total == 0:
        return resultado

    paginas_lineas = [p.splitlines() for p in paginas]
    umbral = max(UMBRAL_MINIMO_PAGINAS, int(total * UMBRAL_PROPORCION))
    arriba, abajo, cualquiera = _contar_repeticiones(paginas_lineas)

    def _es_ruido_zona(norma: str, cuenta: int) -> bool:
        """Encabezado/pie: la coincidencia ignora dígitos, así que además de
        corta en caracteres la línea debe ser corta en palabras (membrete,
        folio); una oración con números adentro es contenido."""
        return (
            bool(norma)
            and cuenta >= umbral
            and len(norma) <= LARGO_MAX_RUIDO
            and ("#" not in norma or len(norma.split()) <= PALABRAS_MAX_RUIDO_CON_DIGITOS)
        )

    def _es_ruido_exacto(norma: str, cuenta: int) -> bool:
        return bool(norma) and cuenta >= umbral and len(norma) <= LARGO_MAX_RUIDO

    encabezados = {n for n, c in arriba.items() if _es_ruido_zona(n, c)}
    pies = {n for n, c in abajo.items() if _es_ruido_zona(n, c)}
    sellos = {
        n for n, c in cualquiera.items() if _es_ruido_exacto(n, c)
    } - encabezados - pies

    # Números de expediente repetidos: sólo si el MISMO número (normalizado
    # con sus dígitos) aparece estampado en muchas páginas.
    expedientes = Counter()
    for lineas in paginas_lineas:
        encontrados = set()
        for l in lineas:
            for m in _RE_EXPEDIENTE.findall(l):
                encontrados.add(m.strip().lower())
        expedientes.update(encontrados)
    exp_repetidos = {e for e, c in expedientes.items() if c >= umbral}

    resultado.patrones_detectados = {
        "encabezados": sorted(encabezados),
        "pies": sorted(pies),
        "sellos": sorted(sellos),
        "expedientes_repetidos": sorted(exp_repetidos),
        "umbral_paginas": umbral,
    }

    for num, lineas in enumerate(paginas_lineas, start=1):
        limpias, eliminadas = [], []
        no_vacias = [l for l in lineas if l.strip()]
        z = _zona(no_vacias)
        zona_arriba = set(no_vacias[:z])
        zona_abajo = set(no_vacias[-z:])
        for linea in lineas:
            norma = _normalizar(linea)
            norma_exacta = _normalizar_exacta(linea)
            if not norma:
                limpias.append(linea)
                continue
            es_ruido = (
                (linea in zona_arriba and norma in encabezados)
                or (linea in zona_abajo and norma in pies)
                or norma_exacta in sellos
            )
            if not es_ruido and exp_repetidos:
                # línea que es únicamente un número de expediente repetido
                sin_exp = _RE_EXPEDIENTE.sub("", linea).strip(" -–—:·.")
                if not sin_exp and any(
                    e in linea.lower() for e in exp_repetidos
                ):
                    es_ruido = True
            if es_ruido:
                eliminadas.append(linea.strip())
            else:
                limpias.append(linea)
        texto_limpio = "\n".join(limpias).strip()
        if len(texto_limpio) < MINIMO_CARACTERES_PAGINA:
            resultado.paginas_vacias.append(num)
        resultado.paginas_limpias.append(texto_limpio)
        resultado.eliminadas_por_pagina.append(eliminadas)

    return resultado
