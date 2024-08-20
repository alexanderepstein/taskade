from __future__ import annotations

import asyncio
import weakref
from collections import UserDict
from concurrent import futures
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import wraps
from graphlib import TopologicalSorter
from typing import Awaitable, Callable, Dict, Optional, Protocol, Self, Set, Tuple, Type, TypeVar, Union, cast

from tanto._exceptions import FailedDependencyError

_T = TypeVar("_T")
"""Type variable for the return type of a task"""


def pass_through(*args: Tuple[_T, ...]) -> Tuple[_T, ...]:
    """
    A pass through function

    :return: the arguments provided to the graph
    """
    return args


def eat(*args: Tuple[_T, ...]) -> Tuple:
    """
    Eats the arguments of its invocation

    :return: an empty tuple
    """
    return ()


def _get_eligble_tasks(available_tasks: Tuple[Task, ...], results: Dict[Task, _T]) -> Tuple[Task, ...]:
    """
    Get the eligible tasks for execution

    :param available_tasks: the tasks that are available for execution
    :param results: the results of the tasks
    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed
    :return: the tasks that are eligible for execution
    """
    eligible_tasks = tuple(
        available_task
        for available_task in available_tasks
        if not any(isinstance(results[dependent_task], Exception) for dependent_task in available_task.dependencies)
    )
    if not eligible_tasks:
        raise FailedDependencyError("All available nodes are waiting on a dependency that has failed.", results)
    return eligible_tasks


class Graph(TopologicalSorter):
    """The graph object, tying together multiple tasks together for execution of a DAG"""

    def __init__(self, tasks: Optional[Tuple[Task, ...]] = None, name: Optional[str] = None) -> None:
        """
        Initializer for the graph

        :param tasks: tuple of tasks tied to this graph, defaults to None
        :param name: the identifier for the graph, defaults to None
        """
        super().__init__()
        self.name = name
        self.__is_async = False
        self._node_to_dependencies: Dict[Task, Tuple[Task, ...]] = {}
        if tasks:
            for task in tasks:
                self._node_to_dependencies[task] = task.dependencies
                self.add(task, *task.dependencies)
                if not self.__is_async:
                    self.__is_async = task.is_async

    def __getitem__(self, key: str) -> Task:
        """
        Gets the task by name in the graph

        :param key: the name of the task to retrieve
        :raises KeyError: raised if the task is not found in the graph
        :return: the task object
        """
        for task in self._node_to_dependencies:
            if task.name == key:
                return task
        raise KeyError(f"Task {key} not found in graph.")

    @property
    def unsorted_graph(self: Self) -> Dict[Task, Tuple[Task, ...]]:
        """
        The unsorted version of the graph

        :return: the dictionary of task to its dependencies
        """
        return self._node_to_dependencies

    @property
    def is_async(self: Self) -> bool:
        """
        Indicates if the graph is async

        :return: true if any node in the graph is async, otherwise false
        """
        return self.__is_async

    def __add__(self: Self, task: Task) -> Graph:
        """
        Adds a task to the graph

        :param task: the task to add to the graph
        :return: the graph itself
        """
        if not self.__is_async:
            self.__is_async = task.is_async
        self._node_to_dependencies[task] = task.dependencies
        self.add(task, *task.dependencies)
        return self

    def __iadd__(self: Self, task: Task) -> Graph:
        """
        In place addition operator for adding a task to the graph

        :param task: the task to add to the graph
        :return: the graph itself
        """
        return self + task

    def __call__(
        self: Self,
        pre_call: PreCallProtocol = pass_through,
        post_call: Optional[PostCallProtocol] = None,
        raise_immediately: bool = True,
        tasks_semaphore: Optional[asyncio.Semaphore] = None,
        concurrency_pool: Union[
            Union[Union[ThreadPoolExecutor, ProcessPoolExecutor], Type[ThreadPoolExecutor]], Type[ProcessPoolExecutor]
        ] = ThreadPoolExecutor,
        n_jobs: Optional[int] = None,
    ) -> Union[Dict[str, _T], Awaitable[Dict[str, _T]]]:
        """
            Executes the graph
            :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to pass_through
            :param post_call: default post_call function to use for execution, task level post_call functions take precendence over this, defaults to None
            :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
            if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True
            :param tasks_semaphore: only applies to async execution, the semaphore to control the number of tasks running concurrently, defaults to None
            :param concurrency_pool: only applies to non-async execution, pool for executing a graph concurrently, this pool will be used for executing the individual tasks,
        can either provide an instance of a thread or process pool or specify the type of pool and set the n_jobs parameter, defaults to ThredPoolExecutor type
        :param n_jobs: only applies to non-async execution, optional number of jobs for executing a graph concurrently, defaults to None
            :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
            :return: if the graph is async this will return the awaitable, otherwise this will return the result of the graph execution
        """
        if self.is_async:
            return aexecute_graph(self, pre_call, post_call, raise_immediately, tasks_semaphore)
        else:
            return execute_graph(self, pre_call, post_call, raise_immediately, concurrency_pool, n_jobs)


