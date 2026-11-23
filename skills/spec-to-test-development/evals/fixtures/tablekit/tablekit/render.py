"""Plain-text table rendering."""


def _pad(cell: str, width: int) -> str:
    return cell + " " * (width - len(cell))


def render_table(rows: list[list[str]]) -> str:
    """Render rows as a pipe-separated table with aligned columns.

    Every row must have the same number of cells. Raises ValueError otherwise.
    Returns "" for an empty list.
    """
    if not rows:
        return ""
    ncols = len(rows[0])
    if any(len(r) != ncols for r in rows):
        raise ValueError("all rows must have the same number of cells")
    widths = [max(len(r[i]) for r in rows) for i in range(ncols)]
    lines = []
    for r in rows:
        lines.append("| " + " | ".join(_pad(c, w) for c, w in zip(r, widths)) + " |")
    return "\n".join(lines)
