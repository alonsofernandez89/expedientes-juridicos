"""Pruebas de la búsqueda semántica (embeddings simulados, sin red)."""

from unittest.mock import MagicMock

from app.almacenamiento.base_datos import BaseDatosProyecto
from app.busqueda.almacen_vectorial import (
    AlmacenInterno,
    bytes_a_vector,
    vector_a_bytes,
)
from app.busqueda.buscador import BuscadorSemantico, fragmentar_pagina
from app.resumen.cliente_ollama import ClienteOllama

# Embeddings de juguete: cada texto se mapea a un vector 3D según palabras clave
_VOCAB = {"obra": 0, "factura": 1, "dictamen": 2}


def _embedding_falso(modelo, texto):
    v = [0.01, 0.01, 0.01]
    for palabra, idx in _VOCAB.items():
        if palabra in texto.lower():
            v[idx] = 1.0
    return v


def _cliente_falso():
    cliente = MagicMock(spec=ClienteOllama)
    cliente.embedding.side_effect = _embedding_falso
    cliente.generar.return_value = "La factura consta a fs. 2 (pág. 2)."
    return cliente


def test_serializacion_de_vectores():
    v = [0.5, -1.25, 3.0]
    assert bytes_a_vector(vector_a_bytes(v)) == v


def test_almacen_interno_orden_por_similitud():
    a = AlmacenInterno()
    a.agregar(["x", "y"], [[1.0, 0.0], [0.0, 1.0]])
    resultado = a.buscar([0.9, 0.1], k=2)
    assert resultado[0][0] == "x"
    assert resultado[0][1] > resultado[1][1]


def test_fragmentar_pagina_con_solapamiento():
    texto = "a" * 2500
    frags = fragmentar_pagina(texto, 3)
    assert all(id_.startswith("p3_f") for id_, _, _ in frags)
    assert all(len(t) <= 1000 for _, _, t in frags)
    assert sum(len(t) for _, _, t in frags) >= 2500  # cubre todo (con solape)
    assert fragmentar_pagina("   ", 1) == []


def test_indexar_y_preguntar(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        cliente = _cliente_falso()
        buscador = BuscadorSemantico(cliente, db, "nomic-embed-text")
        paginas = [
            "Informe de avance de la obra pública.",
            "Se adjunta la factura N° 33 del proveedor.",
            "Dictamen jurídico favorable.",
        ]
        indexados = buscador.indexar(paginas)
        assert indexados == 3
        assert buscador.esta_indexado

        resultado = buscador.preguntar("¿dónde está la factura?", "llama3.2")
        assert resultado["pasajes"][0][0] == 2  # página 2 primero
        assert "pág. 2" in resultado["respuesta"]


def test_indice_persistido_se_restaura(tmp_path):
    ruta = tmp_path / "p.db"
    with BaseDatosProyecto(ruta) as db:
        buscador = BuscadorSemantico(_cliente_falso(), db, "nomic-embed-text")
        buscador.indexar(["texto sobre la obra", "texto con factura"])

    # nueva sesión: se restaura sin volver a pedir embeddings de páginas
    with BaseDatosProyecto(ruta) as db:
        cliente = _cliente_falso()
        buscador2 = BuscadorSemantico(cliente, db, "nomic-embed-text")
        assert buscador2.cargar_indice_guardado() is True
        assert buscador2.esta_indexado
        pasajes = buscador2.buscar_pasajes("factura del proveedor")
        assert pasajes[0][0] == 2
        # sólo 1 embedding pedido (la pregunta), ninguno de páginas
        assert cliente.embedding.call_count == 1


def test_preguntar_sin_indice(tmp_path):
    with BaseDatosProyecto(tmp_path / "p.db") as db:
        buscador = BuscadorSemantico(_cliente_falso(), db, "nomic-embed-text")
        resultado = buscador.preguntar("¿qué pasó?", "llama3.2")
        assert resultado["pasajes"] == []
        assert "no" in resultado["respuesta"].lower()
