"""Presentation layer (upper layer, Decepticon-style).

Subscribes to the orchestrator's on_event stream and renders a live view.
Nothing here affects agent behavior — it only observes.
"""
from .banner import show_banner

__all__ = ["show_banner"]
