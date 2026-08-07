"""Gunicorn entry point for production. `run.py` remains the local dev entry point."""

from alphalab.api.routes import create_app

app = create_app()
