"""Revisión con Claude — integración OPCIONAL y aislada.

Reglas de este módulo (invariantes de privacidad de la aplicación):

1. Nada de este paquete se ejecuta salvo que el usuario active expresamente
   la "Revisión con Claude". El resto de la app no importa este módulo.
2. Sólo se envían datos DESTILADOS: resúmenes parciales, cronología, datos
   estructurados (documentos detectados) y la pregunta del usuario. Nunca el
   PDF ni el texto completo del expediente, salvo selección expresa
   (permitir_texto_completo=True) que la interfaz advierte por separado.
3. Antes de enviar, `preparar_envio()` devuelve EXACTAMENTE lo que se va a
   transmitir y la estimación de tokens/costo, para mostrarlo al usuario.
   `enviar()` exige el objeto confirmado.
4. La clave se lee sólo de la variable de entorno ANTHROPIC_API_KEY.
"""

import os
from dataclasses import dataclass, field

from app.claude_api.estimador_tokens import EstimacionTokens, estimar_consulta
from app.config.settings import VAR_CLAVE_CLAUDE
from app.utils.errores import ClaveApiFaltante, ErrorAplicacion
from app.utils.registro import obtener_logger

log = obtener_logger("claude")

_SISTEMA = (
    "Sos un revisor jurídico-administrativo senior. Recibís resúmenes y datos "
    "estructurados de un expediente administrativo (no el documento original) "
    "y respondés en español. Cada afirmación debe apoyarse en los datos "
    "recibidos, citando la página cuando esté disponible, por ejemplo "
    "(pág. 12). Señalá también qué no puede verificarse con la información "
    "provista."
)


class SdkAnthropicFaltante(ErrorAplicacion):
    titulo = "Falta el paquete 'anthropic'"

    def __init__(self, detalle: str = ""):
        super().__init__(
            "La Revisión con Claude requiere el paquete oficial de "
            "Anthropic.\n\nInstalalo con:  pip install anthropic",
            detalle,
        )


@dataclass
class EnvioPropuesto:
    """Lo que se enviaría a Claude, para revisión y confirmación del usuario."""

    modelo: str
    pregunta: str
    contenido: str                 # texto completo que se transmitirá
    estimacion: EstimacionTokens = None
    secciones_incluidas: list[str] = field(default_factory=list)
    confirmado: bool = False       # la GUI lo pone en True tras la advertencia


def hay_clave_api() -> bool:
    return bool(os.environ.get(VAR_CLAVE_CLAUDE))


def preparar_envio(
    pregunta: str,
    modelo: str,
    resumenes_parciales: list[str] | None = None,
    resumen_general: str | None = None,
    cronologia: list[dict] | None = None,
    documentos: list[dict] | None = None,
    texto_completo: str | None = None,
    permitir_texto_completo: bool = False,
) -> EnvioPropuesto:
    """Arma el paquete a enviar SIN transmitir nada todavía."""
    partes, secciones = [], []
    if resumen_general:
        partes.append(f"# RESUMEN GENERAL DEL EXPEDIENTE\n\n{resumen_general}")
        secciones.append("Resumen general")
    if resumenes_parciales:
        partes.append("# RESÚMENES PARCIALES POR BLOQUE\n\n" + "\n\n".join(resumenes_parciales))
        secciones.append(f"Resúmenes parciales ({len(resumenes_parciales)} bloques)")
    if cronologia:
        lineas = [
            f"- {e.get('fecha_iso', '')} (pág. {e.get('pagina', '?')}): {e.get('contexto', '')}"
            for e in cronologia
        ]
        partes.append("# CRONOLOGÍA\n\n" + "\n".join(lineas))
        secciones.append(f"Cronología ({len(cronologia)} eventos)")
    if documentos:
        lineas = [
            f"- [{d['tipo']}] (pág. {d['pagina']}) {d['referencia']}" for d in documentos
        ]
        partes.append("# DOCUMENTOS DETECTADOS\n\n" + "\n".join(lineas))
        secciones.append(f"Documentos detectados ({len(documentos)})")
    if texto_completo:
        if not permitir_texto_completo:
            raise ErrorAplicacion(
                "El texto completo del expediente sólo puede enviarse con la "
                "opción expresa 'Incluir texto completo'. Por defecto se "
                "envían únicamente los resúmenes y datos estructurados."
            )
        partes.append(f"# TEXTO COMPLETO DEL EXPEDIENTE (autorizado expresamente)\n\n{texto_completo}")
        secciones.append("⚠ TEXTO COMPLETO del expediente")

    contenido = "\n\n---\n\n".join(partes)
    if not contenido:
        raise ErrorAplicacion(
            "No hay resúmenes ni datos para enviar. Procesá el expediente "
            "localmente antes de usar la Revisión con Claude."
        )
    envio = EnvioPropuesto(
        modelo=modelo,
        pregunta=pregunta.strip(),
        contenido=contenido,
        secciones_incluidas=secciones,
    )
    envio.estimacion = estimar_consulta(
        _SISTEMA + contenido + envio.pregunta, modelo
    )
    return envio


def enviar(envio: EnvioPropuesto) -> str:
    """Envía la consulta confirmada a la API de Anthropic y devuelve el texto."""
    if not envio.confirmado:
        raise ErrorAplicacion(
            "El envío a Claude no fue confirmado por el usuario. "
            "Revisá la advertencia y confirmá qué se enviará."
        )
    if not hay_clave_api():
        raise ClaveApiFaltante()
    try:
        import anthropic
    except ImportError as e:
        raise SdkAnthropicFaltante(detalle=str(e))

    cliente = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno
    log.info(
        "Revisión con Claude: modelo=%s, secciones=%s, tokens estimados=%d",
        envio.modelo,
        "; ".join(envio.secciones_incluidas),
        envio.estimacion.tokens_entrada if envio.estimacion else -1,
    )
    try:
        with cliente.messages.stream(
            model=envio.modelo,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=_SISTEMA,
            messages=[{
                "role": "user",
                "content": (
                    f"{envio.contenido}\n\n---\n\n"
                    f"CONSULTA DEL USUARIO: {envio.pregunta}"
                ),
            }],
        ) as stream:
            respuesta = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise ClaveApiFaltante(detalle=f"La clave fue rechazada: {e.message}")
    except anthropic.NotFoundError as e:
        raise ErrorAplicacion(
            f"El modelo '{envio.modelo}' no existe o no está disponible para "
            "tu cuenta.", detalle=str(e),
        )
    except anthropic.RateLimitError as e:
        raise ErrorAplicacion(
            "Se alcanzó el límite de uso de la API de Anthropic. Esperá unos "
            "minutos y volvé a intentar.", detalle=str(e),
        )
    except anthropic.APIStatusError as e:
        raise ErrorAplicacion(
            f"La API de Anthropic devolvió un error ({e.status_code}). "
            "Reintentá más tarde.", detalle=str(e),
        )
    except anthropic.APIConnectionError as e:
        raise ErrorAplicacion(
            "No se pudo conectar con la API de Anthropic. Verificá la "
            "conexión a internet.", detalle=str(e),
        )

    if respuesta.stop_reason == "refusal":
        return (
            "Claude declinó responder esta consulta por políticas de "
            "seguridad. Reformulá la pregunta."
        )
    texto = "".join(b.text for b in respuesta.content if b.type == "text")
    log.info(
        "Respuesta de Claude recibida: %d tokens de salida",
        respuesta.usage.output_tokens,
    )
    return texto