class PreCallProtocol(Protocol):
    """Protocol for the pre_call function"""

    def __call__(self, *args: Tuple[_T, ...]) -> Tuple[_T, ...]: ...


class PostCallProtocol(Protocol):
    """Protocol for the post_call function"""

    def __call__(self, *args: Tuple[_T, ...]) -> None: ...


class GraphResults(UserDict):
    """Results of a graph execution"""

    def __getitem__(self, key: Task | int | str) -> _T:
        """
        Get the result of a task by its name or hash.
        This allows for retrieval of task results by either the name or the task object itself

        :param key: the task, task name name or hash
        :return: the result of the task
        """
        if isinstance(key, Task):
            key = hash(key)
        return super().__getitem__(key)


@dataclass
class Task:
    """The task object, wrapping a function and its dependencies"""

    func: Callable[..., Union[_T, Awaitable[_T]]]
    """The function that that task is wrapping"""

    dependencies: Union[Tuple[Task, ...], Task] = ()
    """The dependencies of the task"""

    input_names: Tuple[str, ...] = ()
    pre_call: Optional[
        Callable[
            [
                _T,
            ],
            Tuple[_T, ...],
        ]
    ] = field(default=None, kw_only=True)
    """The function to call with the results of the dependencies for this task, the return value of this function will be the input to this task execuion"""

    post_call: Optional[
        Callable[
            [
                _T,
            ],
            None,
        ]
    ] = field(default=None, kw_only=True)
    """The function to call with the output of this task, the result of this function will be the stored result for this task"""

    name: Optional[str] = field(default=None, kw_only=True)
    """The optional name for this task"""

    _graph: Optional[Union[Graph, weakref.ref[Graph]]] = None
    """The optional graph where this task is part of the execution"""

    __id: Optional[str] = None
    """The id of the task"""

    def __call__(self, *args, **kwargs) -> Union[Union[_T, Tuple[_T, ...]], Awaitable[Union[_T, Tuple[_T, ...]]]]:
        """
        Executes the function within the task

        :return: the results of the execution, if the function is async this will return the awaitable
        """
        return self.func(*args, **kwargs)

    def __post_init__(self) -> None:
        """
        Post initialization for the task, this performs the necessary manipulations on the internal state
        """
        self.__id = str(id(self))
        if self.name is None:
            self.name = self.__id
        if isinstance(self.dependencies, Task):
            self.dependencies = (self.dependencies,)
        self.dependencies = cast(Tuple[Task, ...], self.dependencies)
        for dependent_task in self.dependencies:
            self._set_graph(dependent_task)

    def _set_graph(self, other: Task) -> None:
        """
        Ensures that this task and an other task are tied to the same graph, whichever task is tied to an existing graph then the other will
        be provided a weak reference to the graph through the task tied to it. If neither task are tied to a graph then a graph will be created
        and this task will contain a strong reference while the other will contain the weak reference

        :param other: the other task tied to this task
        :raises ValueError: if both tasks have a graph and they are not the same graph
        """
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
    def is_async(self: Self) -> bool:
        """
        Indicates if the task is async

        :return: true if the task is async, false otherwise
        """
        return asyncio.iscoroutinefunction(self.func)

    @property
    def id(self: Self) -> str:
        """
        The id for the task

        :return: a unique identifier for the task
        """
        return self.__id

    @property
    def graph(self: Self) -> Optional[Graph]:
        """
        The underlying graph for the task

        :return: the grah for the task, this will be None if this task is not part of a graph
        """
        return self._graph if self._graph is None or isinstance(self._graph, Graph) else self._graph()

    def __hash__(self: Self) -> int:
        """
        Hash function for the task, this lets it be stored in hashable types (sets, as dict keys etc...)

        :return: the hash for the task, if a name is provided this is a hash of the name otherwise its a hash of the id
        """
        return int(self.__id) if self.name is None else hash(self.name)

    def __and__(self: Self, other: Task) -> Tuple[Task, ...]:
        """
        Binary and operator for the task
        This allows for the syntax task_a & task_b when defining dependencies for another graph
        Implicitly these tasks will be made part of the same graph

        :param other: the task being `anded` with this task
        :raises ValueError: if both tasks have an assigned graph and they are not the same graph
        :return: a tuple of this task and the one being added
        """
        self._set_graph(other)
        return (self, other)

    def __rand__(self: Self, other: Task) -> Tuple[Task, ...]:
        """
        Binary and operator for the task
        This allows for the syntax task_a & task_b when defining dependencies for another graph
        Implicitly these tasks will be made part of the same graph

        :param other: the task being `anded` with this task
        :raises ValueError: if both tasks have an assigned graph and they are not the same graph
        :return: a tuple of this task and the one being added
        """
        self._set_graph(other)
        return (other, self)


