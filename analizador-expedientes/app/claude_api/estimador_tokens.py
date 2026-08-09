"""Estimación LOCAL de tokens y costo antes de cualquier consulta externa.

Importante: la estimación es local a propósito. Usar el endpoint oficial de
conteo de tokens implicaría enviar el contenido a la API antes de que el
usuario confirme, lo que contradice la política de privacidad de la app.
La aproximación (≈3,5 caracteres por token en español) da el orden de
magnitud correcto para la advertencia previa.
"""

from dataclasses import dataclass

CARACTERES_POR_TOKEN = 3.5

# Precios de referencia (USD por millón de tokens). Sólo para orientar la
# advertencia; el costo real lo factura Anthropic.
PRECIOS_USD_POR_MILLON = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
PRECIO_DEFECTO = (5.00, 25.00)


@dataclass
class EstimacionTokens:
    tokens_entrada: int
    tokens_salida_previstos: int
    costo_estimado_usd: float
    modelo: str

    def resumen(self) -> str:
        return (
            f"Tokens de entrada estimados: {self.tokens_entrada:,}\n"
            f"Tokens de salida previstos: {self.tokens_salida_previstos:,}\n"
            f"Costo aproximado: US$ {self.costo_estimado_usd:.4f} ({self.modelo})"
        ).replace(",", ".")


def estimar_tokens(texto: str) -> int:
    return max(1, round(len(texto) / CARACTERES_POR_TOKEN))


def estimar_consulta(
    texto_entrada: str,
    modelo: str,
    tokens_salida_previstos: int = 4000,
) -> EstimacionTokens:
    entrada = estimar_tokens(texto_entrada)
    precio_in, precio_out = PRECIOS_USD_POR_MILLON.get(modelo, PRECIO_DEFECTO)
    costo = (entrada * precio_in + tokens_salida_previstos * precio_out) / 1_000_000
    return EstimacionTokens(
        tokens_entrada=entrada,
        tokens_salida_previstos=tokens_salida_previstos,
        costo_estimado_usd=costo,
        modelo=modelo,
    )
