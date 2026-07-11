"""Almacén vectorial local con degradación elegante.

Orden de preferencia:
1. ChromaDB (si está instalado) — persistencia propia y HNSW.
2. FAISS (si está instalado) — índice plano por producto interno.
3. Almacén interno en Python puro — similitud coseno por fuerza bruta.

Para expedientes (cientos a miles de fragmentos) los tres rinden de sobra,
y el interno garantiza que la búsqueda semántica SIEMPRE funcione sin
dependencias pesadas. Todos son 100 % locales.
"""

import math
from array import array


def vector_a_bytes(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def bytes_a_vector(datos: bytes) -> list[float]:
    a = array("f")
    a.frombytes(datos)
    return list(a)


class AlmacenInterno:
    """Similitud coseno por fuerza bruta, sin dependencias."""

    nombre = "interno"

    def __init__(self):
        self._items: list[tuple[str, list[float]]] = []

    def agregar(self, ids: list[str], vectores: list[list[float]]) -> None:
        self._items.extend(zip(ids, vectores))

    def buscar(self, vector: list[float], k: int) -> list[tuple[str, float]]:
        norma_q = math.sqrt(sum(x * x for x in vector)) or 1.0
        puntajes = []
        for id_, v in self._items:
            prod = sum(a * b for a, b in zip(vector, v))
            norma_v = math.sqrt(sum(x * x for x in v)) or 1.0
            puntajes.append((id_, prod / (norma_q * norma_v)))
        puntajes.sort(key=lambda p: p[1], reverse=True)
        return puntajes[:k]

    def __len__(self) -> int:
        return len(self._items)


class AlmacenFaiss:
    nombre = "faiss"

    def __init__(self):
        import faiss  # noqa: F401  (probar disponibilidad al construir)
        import numpy as np

        self._faiss = faiss
        self._np = np
        self._indice = None
        self._ids: list[str] = []

    def agregar(self, ids: list[str], vectores: list[list[float]]) -> None:
        if not vectores:
            return
        matriz = self._np.array(vectores, dtype="float32")
        self._faiss.normalize_L2(matriz)
        if self._indice is None:
            self._indice = self._faiss.IndexFlatIP(matriz.shape[1])
        self._indice.add(matriz)
        self._ids.extend(ids)

    def buscar(self, vector: list[float], k: int) -> list[tuple[str, float]]:
        if self._indice is None or not self._ids:
            return []
        consulta = self._np.array([vector], dtype="float32")
        self._faiss.normalize_L2(consulta)
        puntajes, indices = self._indice.search(consulta, min(k, len(self._ids)))
        return [
            (self._ids[i], float(s))
            for i, s in zip(indices[0], puntajes[0])
            if i >= 0
        ]

    def __len__(self) -> int:
        return len(self._ids)


class AlmacenChroma:
    nombre = "chromadb"

    def __init__(self):
        import chromadb

        self._cliente = chromadb.EphemeralClient()
        self._coleccion = self._cliente.create_collection(
            "expediente", metadata={"hnsw:space": "cosine"}
        )
        self._total = 0

    def agregar(self, ids: list[str], vectores: list[list[float]]) -> None:
        if not ids:
            return
        self._coleccion.add(ids=ids, embeddings=vectores)
        self._total += len(ids)

    def buscar(self, vector: list[float], k: int) -> list[tuple[str, float]]:
        if self._total == 0:
            return []
        res = self._coleccion.query(
            query_embeddings=[vector], n_results=min(k, self._total)
        )
        ids = res["ids"][0]
        distancias = res["distances"][0]
        # Chroma devuelve distancia coseno; la convertimos a similitud
        return [(i, 1.0 - d) for i, d in zip(ids, distancias)]

    def __len__(self) -> int:
        return self._total


def crear_almacen():
    """Devuelve el mejor almacén disponible en este entorno."""
    for clase in (AlmacenChroma, AlmacenFaiss):
        try:
            return clase()
        except Exception:
            continue
    return AlmacenInterno()
