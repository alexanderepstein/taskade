from typing import Any, List, Optional, Tuple

class TopologicalSorter:
    """
    A class for performing topological sorting on a graph.

    This class provides methods to add nodes and their dependencies,
    prepare the graph for processing, and iterate through the nodes
    in topological order.
    """

    def __init__(self, initial_capacity: int = ...) -> None:
        """
        Initialize a new TopologicalSorter instance.

        Args:
            initial_capacity: The initial capacity for the internal data structures.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c

    def add(self, node: Any, predecessors: Optional[Tuple[Any, ...]] = ...) -> None:
        """
        Add a node and its predecessors to the graph.

        Args:
            node: The node to add.
            predecessors: A tuple of predecessor nodes.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c

    def prepare(self) -> None:
        """
        Prepare the graph for processing.

        This method should be called after all nodes have been added
        and before starting to process the nodes.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c

    def get_ready(self) -> List[Any]:
        """
        Get a list of nodes that are ready to be processed.

        Returns:
            A list of nodes with no unprocessed predecessors.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c

    def done(self, node: Any) -> None:
        """
        Mark a node as done.

        This method should be called after a node has been processed.

        Args:
            node: The node to mark as done.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c

    def is_active(self) -> bool:
        """
        Check if the sorter is still active.

        Returns:
            True if there are still nodes to be processed, False otherwise.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c

    def static_order(self) -> List[Any]:
        """
        Return a static ordering of the graph.

        This method processes the entire graph and returns a list of
        all nodes in topological order.

        Returns:
            A list of all nodes in topological order.
        """
        ...  # A stub, the actual implementation is in cgraphlib.c
