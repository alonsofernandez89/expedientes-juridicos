"""Persistencia del proyecto en SQLite.

Cada expediente procesado es un "proyecto": una carpeta con los archivos
generados y un `proyecto.db` con todo el estado (texto por página, resúmenes
parciales cacheados, cronología, documentos detectados, embeddings).

La caché de resúmenes se indexa por hash SHA-256 de
(contenido del bloque + modelo + versión de prompt): si nada de eso cambió,
el bloque no se vuelve a enviar al modelo.
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS proyecto (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
CREATE TABLE IF NOT EXISTS paginas (
    numero INTEGER PRIMARY KEY,          -- 1-based, igual que en el PDF
    texto TEXT NOT NULL,
    texto_limpio TEXT,
    es_vacia INTEGER DEFAULT 0,
    lineas_eliminadas TEXT               -- JSON: ruido quitado (auditoría)
);
CREATE TABLE IF NOT EXISTS resumenes (
    hash TEXT PRIMARY KEY,               -- sha256(contenido+modelo+version)
    indice_bloque INTEGER,
    pagina_desde INTEGER,
    pagina_hasta INTEGER,
    modelo TEXT,
    resumen TEXT NOT NULL,
    creado REAL
);
CREATE TABLE IF NOT EXISTS resumen_general (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    modelo TEXT,
    texto TEXT NOT NULL,
    creado REAL
);
CREATE TABLE IF NOT EXISTS cronologia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_iso TEXT,                      -- YYYY-MM-DD para ordenar
    fecha_texto TEXT,                    -- como aparece en el documento
    contexto TEXT,
    pagina INTEGER
);
CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT,                           -- resolución, nota, decreto...
    referencia TEXT,                     -- línea donde se detectó
    pagina INTEGER
);
CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,                 -- p<página>_f<fragmento>
    pagina INTEGER,
    texto TEXT,
    vector BLOB,                         -- float32 empaquetado
    modelo TEXT
);
"""


def hash_bloque(contenido: str, modelo: str, version_prompt: int) -> str:
    base = f"{contenido}\x00{modelo}\x00{version_prompt}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


