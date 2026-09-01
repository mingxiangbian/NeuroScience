"""Website factory for the sequential M1/M3 runtime."""
from functools import partial

from .app import create_app as base_app
from .staged_worker import StagedDispatcher


def create_app(*, observer=None, **kwargs):
    return base_app(dispatcher_factory=partial(StagedDispatcher, observer=observer), **kwargs)
