"""Configuración de la aplicación.

La configuración de usuario se guarda en un JSON dentro de la carpeta de
datos del usuario (en Windows: %APPDATA%/AnalizadorExpedientes). Las claves
de API NUNCA se guardan acá: se leen de variables de entorno.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

VERSION_APP = "0.1.0"
# Cambiar esta versión invalida la caché de resúmenes (los prompts cambiaron).
VERSION_PROMPTS = 1

URL_OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
VAR_CLAVE_CLAUDE = "ANTHROPIC_API_KEY"

BLOQUE_PAGINAS_MIN = 10
BLOQUE_PAGINAS_MAX = 30
BLOQUE_PAGINAS_DEFECTO = 15


def carpeta_datos_usuario() -> Path:
    """Carpeta de datos por usuario (config y logs)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "AnalizadorExpedientes"


@dataclass
class Configuracion:
    """Preferencias persistentes del usuario."""

    # Procesamiento
    paginas_por_bloque: int = BLOQUE_PAGINAS_DEFECTO
    idioma_ocr: str = "spa"
    limpiar_ruido: bool = True

    # Ollama
    modelo_resumen: str = "llama3.2"
    modelo_embeddings: str = "nomic-embed-text"

    # Claude (siempre desactivado por defecto; se confirma en cada envío)
    revision_claude_habilitada: bool = False
    modelo_claude: str = "claude-opus-4-8"

    # Salida
    carpeta_salida: str = str(Path.home() / "Expedientes analizados")

    # Interno
    version: str = VERSION_APP
    _extras: dict = field(default_factory=dict, repr=False)

    def validar(self) -> None:
        self.paginas_por_bloque = max(
            BLOQUE_PAGINAS_MIN, min(BLOQUE_PAGINAS_MAX, int(self.paginas_por_bloque))
        )

    # --- persistencia ---

    @classmethod
    def ruta_archivo(cls) -> Path:
        return carpeta_datos_usuario() / "configuracion.json"

    @classmethod
    def cargar(cls) -> "Configuracion":
        ruta = cls.ruta_archivo()
        config = cls()
        if ruta.exists():
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
                for clave, valor in datos.items():
                    if hasattr(config, clave) and not clave.startswith("_"):
                        setattr(config, clave, valor)
            except (json.JSONDecodeError, OSError):
                pass  # configuración corrupta: se usan los valores por defecto
        config.validar()
        return config

    def guardar(self) -> None:
        self.validar()
        ruta = self.ruta_archivo()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        ruta.write_text(
            json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8"
        )