def _concurrent_execute_graph(
    graph: Graph,
    pre_call: Callable[
        [
            _T,
        ],
        Tuple[_T],
    ] = pass_through,
    post_call: Optional[Callable[[_T], None]] = None,
    raise_immediately: bool = True,
    concurrency_pool: Union[ThreadPoolExecutor, ProcessPoolExecutor] = None,
) -> Dict[str, _T]:
    """
    Concurrently execute the graph

    :param graph: graph to execute
    :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to pass_through
    :param post_call: default post_call function to use for execution, task level post_call functions take precendence over this, defaults to None
    :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
    if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True
    :param concurrency_pool: pool for executing a graph concurrently, this pool will be used for executing the individual tasks
    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
    :return: the result of the graph execution
    """
    graph.prepare()
    results: Dict[Task, _T] = {}
    task_futures: Set[Tuple[Future, Task]] = set()
    task_future_map: Dict[Future, Task] = {}
    while graph.is_active():
        available_tasks = graph.get_ready()
        eligible_tasks = _get_eligble_tasks(available_tasks, results) if not raise_immediately else available_tasks
        for available_task in eligible_tasks:
            available_task = cast(Task, available_task)
            call_args = getattr(available_task, pre_call.__name__, pre_call)(
                *(results[dependent_task] for dependent_task in available_task.dependencies)
            )
            if len(available_task.input_names):
                call_args = {name: arg for name, arg in zip(available_task.input_names, call_args)}
            # TODO: Look for a way around submit as we lose the chunksize behavior offered by pool.map
            task_future = concurrency_pool.submit(available_task.func, *call_args)
            task_futures.add(task_future)
            task_future_map[task_future] = available_task

        task_future = next(futures.as_completed(task_futures))
        task = task_future_map[task_future]
        if task_future.exception():
            if raise_immediately:
                # Cancel tasks before raising the exception,
                # this may be caught on the outside and kept within the context of the pool
                for task_future in task_futures:
                    task_future.cancel()
                raise task_future.exception()
            else:
                result = task_future.exception()
        else:
            result = task_future.result()
        task_futures.remove(task_future)
        if post_call:
            post_call(
                result,
                *(result[dependent_task] for dependent_task in task.dependencies),
            )
        graph.done(task)
        results[task] = result
    return GraphResults({hash(task): result for task, result in results.items()})


