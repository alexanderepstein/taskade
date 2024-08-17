import asyncio
import functools
from typing import Awaitable, Callable, Dict, Optional, Tuple, TypeVar, Union

from tanto._base import Graph, Task

_T = TypeVar("_T")

__graphs: Dict[str, Graph] = {}


def get_graph(graph_name: str) -> Optional[Graph]:
    """
    Retrieve a graph by name from the global graph dictionary.

    :param graph_name: The name of the graph to retrieve
    :return: The retrieved Graph object or None if not found
    """
    return __graphs.get(graph_name)


def task(
    graph_name: str,
    *,
    dependencies: Union[Task, Tuple[Task, ...]] = (),
    input_names: Tuple[str, ...] = (),
    pre_call: Optional[
        Callable[
            [
                _T,
            ],
            Tuple[_T, ...],
        ]
    ] = None,
    post_call: Optional[Callable[[_T], None]] = None,
    name: Optional[str] = None,
) -> Callable[[Callable[..., Union[_T, Awaitable[_T]]]], Callable[..., Union[_T, Awaitable[_T]]]]:
    """
    Decorator to create a Task with its dependencies and associate it with a named graph.

    :param graph_name: The name of the graph to associate the task with
    :param dependencies: A tuple of Task objects that this task depends on
    :param input_names: A tuple of input names for the task
    :param pre_call: An optional function to be called before the task execution
    :param post_call: An optional function to be called after the task execution
    :param name: An optional name for the task
    :return: A decorator function that wraps the task function
    """

    def decorator(
        func: Callable[..., Union[_T, Awaitable[_T]]],
    ) -> Callable[..., Union[_T, Awaitable[_T]]]:
        """
        Inner decorator function that wraps the task function.

        :param func: The function to be wrapped as a task
        :return: The wrapped task function
        """

        @functools.wraps(func)
        def wrapped_function(*args, **kwargs):
            """
            Wrapper function that executes the original task function.

            :param args: Positional arguments to pass to the task function
            :param kwargs: Keyword arguments to pass to the task function
            :return: The result of the task function execution
            """
            return func(*args, **kwargs)

        # Retrieve or create the graph
        graph = __graphs.get(graph_name)
        if graph is None:
            graph = Graph()
            __graphs[graph_name] = graph

        # Create a Task using the decorated function and its parameters
        task_instance = Task(
            func=wrapped_function,
            dependencies=dependencies,
            _graph=graph,
            _is_async=asyncio.iscoroutinefunction(func),
            input_names=input_names,
            pre_call=pre_call,
            post_call=post_call,
            name=name if name else func.__name__,
        )

        # Add the task to the graph
        graph += task_instance

        return task_instance

    return decorator
