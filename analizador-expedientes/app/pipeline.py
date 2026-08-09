"""Orquestador del procesamiento de un expediente.

Encadena los módulos (OCR → extracción → limpieza → análisis → bloques →
resumen) sin depender de la interfaz: la GUI lo ejecuta en un hilo y recibe
avisos por los callbacks `progreso(mensaje)` y `progreso_parcial(actual,
total, etapa)`.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.almacenamiento.base_datos import BaseDatosProyecto
from app.analisis.cronologia import construir_cronologia
from app.analisis.documentos import detectar_documentos
from app.bloques.divisor import Bloque, dividir_en_bloques
from app.config.settings import Configuracion
from app.extraccion.extractor import (
    extraer_paginas,
    guardar_json,
    guardar_txt,
    verificar_texto_detectado,
)
from app.extraccion.limpieza import limpiar_paginas
from app.ocr.motor_ocr import copiar_original, ejecutar_ocr, validar_pdf
from app.resumen.cliente_ollama import ClienteOllama
from app.resumen.resumidor import Resumidor
from app.utils.registro import obtener_logger

log = obtener_logger("pipeline")


def _nombre_proyecto(ruta_pdf: Path) -> str:
    base = re.sub(r"[^\w\-. ]", "_", ruta_pdf.stem).strip() or "expediente"
    return base


@dataclass
class ResultadoProcesamiento:
    carpeta: Path
    total_paginas: int = 0
    paginas: list[str] = field(default_factory=list)          # texto crudo
    paginas_limpias: list[str] = field(default_factory=list)
    paginas_vacias: list[int] = field(default_factory=list)
    bloques: list[Bloque] = field(default_factory=list)
    cronologia: list[dict] = field(default_factory=list)
    documentos: list[dict] = field(default_factory=list)
    resumenes_parciales: list[str] = field(default_factory=list)
    resumen_general: str = ""


class ProcesadorExpediente:
    """Ejecuta el flujo completo sobre un PDF. Reutilizable desde la GUI o CLI."""

    def __init__(
        self,
        config: Configuracion,
        progreso=None,        # callable(str)
        progreso_parcial=None,  # callable(actual, total, etapa)
        cancelado=None,       # callable() -> bool
    ):
        self.config = config
        self._progreso = progreso or (lambda m: None)
        self._parcial = progreso_parcial or (lambda a, t, e: None)
        self._cancelado = cancelado or (lambda: False)

    # ------------------------------------------------------------------
    def preparar_proyecto(self, ruta_pdf: Path) -> Path:
        """Crea la carpeta del proyecto y copia el PDF original intacto."""
        carpeta = Path(self.config.carpeta_salida) / _nombre_proyecto(ruta_pdf)
        carpeta.mkdir(parents=True, exist_ok=True)
        copiar_original(ruta_pdf, carpeta)
        return carpeta

    def procesar_hasta_texto(self, ruta_pdf: Path) -> ResultadoProcesamiento:
        """Etapas locales sin LLM: validación, OCR, extracción, limpieza,
        análisis y división en bloques. Todo queda persistido en el proyecto."""
        self._progreso("Validando el PDF…")
        validar_pdf(ruta_pdf)

        carpeta = self.preparar_proyecto(ruta_pdf)
        resultado = ResultadoProcesamiento(carpeta=carpeta)
        pdf_ocr = carpeta / "ocr.pdf"

        self._progreso("Ejecutando OCR (puede tardar varios minutos)…")
        ejecutar_ocr(
            carpeta / "original.pdf",
            pdf_ocr,
            idioma=self.config.idioma_ocr,
            progreso=self._progreso,
        )

        self._progreso("Extrayendo texto por página…")
        paginas = extraer_paginas(pdf_ocr)
        verificar_texto_detectado(paginas)
        resultado.paginas = paginas
        resultado.total_paginas = len(paginas)
        guardar_txt(paginas, carpeta / "texto_completo.txt")
        guardar_json(paginas, carpeta / "texto_por_pagina.json")

        with BaseDatosProyecto(carpeta / "proyecto.db") as db:
            db.guardar_paginas(paginas)
            db.guardar_meta("nombre", carpeta.name)
            db.guardar_meta("total_paginas", len(paginas))
            db.guardar_meta("fecha_procesado", date.today().isoformat())

            if self.config.limpiar_ruido:
                self._progreso("Detectando encabezados, sellos y páginas vacías…")
                limpieza = limpiar_paginas(paginas)
                resultado.paginas_limpias = limpieza.paginas_limpias
                resultado.paginas_vacias = limpieza.paginas_vacias
                for i, (texto, eliminadas) in enumerate(
                    zip(limpieza.paginas_limpias, limpieza.eliminadas_por_pagina),
                    start=1,
                ):
                    db.actualizar_limpieza(
                        i, texto, i in limpieza.paginas_vacias, eliminadas
                    )
                db.guardar_meta("patrones_ruido", limpieza.patrones_detectados)
            else:
                resultado.paginas_limpias = paginas

            self._progreso("Construyendo cronología y detectando documentos…")
            resultado.cronologia = construir_cronologia(resultado.paginas_limpias)
            resultado.documentos = detectar_documentos(resultado.paginas_limpias)
            db.guardar_cronologia(resultado.cronologia)
            db.guardar_documentos(resultado.documentos)

        resultado.bloques = dividir_en_bloques(
            resultado.paginas_limpias,
            self.config.paginas_por_bloque,
            set(resultado.paginas_vacias),
        )
        self._progreso(
            f"Listo: {resultado.total_paginas} páginas en "
            f"{len(resultado.bloques)} bloques."
        )
        return resultado

    def resumir(self, resultado: ResultadoProcesamiento) -> ResultadoProcesamiento:
        """Resumen por bloques + resumen general con Ollama (usa la caché)."""
        cliente = ClienteOllama()
        with BaseDatosProyecto(resultado.carpeta / "proyecto.db") as db:
            resumidor = Resumidor(cliente, db, self.config.modelo_resumen)
            self._progreso(
                f"Resumiendo {len(resultado.bloques)} bloques con "
                f"{self.config.modelo_resumen}…"
            )
            resultado.resumenes_parciales = resumidor.resumir_bloques(
                resultado.bloques,
                progreso=lambda a, t, c: self._parcial(a, t, "resumen"),
                cancelado=self._cancelado,
            )
            if self._cancelado():
                return resultado
            self._progreso("Generando el resumen general…")
            resultado.resumen_general = resumidor.resumen_general(
                resultado.resumenes_parciales
            )
        return resultado

    # ------------------------------------------------------------------
    @staticmethod
    def cargar_proyecto(carpeta: Path) -> ResultadoProcesamiento | None:
        """Reabre un proyecto ya procesado sin repetir OCR ni resúmenes."""
        ruta_db = Path(carpeta) / "proyecto.db"
        if not ruta_db.exists():
            return None
        resultado = ResultadoProcesamiento(carpeta=Path(carpeta))
        with BaseDatosProyecto(ruta_db) as db:
            paginas = db.leer_paginas()
            if not paginas:
                return None
            resultado.paginas = [p["texto"] for p in paginas]
            resultado.paginas_limpias = [
                p["texto_limpio"] if p["texto_limpio"] is not None else p["texto"]
                for p in paginas
            ]
            resultado.paginas_vacias = [
                p["numero"] for p in paginas if p["es_vacia"]
            ]
            resultado.total_paginas = len(paginas)
            resultado.cronologia = db.leer_cronologia()
            resultado.documentos = db.leer_documentos()
            resultado.resumenes_parciales = [
                f"### Bloque {r['indice_bloque'] + 1} "
                f"(páginas {r['pagina_desde']}–{r['pagina_hasta']})\n\n{r['resumen']}"
                for r in db.leer_resumenes()
            ]
            resultado.resumen_general = db.leer_resumen_general() or ""
        return resultado
