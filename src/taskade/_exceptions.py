from __future__ import annotations

from typing import Any, Dict

from taskade._types import _T


class TaskadeError(Exception):
    """Base class for Taskade exceptions."""

    pass


class FailedDependencyError(TaskadeError):
    """Error for when all available tasks have at least one failed dependency."""

    def __init__(self: FailedDependencyError, message: str, partial_results: Dict[Any, _T]):
        """
        Initialize the FailedDependencyError.

        :param message: the message to display
        :param partial_results: the partial results of the graph execution
        """
        super().__init__(message)
        self.partial_results = partial_results
