from typing import Awaitable, Callable, Dict, Optional, Tuple, Union, cast

from taskade._execution import Graph, PostCallProtocol, PreCallProtocol, Task, _get_graph
from taskade._types import _T


def __map_dependencies(
    graph_name: str,
    task_name: Optional[str],
    dependencies: Union[Union[Tuple[str, ...], str], Union[Task, Tuple[Task, ...]]],
) -> Tuple[Task, ...]:
    """
    Map dependencies to Task objects, needed for multiple decorators on the same function
    as dependencies will use the task name instead of the task object directly.

    :param graph_name: name of the graph
    :param task_name: name of the task
    :param dependencies: dependencies of the task, can be an individual element or a tuple of elements where the elements are either Task objects or names of tasks within the same graph
    :raises ValueError: if the dependency is not found in the graph
    :return: tuple of Task objects
    """
    if isinstance(dependencies, str):
        dependencies = (dependencies,)
    if isinstance(dependencies, tuple) and len(dependencies) > 0 and isinstance(dependencies[0], str):
        dependencies = cast(Tuple[str, ...], dependencies)
        mapped_dependencies = []
        for dependency in dependencies:
            try:
                mapped_dependencies.append(_get_graph()[graph_name][dependency])
            except KeyError:
                raise ValueError(
                    f"Task {task_name} within graph {graph_name} has a dependency {dependency} on a function that has not been decorated or names for decorated functions are misaligned to their dependency usage."
                )
        dependencies = tuple(mapped_dependencies)
    return cast(Tuple[Task, ...], dependencies)


def __retrieve_or_create_graph(graph_name: str) -> Graph:
    """
    Retrieve a graph by name from the global graph dictionary or create a new graph if not found.

    :param graph_name: The name of the graph to retrieve or create
    :return: The retrieved or created Graph object
    """
    graph = _get_graph().get(graph_name)
    if graph is None:
        graph = Graph(name=graph_name)
        _get_graph()[graph_name] = graph
    return graph


def task(
    graph_name: str,
    *,
    dependencies: Union[Union[Tuple[str, ...], str], Union[Task, Tuple[Task, ...]]] = (),
    output_names: Tuple[str, ...] = (),
    pre_call: Optional[PreCallProtocol] = None,
    post_call: Optional[PostCallProtocol] = None,
    name: Optional[str] = None,
    init_kwargs: Optional[Dict[str, _T]] = None,
) -> Callable[..., Task]:
    """
    Decorator to create a Task with its dependencies and associate it with a named graph.

    :param graph_name: The name of the graph to associate the task with
    :param dependencies: A tuple of Task objects or names of tasks within the same graph that this task depends on
    :param output_names: A tuple of output names for the task
    :param pre_call: An optional function to be called before the task execution, defaults to None
    :param post_call: An optional function to be called after the task execution, defaults to None
    :param name: An optional name for the task, defaults to None
    :param init_kwargs: Optional kwargs to use for executing the task, defaults to None
    :return: A decorator function that wraps the task function
    """

    def decorator(
        func: Union[Dict[str, Dict[str, Task]], Union[Task, Callable[..., Union[_T, Awaitable[_T]]]]],
        name: Optional[str] = name,
        dependencies: Union[Union[Tuple[str, ...], str], Union[Task, Tuple[Task, ...]]] = dependencies,
    ) -> Task:
        """
        Inner decorator function that wraps the task function.

        :param func: The function to be wrapped as a task
        :param name: An optional name for the task
        :param dependencies: A tuple of Task objects or names of tasks within the same graph that this task depends on
        :return: The wrapped task function
        """
        # Allow for multiple uses of the decorator on the same function
        if isinstance(func, Task):
            func = func.func
        func = cast(Callable[..., Union[_T, Awaitable[_T]]], func)
        name = name if name else func.__name__
        graph = __retrieve_or_create_graph(graph_name)

        task_instance = Task(
            func=func,
            dependencies=__map_dependencies(graph_name, name, dependencies),
            _graph=graph,
            output_names=output_names,
            pre_call=pre_call,
            post_call=post_call,
            name=name,
            init_kwargs=init_kwargs,
        )

        # Add the task to the graph
        graph += task_instance
        return task_instance

    return decorator
