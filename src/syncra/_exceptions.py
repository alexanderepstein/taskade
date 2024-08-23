from __future__ import annotations

from typing import Dict

from syncra._types import _T


class SyncraError(Exception):
    """Base class for Syncra exceptions."""

    pass


class FailedDependencyError(SyncraError):
    """Error for when all available tasks have at least one failed dependency."""

    def __init__(self: SyncraError, message: str, partial_results: Dict[str, _T]):
        """
        Initialize the FailedDependencyError.

        :param message: the message to display
        :param partial_results: the partial results of the graph execution
        """
        super().__init__(message)
        self.partial_results = partial_results
