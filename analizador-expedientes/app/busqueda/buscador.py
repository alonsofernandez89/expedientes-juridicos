"""Búsqueda semántica local sobre el expediente.

Las páginas se parten en fragmentos con solapamiento, se vectorizan con un
modelo de embeddings local (Ollama, p. ej. nomic-embed-text) y se indexan
en el almacén vectorial. Los embeddings se persisten en el proyecto para
no recalcularlos al reabrir. Las respuestas citan la página de origen.
"""

from collections.abc import Callable

from app.almacenamiento.base_datos import BaseDatosProyecto
from app.busqueda.almacen_vectorial import (
    bytes_a_vector,
    crear_almacen,
    vector_a_bytes,
)
from app.resumen import prompts
from app.resumen.cliente_ollama import ClienteOllama
from app.utils.registro import obtener_logger

log = obtener_logger("busqueda")

LARGO_FRAGMENTO = 1000
SOLAPAMIENTO = 150


def fragmentar_pagina(texto: str, pagina: int) -> list[tuple[str, int, str]]:
    """Divide una página en fragmentos (id, pagina, texto)."""
    texto = texto.strip()
    if not texto:
        return []
    fragmentos = []
    paso = LARGO_FRAGMENTO - SOLAPAMIENTO
    for n, inicio in enumerate(range(0, len(texto), paso)):
        pedazo = texto[inicio: inicio + LARGO_FRAGMENTO].strip()
        if pedazo:
            fragmentos.append((f"p{pagina}_f{n}", pagina, pedazo))
        if inicio + LARGO_FRAGMENTO >= len(texto):
            break
    return fragmentos


class BuscadorSemantico:
    def __init__(
        self,
        cliente: ClienteOllama,
        db: BaseDatosProyecto,
        modelo_embeddings: str,
    ):
        self.cliente = cliente
        self.db = db
        self.modelo = modelo_embeddings
        self.almacen = crear_almacen()
        self._textos: dict[str, tuple[int, str]] = {}  # id → (página, texto)

    @property
    def esta_indexado(self) -> bool:
        return len(self.almacen) > 0

    def cargar_indice_guardado(self) -> bool:
        """Restaura los embeddings persistidos (si existen para el modelo)."""
        registros = self.db.leer_embeddings(self.modelo)
        if not registros:
            return False
        ids, vectores = [], []
        for r in registros:
            ids.append(r["id"])
            vectores.append(bytes_a_vector(r["vector"]))
            self._textos[r["id"]] = (r["pagina"], r["texto"])
        self.almacen.agregar(ids, vectores)
        log.info("Índice restaurado: %d fragmentos (%s)", len(ids), self.almacen.nombre)
        return True

    def indexar(
        self,
        paginas: list[str],
        progreso: Callable[[int, int], None] | None = None,
        cancelado: Callable[[], bool] | None = None,
    ) -> int:
        """Vectoriza e indexa todas las páginas. Devuelve fragmentos indexados."""
        fragmentos: list[tuple[str, int, str]] = []
        for i, texto in enumerate(paginas, start=1):
            fragmentos.extend(fragmentar_pagina(texto, i))

        self.db.borrar_embeddings()
        total = len(fragmentos)
        ids, vectores, registros = [], [], []
        for n, (id_, pagina, texto) in enumerate(fragmentos, start=1):
            if cancelado and cancelado():
                break
            vector = self.cliente.embedding(self.modelo, texto)
            ids.append(id_)
            vectores.append(vector)
            self._textos[id_] = (pagina, texto)
            registros.append((id_, pagina, texto, vector_a_bytes(vector), self.modelo))
            if progreso:
                progreso(n, total)
        self.almacen.agregar(ids, vectores)
        self.db.guardar_embeddings(registros)
        log.info("Indexados %d fragmentos con %s (%s)", len(ids), self.modelo, self.almacen.nombre)
        return len(ids)

    def buscar_pasajes(self, pregunta: str, k: int = 6) -> list[tuple[int, str, float]]:
        """Pasajes más relevantes: lista de (página, texto, similitud)."""
        vector = self.cliente.embedding(self.modelo, pregunta)
        resultados = []
        for id_, puntaje in self.almacen.buscar(vector, k):
            pagina, texto = self._textos[id_]
            resultados.append((pagina, texto, puntaje))
        return resultados

    def preguntar(self, pregunta: str, modelo_respuesta: str, k: int = 6) -> dict:
        """Responde con el modelo local citando páginas.

        Devuelve {"respuesta": str, "pasajes": [(página, texto, similitud)]}.
        """
        pasajes = self.buscar_pasajes(pregunta, k)
        if not pasajes:
            return {
                "respuesta": "El expediente todavía no está indexado o no se "
                "encontraron pasajes relevantes.",
                "pasajes": [],
            }
        respuesta = self.cliente.generar(
            modelo_respuesta,
            prompts.prompt_pregunta(pregunta, [(p, t) for p, t, _ in pasajes]),
            sistema=prompts.SISTEMA_RESUMIDOR,
        )
        return {"respuesta": respuesta, "pasajes": pasajes}
