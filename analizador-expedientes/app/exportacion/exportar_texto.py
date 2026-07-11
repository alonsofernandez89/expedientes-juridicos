"""Exportación del informe a TXT plano y JSON estructurado."""

import json
from datetime import datetime
from pathlib import Path

from app.exportacion.datos_informe import Informe, separar_secciones


def exportar_txt(informe: Informe, ruta: Path) -> None:
    partes = [
        informe.titulo.upper(),
        informe.expediente,
        "=" * 70,
        "",
        "RESUMEN GENERAL DEL EXPEDIENTE",
        "-" * 70,
    ]
    for titulo, cuerpo in separar_secciones(informe.resumen_general):
        if titulo:
            partes += ["", titulo.upper(), "-" * len(titulo)]
        if cuerpo:
            partes.append(cuerpo)
    if informe.cronologia:
        partes += ["", "", "CRONOLOGÍA", "-" * 70]
        for e in informe.cronologia:
            partes.append(
                f"{e.get('fecha_iso', '')}  (pág. {e.get('pagina', '?')})  "
                f"{e.get('contexto', '')}"
            )
    if informe.documentos:
        partes += ["", "", "DOCUMENTACIÓN DETECTADA", "-" * 70]
        for d in informe.documentos:
            partes.append(f"[{d['tipo']}]  (pág. {d['pagina']})  {d['referencia']}")
    if informe.resumenes_parciales:
        partes += ["", "", "ANEXO: RESÚMENES POR BLOQUE", "-" * 70]
        partes += informe.resumenes_parciales
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(partes), encoding="utf-8")


def exportar_json(informe: Informe, ruta: Path) -> None:
    datos = {
        "titulo": informe.titulo,
        "expediente": informe.expediente,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "metadatos": informe.metadatos,
        "resumen_general": {
            "texto": informe.resumen_general,
            "secciones": [
                {"titulo": t, "contenido": c}
                for t, c in separar_secciones(informe.resumen_general)
            ],
        },
        "resumenes_parciales": informe.resumenes_parciales,
        "cronologia": informe.cronologia,
        "documentos_detectados": informe.documentos,
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
