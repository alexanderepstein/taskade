from __future__ import annotations

import asyncio
import inspect
import weakref
from collections import UserDict
from dataclasses import dataclass, field
from functools import wraps
from graphlib import TopologicalSorter
from typing import (Awaitable, Callable, Dict, Optional, Protocol, Tuple,
                    TypeVar, Union, cast)

_T = TypeVar("_T")


class GraphResults(UserDict):
    def __getitem__(self, key: Task) -> _T:
        if isinstance(key, Task):
            key = hash(key)
        return super().__getitem__(key)


def pass_through(*args: Tuple[_T, ...]) -> Tuple[_T, ...]:
    return args


def eat(*args: Tuple[_T, ...]) -> Tuple:
    return ()


class PreCallProtocol(Protocol):
    def __call__(self, *args: Tuple[_T, ...]) -> Tuple[_T, ...]: ...


class PostCallProtocol(Protocol):
    def __call__(self, *args: Tuple[_T, ...]) -> None: ...


class ExecuteGraphProtocol(Protocol):
    def __call__(
        self,
        graph: Graph,
        pre_call: Callable[
            [
                _T,
            ],
            Tuple[_T],
        ],
        post_call: Optional[Callable[[_T], None]],
        raise_immediately: bool,
        validate_graph: bool,
    ) -> Dict[str, _T]: ...


async def _aproducer(task: Task, coro: Awaitable[_T], result_queue: asyncio.Queue) -> None:
    try:
        result = await coro
    except Exception as e:
        result = e
    await result_queue.put((task, result))


async def _aconsumer(result_queue: asyncio.Queue, raise_immediately: bool) -> Tuple[Task, _T]:
    task, result = await result_queue.get()
    if isinstance(result, Exception):
        if raise_immediately:
            raise result
    result_queue.task_done()
    return task, result


async def aexecute_graph(
    graph: Graph,
    pre_call: Callable[
        [
            _T,
        ],
        Tuple[_T],
    ] = pass_through,
    post_call: Optional[Callable[[_T], None]] = None,
    raise_immediately: bool = True,
    validate_graph: bool = False,
) -> Dict[str, _T]:
    graph.prepare()
    result_queue = asyncio.Queue()
    results: Dict[Task, _T] = {}
    while graph.is_active():
        for available_task in graph.get_ready():
            available_task = cast(Task, available_task)
            if not available_task._is_async:

                @wraps(available_task.func)
                async def async_wrapper(*args, **kwargs):
                    return available_task.func(*args, **kwargs)

                executing_func = async_wrapper
            else:
                executing_func = available_task.func

            call_args = getattr(available_task, pre_call.__name__, pre_call)(
                *(results[dependent_task] for dependent_task in available_task.dependencies)
            )
            if len(available_task.input_names):
                call_args = {name: arg for name, arg in zip(available_task.input_names, call_args)}
            asyncio.create_task(_aproducer(available_task, executing_func(*call_args), result_queue))
        task, result = await _aconsumer(result_queue, raise_immediately)
        if post_call:
            post_call(
                result,
                *(result[dependent_task] for dependent_task in task.dependencies),
            )
        graph.done(task)
        results[task] = result
    return GraphResults({hash(task): result for task, result in results.items()})


def execute_graph(
    graph: Graph,
    pre_call: Callable[
        [
            _T,
        ],
        Tuple[_T],
    ] = pass_through,
    post_call: Optional[Callable[[_T], None]] = None,
    raise_immediately: bool = True,
    validate_graph: bool = False,
) -> Dict[str, _T]:
    graph.prepare()
    results: Dict[Task, _T] = {}
    while graph.is_active():
        for available_task in graph.get_ready():
            available_task = cast(Task, available_task)
            call_args = getattr(available_task, pre_call.__name__, pre_call)(
                *(results[dependent_task] for dependent_task in available_task.dependencies)
            )
            if len(available_task.input_names):
                call_args = {name: arg for name, arg in zip(available_task.input_names, call_args)}
            result = available_task.func(*call_args)
            if post_call:
                post_call(
                    result,
                    *(result[dependent_task] for dependent_task in available_task.dependencies),
                )
            graph.done(available_task)
            results[available_task] = result
    return GraphResults({hash(task): result for task, result in results.items()})


