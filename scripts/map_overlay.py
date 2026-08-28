"""Compatibility hook for maps without fixed canvas overlays."""

from __future__ import annotations

from typing import Final

from branca.element import MacroElement

def build_overlay(data_sources: frozenset[str]) -> MacroElement:
    """Return an empty compatibility element; Leaflet controls own the canvas UI."""
    return MacroElement()
