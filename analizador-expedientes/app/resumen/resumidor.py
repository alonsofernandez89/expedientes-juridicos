"""Resumen por bloques con Ollama, con caché para no reprocesar.

Cada bloque se resume una única vez: el resultado queda en SQLite indexado
por hash de (contenido + modelo + versión de prompt). Reabrir el proyecto,
reintentar tras un corte o agregar bloques nuevos no repite trabajo.
"""

from collections.abc import Callable

from app.almacenamiento.base_datos import BaseDatosProyecto, hash_bloque
from app.bloques.divisor import Bloque
from app.config.settings import VERSION_PROMPTS
from app.resumen import prompts
from app.resumen.cliente_ollama import ClienteOllama
from app.utils.registro import obtener_logger

log = obtener_logger("resumen")


class Resumidor:
    def __init__(self, cliente: ClienteOllama, db: BaseDatosProyecto, modelo: str):
        self.cliente = cliente
        self.db = db
        self.modelo = modelo

    def resumir_bloques(
        self,
        bloques: list[Bloque],
        progreso: Callable[[int, int, bool], None] | None = None,
        cancelado: Callable[[], bool] | None = None,
    ) -> list[str]:
        """Resume todos los bloques (usando caché) y devuelve los resúmenes.

        `progreso(indice, total, desde_cache)` se llama al terminar cada bloque.
        `cancelado()` permite abortar entre bloques sin perder lo ya resumido.
        """
        resultados: list[str] = []
        total = len(bloques)
        for bloque in bloques:
            if cancelado and cancelado():
                log.info("Resumen cancelado en el bloque %d", bloque.indice + 1)
                break
            h = hash_bloque(bloque.texto, self.modelo, VERSION_PROMPTS)
            resumen = self.db.buscar_resumen(h)
            desde_cache = resumen is not None
            if not desde_cache:
                resumen = self.cliente.generar(
                    self.modelo,
                    prompts.prompt_bloque(bloque.etiqueta, bloque.texto),
                    sistema=prompts.SISTEMA_RESUMIDOR,
                )
                self.db.guardar_resumen(
                    h,
                    bloque.indice,
                    bloque.pagina_desde,
                    bloque.pagina_hasta,
                    self.modelo,
                    resumen,
                )
            log.info(
                "Bloque %d/%d %s",
                bloque.indice + 1, total,
                "recuperado de caché" if desde_cache else "resumido",
            )
            resultados.append(f"### {bloque.etiqueta}\n\n{resumen}")
            if progreso:
                progreso(bloque.indice + 1, total, desde_cache)
        return resultados

    def resumen_general(self, resumenes_parciales: list[str]) -> str:
        """Consolida los resúmenes parciales en el resumen estructurado final."""
        texto = self.cliente.generar(
            self.modelo,
            prompts.prompt_general(resumenes_parciales),
            sistema=prompts.SISTEMA_RESUMIDOR,
        )
        self.db.guardar_resumen_general(self.modelo, texto)
        return texto