def _sync_execute_graph(
    graph: Graph,
    pre_call: Callable[
        [
            _T,
        ],
        Tuple[_T],
    ] = pass_through,
    post_call: Optional[Callable[[_T], None]] = None,
    raise_immediately: bool = True,
) -> Dict[str, _T]:
    """
    Execute the graph

    :param graph: graph to execute
    :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to pass_through
    :param post_call: default post_call function to use for execution, task level post_call functions take precendence over this, defaults to None
    :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
    if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True

    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
    :return: the result of the graph execution
    """
    graph.prepare()
    results: Dict[Task, _T] = {}
    while graph.is_active():
        available_tasks = graph.get_ready()
        eligible_tasks = _get_eligble_tasks(available_tasks, results) if not raise_immediately else available_tasks
        for available_task in eligible_tasks:
            available_task = cast(Task, available_task)
            call_args = getattr(available_task, pre_call.__name__, pre_call)(
                *(results[dependent_task] for dependent_task in available_task.dependencies)
            )
            if len(available_task.input_names):
                call_args = {name: arg for name, arg in zip(available_task.input_names, call_args)}
            try:
                result = available_task.func(*call_args)
            except Exception as e:
                result = e
                if raise_immediately:
                    raise result
            if post_call:
                post_call(
                    result,
                    *(result[dependent_task] for dependent_task in available_task.dependencies),
                )
            graph.done(available_task)
            results[available_task] = result
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
    concurrency_pool: Union[
        Union[Union[ThreadPoolExecutor, ProcessPoolExecutor], Type[ThreadPoolExecutor]], Type[ProcessPoolExecutor]
    ] = ThreadPoolExecutor,
    n_jobs: Optional[int] = None,
) -> Dict[str, _T]:
    """
    Execute the graph with optional concurrency

    :param graph: graph to execute
    :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to pass_through
    :param post_call: default post_call function to use for execution, task level post_call functions take precendence over this, defaults to None
    :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
    if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True
    :param concurrency_pool: pool for executing a graph concurrently, this pool will be used for executing the individual tasks,
    can either provide an instance of a thread or process pool or specify the type of pool and set the n_jobs parameter, defaults to ThredPoolExecutor type
    :param n_jobs: optional number of jobs for executing a graph concurrently, defaults to None
    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
    :return: the result of the graph execution
    """
    if isinstance(concurrency_pool, ThreadPoolExecutor) or isinstance(concurrency_pool, ProcessPoolExecutor):
        concurrency_pool = cast(Union[ThreadPoolExecutor, ProcessPoolExecutor], concurrency_pool)
        result = _concurrent_execute_graph(graph, pre_call, post_call, raise_immediately, concurrency_pool)
    elif n_jobs:
        concurrency_pool = cast(Union[Type[ThreadPoolExecutor], Type[ProcessPoolExecutor]], concurrency_pool)
        with concurrency_pool(max_workers=n_jobs) as pool:
            result = _concurrent_execute_graph(graph, pre_call, post_call, raise_immediately, pool)
    else:
        result = _sync_execute_graph(graph, pre_call, post_call, raise_immediately)
    return result


async def _aproducer(
    task: Task, coro: Awaitable[_T], result_queue: asyncio.Queue, tasks_semaphore: Optional[asyncio.Semaphore]
) -> None:
    """
    This is the producer for async function execution
    Ensuring, non-blocking invocation of nodes in the graph

    :param task: instance of the task being executed
    :param coro: the coroutine that is being executed
    :param result_queue: the result of the coroutine is put into this queue
    :param tasks_semaphore: the semaphore to control the number of tasks running concurrently, defaults to None
    """
    if tasks_semaphore:
        async with tasks_semaphore:
            try:
                result = await coro
            except Exception as e:
                result = e
    else:
        try:
            result = await coro
        except Exception as e:
            result = e
    await result_queue.put((task, result))


async def _aconsumer(result_queue: asyncio.Queue, raise_immediately: bool) -> Tuple[Task, _T]:
    """
    Consumer for async function execution
    This call will wait until a result is available from the result queue

    :param result_queue: the queue to retrieve the results from
    :param raise_immediately: indicates if the result of the function execution should be raised immediately
    :raises Exception: if raise_immediately is set to True and the retrieved task returns an exception
    :return: the task instance and its corresponding result
    """
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
    tasks_semaphore: Optional[asyncio.Semaphore] = None,
) -> Dict[str, _T]:
    """
    Asynchronously execute the graph

    :param graph: graph to execute
    :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to pass_through
    :param post_call: default post_call function to use for execution, task level post_call functions take precendence over this, defaults to None
    :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
    if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True
    :param tasks_semaphore: the semaphore to control the number of tasks running concurrently, defaults to None
    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
    :return: the result of the graph execution
    """
    graph.prepare()
    result_queue = asyncio.Queue()
    results: Dict[Task, _T] = {}
    while graph.is_active():
        available_tasks = graph.get_ready()
        eligible_tasks = _get_eligble_tasks(available_tasks, results) if not raise_immediately else available_tasks
        for available_task in eligible_tasks:
            available_task = cast(Task, available_task)
            if not available_task.is_async:

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
            # TODO: Look into using asyncio.wait instead of the queue, assumption is possible speed improvement?
            asyncio.create_task(_aproducer(available_task, executing_func(*call_args), result_queue, tasks_semaphore))
        task, result = await _aconsumer(result_queue, raise_immediately)
        if post_call:
            post_call(
                result,
                *(result[dependent_task] for dependent_task in task.dependencies),
            )
        graph.done(task)
        results[task] = result
    return GraphResults({hash(task): result for task, result in results.items()})