class Graph(TopologicalSorter):
    def __init__(self, tasks: Optional[Tuple[Union[Task, Task], ...]] = None) -> None:
        super().__init__()
        self.__is_async = False
        self._node_to_dependencies: Dict[Task, Tuple[Task, ...]] = {}
        if tasks:
            for task in tasks:
                self._node_to_dependencies[task] = task.dependencies
                self.add(task, *task.dependencies)
                if not self.__is_async:
                    self.__is_async = task._is_async

    def __call__(
        self,
        pre_call: PreCallProtocol = pass_through,
        post_call: Optional[PostCallProtocol] = None,
        raise_immediately: bool = True,
        validate_graph: bool = False,
    ) -> Dict[str, _T]:
        if self.__is_async:
            return aexecute_graph(self, pre_call, post_call, raise_immediately, validate_graph)
        else:
            return execute_graph(self, pre_call, post_call, raise_immediately, validate_graph)

    __call__.__annotations__ = aexecute_graph.__doc__

    @property
    def unsorted_graph(self) -> TopologicalSorter:
        return self._node_to_dependencies

    def __add__(self, task: Task) -> Graph:
        if not self.__is_async:
            self.__is_async = task._is_async
        self.add(task, *task.dependencies)
        return self

    @property
    def is_async(self) -> bool:
        return self.__is_async

    def __iadd__(self, task: Task) -> None:
        self.add(task, *task.dependencies)

    def _get_return_count(self, func: Callable[..., Union[_T, Awaitable[_T]]]) -> Optional[int]:
        """Returns the number of expected return values based on the return type annotation.
        Returns None if the return type is a variable-length tuple (e.g., Tuple[int, ...])."""
        return_type = inspect.signature(func).return_annotation

        if return_type is inspect._empty:
            # If no return annotation, assume 1 output
            return 1

        if hasattr(return_type, "__origin__") and return_type.__origin__ is tuple:
            # Check if the tuple is variable-length (e.g., Tuple[int, ...])
            if len(return_type.__args__) == 2 and return_type.__args__[-1] is Ellipsis:
                return None  # Variable-length tuple (e.g., Tuple[int, ...])
            return len(return_type.__args__)  # Return the number of elements in the fixed tuple

        # Otherwise, assume a single output
        return 1

    def _get_return_annotation(self, coro: Callable[..., Awaitable[_T]]) -> int:
        # Get the number of return values from the coro
        return_type = inspect.signature(coro).return_annotation
        if return_type is inspect._empty:
            return 1  # Assume 1 output if return annotation is missing
        elif hasattr(return_type, "__args__"):
            return len(return_type.__args__)  # Return the number of output types
        return 1


@dataclass
class Task:
    func: Callable[..., Union[_T, Awaitable[_T]]]
    dependencies: Union[Tuple[Task, ...], Task] = ()
    input_names: Tuple[str, ...] = ()
    pre_call: Optional[
        Callable[
            [
                _T,
            ],
            Tuple[_T, ...],
        ]
    ] = field(default=None, kw_only=True)
    post_call: Optional[
        Callable[
            [
                _T,
            ],
            None,
        ]
    ] = field(default=None, kw_only=True)
    name: Optional[str] = field(default=None, kw_only=True)
    _graph: Optional[Union[Graph, weakref.ref[Graph]]] = None
    _is_async: Optional[bool] = None
    __id: Optional[str] = None

    def __call__(self, *args, **kwargs) -> Union[_T, Awaitable[_T]]:
        return self.func(*args, **kwargs)

    def add_dependency(self, task: Task) -> None:
        self.dependencies += (task,)
        if self.graph is not None and task.graph is not None and self.graph != task.graph:
            raise ValueError(f"Task {self.name} and Task {task.name} are in different graphs.")

    def __post_init__(self) -> None:
        self.__id = str(id(self))
        if self._is_async is None:
            self._is_async = asyncio.iscoroutinefunction(self.func)
        if self.name is None:
            self.name = self.__id
        if isinstance(self.dependencies, Task):
            self.dependencies = (self.dependencies,)
        self.dependencies = cast(Tuple[Task, ...], self.dependencies)
        for dependent_task in self.dependencies:
            if dependent_task.graph is not None:
                self._set_graph(dependent_task)

    def _set_graph(self, other: Task) -> None:
        if self._graph is None:
            if other.graph is not None:
                other.graph + self
                self._graph = weakref.ref(other.graph)
            else:
                self._graph = Graph((self, other))
                other._graph = weakref.ref(self._graph)
        else:
            if other.graph is not None and self.graph != other.graph:
                raise ValueError(f"Task {self.name} and Task {other.name} are in different graphs.")
            self.graph + other

    @property
    def id(self) -> str:
        return self.__id

    @property
    def graph(self) -> Optional[Graph]:
        return self._graph if self._graph is None or isinstance(self._graph, Graph) else self._graph()

    def __hash__(self) -> int:
        return int(self.__id) if self.name is None else hash(self.name)

    def __and__(self, other: Union[Tuple[Task], Task]) -> Tuple[Task, ...]:
        self._set_graph(other)
        return (self, other) if isinstance(other, Task) else (self, *other)

    def __rand__(self, other: Union[Tuple[Task], Task]) -> Tuple[Task, ...]:
        self._set_graph(other)
        return (other, self) if isinstance(other, Task) else (*other, self)
