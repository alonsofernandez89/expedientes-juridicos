"""Cotejo determinístico: ¿el expediente cumple cada requisito normativo?

Sin IA. Para cada requisito:

- Si menciona un tipo de documento conocido (informe técnico, presupuesto,
  dictamen, etc.), se busca primero entre los documentos ya detectados por
  `app.analisis.documentos` (más confiable, porque ya identificó el tipo).
- Si no hay tipo de documento asociado, o no se encontró, se buscan sus
  palabras clave en el texto de cada página.

Estados posibles:
- "cumple": se encontró evidencia clara (documento del tipo exigido, o
  suficientes palabras clave juntas en una misma página).
- "no_consta": hay indicios parciales (alguna palabra clave aparece, pero no
  las suficientes para confirmar) — requiere revisión manual.
- "falta": no se encontró ninguna evidencia en el expediente.
"""

from dataclasses import dataclass

from app.dictamen.requisitos import Requisito

CUMPLE = "cumple"
NO_CONSTA = "no_consta"
FALTA = "falta"

LARGO_EVIDENCIA = 200


@dataclass
class ResultadoCotejo:
    requisito: Requisito
    estado: str
    pagina: int | None
    evidencia: str


def _minimo_coincidencias(cantidad_claves: int) -> int:
    """Cuántas palabras clave deben coincidir para dar por cumplido el
    requisito: la mitad (redondeando hacia arriba), con un piso de 1."""
    if cantidad_claves == 0:
        return 0
    return max(1, (cantidad_claves + 1) // 2)


def _buscar_por_documento(requisito: Requisito, documentos: list[dict]) -> ResultadoCotejo | None:
    for d in documentos:
        if d["tipo"].lower() == (requisito.tipo_documento or "").lower():
            return ResultadoCotejo(requisito, CUMPLE, d["pagina"], d["referencia"])
    return None


def _buscar_por_palabras_clave(requisito: Requisito, paginas: list[str]) -> ResultadoCotejo:
    if not requisito.palabras_clave:
        # sin ninguna pista para buscar, no hay evidencia que reportar
        return ResultadoCotejo(requisito, FALTA, None, "")

    umbral = _minimo_coincidencias(len(requisito.palabras_clave))
    mejor_parcial: ResultadoCotejo | None = None

    for numero, texto in enumerate(paginas, start=1):
        texto_min = texto.lower()
        coincidencias = sum(1 for p in requisito.palabras_clave if p in texto_min)
        if coincidencias == 0:
            continue
        if coincidencias >= umbral:
            return ResultadoCotejo(requisito, CUMPLE, numero, texto.strip()[:LARGO_EVIDENCIA])
        if mejor_parcial is None:
            mejor_parcial = ResultadoCotejo(
                requisito, NO_CONSTA, numero, texto.strip()[:LARGO_EVIDENCIA]
            )

    return mejor_parcial or ResultadoCotejo(requisito, FALTA, None, "")


def cotejar_requisito(
    requisito: Requisito, paginas: list[str], documentos: list[dict]
) -> ResultadoCotejo:
    if requisito.tipo_documento:
        resultado = _buscar_por_documento(requisito, documentos)
        if resultado is not None:
            return resultado
    return _buscar_por_palabras_clave(requisito, paginas)


def cotejar_requisitos(
    requisitos: list[Requisito], paginas: list[str], documentos: list[dict]
) -> list[ResultadoCotejo]:
    return [cotejar_requisito(r, paginas, documentos) for r in requisitos]


def resumen_cumplimiento(resultados: list[ResultadoCotejo]) -> dict:
    """Conteo por estado, para la conclusión del dictamen y la GUI."""
    conteo = {CUMPLE: 0, NO_CONSTA: 0, FALTA: 0}
    for r in resultados:
        conteo[r.estado] += 1
    conteo["total"] = len(resultados)
    return conteo
