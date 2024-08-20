from typing import Dict, Self, TypeVar

_T = TypeVar("_T")
"""Type variable for the return type of a task"""


class TantoError(Exception):
    """Base class for Tanto exceptions."""

    pass


class FailedDependencyError(TantoError):
    """Error for when all available tasks have at least one failed dependency."""

    def __init__(self: Self, message: str, partial_results: Dict[str, _T]):
        """
        Initialize the FailedDependencyError.

        :param message: the message to display
        :param partial_results: the partial results of the graph execution
        """
        super().__init__(message)
        self.partial_results = partial_results