class BaseDatosProyecto:
    """Acceso a `proyecto.db`. Uso: with BaseDatosProyecto(ruta) as db: ..."""

    def __init__(self, ruta_db: Path):
        self.ruta_db = Path(ruta_db)
        self.ruta_db.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.ruta_db))
        self._con.row_factory = sqlite3.Row
        self._con.executescript(_ESQUEMA)
        self._con.commit()

    # --- ciclo de vida ---

    def cerrar(self) -> None:
        self._con.close()

    def __enter__(self) -> "BaseDatosProyecto":
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()

    # --- metadatos del proyecto ---

    def guardar_meta(self, clave: str, valor) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO proyecto (clave, valor) VALUES (?, ?)",
            (clave, json.dumps(valor, ensure_ascii=False)),
        )
        self._con.commit()

    def leer_meta(self, clave: str, defecto=None):
        fila = self._con.execute(
            "SELECT valor FROM proyecto WHERE clave = ?", (clave,)
        ).fetchone()
        return json.loads(fila["valor"]) if fila else defecto

    # --- páginas ---

    def guardar_paginas(self, textos: list[str]) -> None:
        """Guarda el texto crudo de todas las páginas (1-based)."""
        self._con.execute("DELETE FROM paginas")
        self._con.executemany(
            "INSERT INTO paginas (numero, texto) VALUES (?, ?)",
            [(i + 1, t) for i, t in enumerate(textos)],
        )
        self._con.commit()

    def actualizar_limpieza(
        self, numero: int, texto_limpio: str, es_vacia: bool, lineas_eliminadas: list[str]
    ) -> None:
        self._con.execute(
            "UPDATE paginas SET texto_limpio=?, es_vacia=?, lineas_eliminadas=? "
            "WHERE numero=?",
            (texto_limpio, int(es_vacia), json.dumps(lineas_eliminadas, ensure_ascii=False), numero),
        )
        self._con.commit()

    def leer_paginas(self) -> list[dict]:
        filas = self._con.execute(
            "SELECT numero, texto, texto_limpio, es_vacia FROM paginas ORDER BY numero"
        ).fetchall()
        return [dict(f) for f in filas]

    # --- caché de resúmenes parciales ---

    def buscar_resumen(self, hash_: str) -> str | None:
        fila = self._con.execute(
            "SELECT resumen FROM resumenes WHERE hash = ?", (hash_,)
        ).fetchone()
        return fila["resumen"] if fila else None

    def guardar_resumen(
        self,
        hash_: str,
        indice_bloque: int,
        pagina_desde: int,
        pagina_hasta: int,
        modelo: str,
        resumen: str,
    ) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO resumenes "
            "(hash, indice_bloque, pagina_desde, pagina_hasta, modelo, resumen, creado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hash_, indice_bloque, pagina_desde, pagina_hasta, modelo, resumen, time.time()),
        )
        self._con.commit()

    def leer_resumenes(self) -> list[dict]:
        filas = self._con.execute(
            "SELECT indice_bloque, pagina_desde, pagina_hasta, modelo, resumen "
            "FROM resumenes ORDER BY indice_bloque"
        ).fetchall()
        return [dict(f) for f in filas]

    # --- resumen general ---

    def guardar_resumen_general(self, modelo: str, texto: str) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO resumen_general (id, modelo, texto, creado) "
            "VALUES (1, ?, ?, ?)",
            (modelo, texto, time.time()),
        )
        self._con.commit()

    def leer_resumen_general(self) -> str | None:
        fila = self._con.execute(
            "SELECT texto FROM resumen_general WHERE id = 1"
        ).fetchone()
        return fila["texto"] if fila else None

    # --- cronología ---

    def guardar_cronologia(self, eventos: list[dict]) -> None:
        self._con.execute("DELETE FROM cronologia")
        self._con.executemany(
            "INSERT INTO cronologia (fecha_iso, fecha_texto, contexto, pagina) "
            "VALUES (:fecha_iso, :fecha_texto, :contexto, :pagina)",
            eventos,
        )
        self._con.commit()

    def leer_cronologia(self) -> list[dict]:
        filas = self._con.execute(
            "SELECT fecha_iso, fecha_texto, contexto, pagina FROM cronologia "
            "ORDER BY fecha_iso, pagina"
        ).fetchall()
        return [dict(f) for f in filas]

    # --- documentos detectados ---

    def guardar_documentos(self, documentos: list[dict]) -> None:
        self._con.execute("DELETE FROM documentos")
        self._con.executemany(
            "INSERT INTO documentos (tipo, referencia, pagina) "
            "VALUES (:tipo, :referencia, :pagina)",
            documentos,
        )
        self._con.commit()

    def leer_documentos(self) -> list[dict]:
        filas = self._con.execute(
            "SELECT tipo, referencia, pagina FROM documentos ORDER BY pagina, id"
        ).fetchall()
        return [dict(f) for f in filas]

    # --- embeddings ---

    def guardar_embeddings(self, registros: list[tuple[str, int, str, bytes, str]]) -> None:
        self._con.executemany(
            "INSERT OR REPLACE INTO embeddings (id, pagina, texto, vector, modelo) "
            "VALUES (?, ?, ?, ?, ?)",
            registros,
        )
        self._con.commit()

    def leer_embeddings(self, modelo: str) -> list[dict]:
        filas = self._con.execute(
            "SELECT id, pagina, texto, vector FROM embeddings WHERE modelo = ?",
            (modelo,),
        ).fetchall()
        return [dict(f) for f in filas]

    def borrar_embeddings(self) -> None:
        self._con.execute("DELETE FROM embeddings")
        self._con.commit()
