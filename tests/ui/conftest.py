"""Configurazione pytest condivisa per i test della UI.

Questi test girano anche su CI headless con la piattaforma Qt "offscreen"
(vedi ``tests/conftest.py``). In quell'ambiente non c'è alcun utente che possa
chiudere i dialog modali: qualsiasi ``QMessageBox`` o ``QDialog.exec()`` modale
bloccherebbe il test all'infinito.

La fixture autouse qui sotto neutralizza in modo centralizzato tutti i dialog
modali, così nessun test UI può restare appeso indipendentemente dal percorso
di codice che esercita. I test che vogliono asserire su uno specifico dialog
possono comunque sovrascrivere il mock localmente con ``patch`` mirato.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox


@pytest.fixture(autouse=True)
def _neutralize_modal_dialogs(monkeypatch):
    """Rende non bloccanti tutti i dialog modali durante i test UI."""
    # QMessageBox: i metodi statici ritornano un pulsante di default senza
    # mostrare nulla.
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    monkeypatch.setattr(
        QMessageBox, "about", staticmethod(lambda *a, **k: None)
    )
    # Istanze di QMessageBox/QDialog mostrate con exec(): ritorna subito invece
    # di entrare in un loop modale.
    monkeypatch.setattr(QMessageBox, "exec", lambda self, *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: QDialog.DialogCode.Accepted.value)
    yield
