"""División del expediente en bloques de páginas para resumir por partes."""

from dataclasses import dataclass

from app.config.settings import BLOQUE_PAGINAS_MAX, BLOQUE_PAGINAS_MIN


@dataclass
class Bloque:
    indice: int          # 0-based
    pagina_desde: int    # 1-based, inclusive
    pagina_hasta: int    # 1-based, inclusive
    texto: str           # texto de las páginas, con marcadores [Página N]

    @property
    def etiqueta(self) -> str:
        return f"Bloque {self.indice + 1} (páginas {self.pagina_desde}–{self.pagina_hasta})"


def dividir_en_bloques(
    paginas: list[str],
    paginas_por_bloque: int,
    paginas_vacias: set[int] | None = None,
) -> list[Bloque]:
    """Agrupa las páginas en bloques consecutivos.

    - `paginas` es la lista 0-based del texto (limpio) de cada página.
    - Las páginas vacías (1-based en `paginas_vacias`) no aportan texto pero
      no rompen la numeración: cada fragmento se antecede con `[Página N]`
      para que el modelo pueda citar la página de origen.
    """
    tam = max(BLOQUE_PAGINAS_MIN, min(BLOQUE_PAGINAS_MAX, int(paginas_por_bloque)))
    vacias = paginas_vacias or set()
    bloques: list[Bloque] = []
    total = len(paginas)
    for inicio in range(0, total, tam):
        fin = min(inicio + tam, total)
        partes = []
        for i in range(inicio, fin):
            numero = i + 1
            if numero in vacias:
                continue
            texto = paginas[i].strip()
            if not texto:
                continue
            partes.append(f"[Página {numero}]\n{texto}")
        contenido = "\n\n".join(partes)
        if not contenido:
            continue  # bloque compuesto solo de páginas vacías
        bloques.append(
            Bloque(
                indice=len(bloques),
                pagina_desde=inicio + 1,
                pagina_hasta=fin,
                texto=contenido,
            )
        )
    return bloques
