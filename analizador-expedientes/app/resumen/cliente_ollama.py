"""Cliente de la API HTTP local de Ollama (http://localhost:11434).

Se usa `requests` directamente para poder distinguir con precisión:
- Ollama no está corriendo (conexión rechazada) → OllamaNoDisponible;
- el modelo pedido no está descargado → ModeloNoInstalado;
- memoria insuficiente al cargar el modelo → MemoriaInsuficiente.
"""

import requests

from app.config.settings import URL_OLLAMA
from app.utils.errores import (
    MemoriaInsuficiente,
    ModeloNoInstalado,
    OllamaNoDisponible,
)
from app.utils.registro import obtener_logger

log = obtener_logger("ollama")

TIMEOUT_CONSULTA = 600   # los modelos locales pueden tardar varios minutos
TIMEOUT_CORTO = 10


class ClienteOllama:
    def __init__(self, url_base: str = URL_OLLAMA):
        self.url_base = url_base.rstrip("/")

    def esta_activo(self) -> bool:
        try:
            r = requests.get(f"{self.url_base}/api/version", timeout=TIMEOUT_CORTO)
            return r.ok
        except requests.RequestException:
            return False

    def listar_modelos(self) -> list[str]:
        """Nombres de los modelos instalados. Lanza OllamaNoDisponible."""
        try:
            r = requests.get(f"{self.url_base}/api/tags", timeout=TIMEOUT_CORTO)
            r.raise_for_status()
        except requests.RequestException as e:
            raise OllamaNoDisponible(detalle=str(e))
        return [m["name"] for m in r.json().get("models", [])]

    def _verificar_modelo(self, modelo: str) -> None:
        instalados = self.listar_modelos()
        # "llama3.2" debe aceptar "llama3.2:latest"
        base = modelo.split(":")[0]
        if not any(m == modelo or m.split(":")[0] == base for m in instalados):
            raise ModeloNoInstalado(modelo)

    def generar(self, modelo: str, prompt: str, sistema: str = "") -> str:
        """Genera una respuesta completa (sin streaming)."""
        self._verificar_modelo(modelo)
        datos = {
            "model": modelo,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if sistema:
            datos["system"] = sistema
        try:
            r = requests.post(
                f"{self.url_base}/api/generate", json=datos, timeout=TIMEOUT_CONSULTA
            )
        except requests.ConnectionError as e:
            raise OllamaNoDisponible(detalle=str(e))
        except requests.Timeout as e:
            raise OllamaNoDisponible(
                detalle=f"Ollama no respondió en {TIMEOUT_CONSULTA} s: {e}"
            )
        if r.status_code == 404:
            raise ModeloNoInstalado(modelo, detalle=r.text)
        if r.status_code == 500 and "memory" in r.text.lower():
            raise MemoriaInsuficiente(detalle=r.text)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise OllamaNoDisponible(detalle=str(e))
        respuesta = r.json().get("response", "").strip()
        log.info(
            "Ollama generó %d caracteres con %s (prompt de %d caracteres)",
            len(respuesta), modelo, len(prompt),
        )
        return respuesta

    def embedding(self, modelo: str, texto: str) -> list[float]:
        """Vector de embedding local para la búsqueda semántica."""
        try:
            r = requests.post(
                f"{self.url_base}/api/embeddings",
                json={"model": modelo, "prompt": texto},
                timeout=TIMEOUT_CONSULTA,
            )
        except requests.RequestException as e:
            raise OllamaNoDisponible(detalle=str(e))
        if r.status_code == 404:
            raise ModeloNoInstalado(modelo, detalle=r.text)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise OllamaNoDisponible(detalle=str(e))
        vector = r.json().get("embedding", [])
        if not vector:
            raise ModeloNoInstalado(
                modelo,
                detalle="El modelo no devolvió embeddings; usá un modelo de "
                "embeddings como nomic-embed-text.",
            )
        return vector
