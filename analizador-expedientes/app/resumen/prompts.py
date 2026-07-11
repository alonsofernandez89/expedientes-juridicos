"""Prompts para el resumen de expedientes administrativos.

Si se modifican los prompts hay que subir VERSION_PROMPTS en
app/config/settings.py para invalidar la caché de resúmenes.
"""

SECCIONES_RESUMEN = [
    "Número y carátula del expediente",
    "Organismo iniciador",
    "Objeto de las actuaciones",
    "Antecedentes",
    "Documentación incorporada",
    "Personas, organismos o empresas intervinientes",
    "Fechas relevantes",
    "Montos",
    "Normativa citada",
    "Informes técnicos",
    "Intervenciones administrativas",
    "Observaciones",
    "Documentación faltante",
    "Posibles inconsistencias",
    "Estado actual del trámite",
    "Conclusión general",
]

SISTEMA_RESUMIDOR = (
    "Sos un asistente jurídico-administrativo experto en analizar "
    "expedientes administrativos argentinos. Trabajás con texto obtenido "
    "por OCR, que puede tener errores de reconocimiento. Respondés siempre "
    "en español, de forma precisa y sin inventar datos: si algo no consta "
    "en el texto, lo decís expresamente. Cada dato que menciones debe "
    "indicar entre paréntesis la página de origen, por ejemplo: (pág. 12). "
    "Los números de página aparecen en el texto como [Página N]."
)


def prompt_bloque(etiqueta: str, texto: str) -> str:
    return f"""Analizá el siguiente fragmento de un expediente administrativo ({etiqueta}).

Extraé de manera ordenada, citando SIEMPRE la página de origen de cada dato:

1. Actos y hechos principales (qué ocurrió, quién intervino).
2. Documentos que se incorporan (notas, resoluciones, decretos, contratos, convenios, dictámenes, informes técnicos, presupuestos, facturas, órdenes de compra, actas, documentación contable).
3. Personas, organismos y empresas mencionados.
4. Fechas relevantes.
5. Montos de dinero.
6. Normativa citada (leyes, decretos, resoluciones, ordenanzas).
7. Observaciones o irregularidades que notes.

Si el fragmento no contiene alguno de esos elementos, omití esa categoría.
Sé conciso: es un resumen de trabajo, no una transcripción.

TEXTO DEL EXPEDIENTE:
{texto}

RESUMEN DEL FRAGMENTO:"""


def prompt_general(resumenes_parciales: list[str]) -> str:
    parciales = "\n\n---\n\n".join(resumenes_parciales)
    secciones = "\n".join(f"## {s}" for s in SECCIONES_RESUMEN)
    return f"""A partir de los siguientes resúmenes parciales de un expediente administrativo (cada uno cubre un rango de páginas y cita las páginas de origen), redactá el RESUMEN GENERAL del expediente completo.

El resumen DEBE tener exactamente estas secciones, en este orden, en formato Markdown:

{secciones}

Reglas:
- Mantené en cada dato la cita de página de origen, por ejemplo (pág. 12).
- Si una sección no tiene información en los resúmenes, escribí "No consta en el expediente analizado."
- En "Fechas relevantes" y "Montos" usá listas con un ítem por dato.
- En "Posibles inconsistencias" señalá contradicciones, saltos de foliatura o falta de actos que deberían existir.
- No inventes información que no esté en los resúmenes parciales.

RESÚMENES PARCIALES:
{parciales}

RESUMEN GENERAL DEL EXPEDIENTE:"""


def prompt_pregunta(pregunta: str, pasajes: list[tuple[int, str]]) -> str:
    contexto = "\n\n".join(f"[Página {p}]\n{t}" for p, t in pasajes)
    return f"""Respondé la siguiente pregunta sobre un expediente administrativo usando ÚNICAMENTE los pasajes provistos. Citá la página de origen de cada dato, por ejemplo (pág. 12). Si la respuesta no está en los pasajes, decilo expresamente.

PASAJES DEL EXPEDIENTE:
{contexto}

PREGUNTA: {pregunta}

RESPUESTA:"""
