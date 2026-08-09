"""Punto de entrada de la aplicación de escritorio.

Uso:  python main.py
"""

import sys

from app.config.settings import carpeta_datos_usuario
from app.utils.registro import configurar_registro


def main() -> int:
    log = configurar_registro(carpeta_datos_usuario() / "logs")
    log.info("Aplicación iniciada")

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "Falta PySide6. Instalá las dependencias con:\n"
            "  pip install -r requirements.txt"
        )
        return 1

    from app.interfaz.ventana_principal import VentanaPrincipal

    app = QApplication(sys.argv)
    app.setApplicationName("Analizador de Expedientes")
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
