"""Piccole utilità Qt condivise dai widget."""

from PyQt6.QtWidgets import QWidget


def repolish(widget: QWidget) -> None:
    """Riapplica lo stylesheet dopo il cambio di una property dinamica (es. ``invalid``).

    ``QWidget.style()`` è ``QStyle | None`` negli stub di PyQt6, anche se un widget ha sempre uno stile.
    """
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
