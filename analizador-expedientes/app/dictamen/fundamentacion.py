"""Redacción del dictamen con Ollama (modelo local, sin costo de API).

El cumplimiento de cada requisito ya fue determinado por reglas en
`cotejo.py` — este módulo NO decide nada, sólo redacta en prosa jurídica lo
que el cotejo ya estableció, citando artículo y página. El prompt exige
explícitamente no agregar hechos que no estén en la lista de resultados, y
usa una caché en SQLite (por hash del cotejo + modelo) para no volver a
generar el mismo texto.
"""

from app.almacenamiento.base_datos import BaseDatosProyecto, hash_bloque
from app.config.settings import VERSION_PROMPTS
from app.dictamen.cotejo import CUMPLE, FALTA, NO_CONSTA, ResultadoCotejo
from app.resumen.cliente_ollama import ClienteOllama
from app.utils.registro import obtener_logger

log = obtener_logger("dictamen")

SISTEMA_DICTAMEN = (
    "Sos un abogado dictaminante en un organismo público. Redactás en "
    "español, en el estilo formal de un dictamen jurídico argentino "
    "('Que...', 'Corresponde...'). Se te da una lista cerrada de "
    "requisitos normativos y si el expediente los cumple o no, ya "
    "verificado. NO agregues requisitos, hechos ni conclusiones que no "
    "estén en esa lista: tu única tarea es redactar en prosa jurídica lo "
    "que ya se determinó, citando siempre el artículo y, si existe, la "
    "página del expediente entre paréntesis, por ejemplo (pág. 12)."
)

_ETIQUETA_ESTADO = {
    CUMPLE: "CUMPLE",
    NO_CONSTA: "NO CONSTA CLARAMENTE EN EL EXPEDIENTE",
    FALTA: "NO CUMPLE / NO SE ENCONTRÓ EN EL EXPEDIENTE",
}


def _listado_resultados(resultados: list[ResultadoCotejo]) -> str:
    lineas = []
    for r in resultados:
        pagina = f"pág. {r.pagina}" if r.pagina else "sin referencia en el expediente"
        evidencia = f" Evidencia: «{r.evidencia}»" if r.evidencia else ""
        lineas.append(
            f"- Requisito ({r.requisito.articulo}): {r.requisito.texto}\n"
            f"  Estado verificado: {_ETIQUETA_ESTADO[r.estado]} ({pagina}).{evidencia}"
        )
    return "\n".join(lineas)


def prompt_considerando(resultados: list[ResultadoCotejo]) -> str:
    return f"""Redactá la sección "CONSIDERANDO" de un dictamen jurídico. Un párrafo por requisito (empezando con "Que..."), en el orden dado, indicando si se cumple, citando el artículo de la normativa y la página del expediente cuando exista. Si el estado es "NO CUMPLE" o "NO CONSTA", decilo con claridad, sin dramatizar.

REQUISITOS Y SU ESTADO VERIFICADO (no modifiques esta información, sólo redactala):
{_listado_resultados(resultados)}

SECCIÓN "CONSIDERANDO":"""


def prompt_resuelve(resultados: list[ResultadoCotejo]) -> str:
    cumplidos = [r for r in resultados if r.estado == CUMPLE]
    faltantes = [r for r in resultados if r.estado == FALTA]
    dudosos = [r for r in resultados if r.estado == NO_CONSTA]
    resumen = (
        f"Total de requisitos: {len(resultados)}. "
        f"Cumplidos: {len(cumplidos)}. "
        f"Faltantes: {len(faltantes)}. "
        f"Sin evidencia clara: {len(dudosos)}."
    )
    return f"""Redactá la sección "RESUELVE" (o "DICTAMINA") de un dictamen jurídico, con artículos numerados (Art. 1°, Art. 2°...). Debe concluir si corresponde continuar el trámite, si es necesario subsanar algo, o si no puede opinarse favorablemente, en función pura y exclusivamente de este resumen:

{resumen}

Si hay requisitos faltantes o sin evidencia clara, el último artículo debe intimar a subsanarlos antes de continuar. No inventes motivos adicionales.

SECCIÓN "RESUELVE":"""


def generar_redaccion(
    cliente: ClienteOllama,
    db: BaseDatosProyecto,
    modelo: str,
    resultados: list[ResultadoCotejo],
) -> dict:
    """Devuelve {"considerando": str, "resuelve": str}, usando caché si el
    cotejo y el modelo no cambiaron desde la última vez."""
    contenido = _listado_resultados(resultados)
    h = hash_bloque(contenido, modelo, VERSION_PROMPTS)
    cache = db.buscar_redaccion_dictamen(h)
    if cache is not None:
        log.info("Redacción de dictamen recuperada de caché")
        return cache

    considerando = cliente.generar(
        modelo, prompt_considerando(resultados), sistema=SISTEMA_DICTAMEN
    )
    resuelve = cliente.generar(
        modelo, prompt_resuelve(resultados), sistema=SISTEMA_DICTAMEN
    )
    db.guardar_redaccion_dictamen(h, modelo, considerando, resuelve)
    log.info("Redacción de dictamen generada con %s", modelo)
    return {"considerando": considerando, "resuelve": resuelve}
