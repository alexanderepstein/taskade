from __future__ import annotations

import asyncio
import weakref
from collections import UserDict
from concurrent import futures
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from functools import lru_cache, wraps
from importlib import import_module
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Protocol, Set, Tuple, Type, Union, cast
from uuid import uuid4

from graphlib import TopologicalSorter

from syncra._exceptions import FailedDependencyError
from syncra._types import _T, PoolExecutor


@lru_cache(maxsize=1)
def _get_graph() -> Dict[str, Graph]:
    """
    Get the graph dictionary

    Wrapping in a function to allow for lru_cache to be used
    without putting the cache on the global scope

    :return: the graph dictionary
    """
    return {}


def get_graph(graph_name: str) -> Optional[Graph]:
    """
    Retrieve a graph by name from the global graph dictionary.

    :param graph_name: The name of the graph to retrieve
    :return: The retrieved Graph object or None if not found
    """
    return _get_graph().get(graph_name)


def _get_args_from_dependencies(
    dependencies: Tuple[Task, ...], results: Dict[Task, Union[_T, Tuple[_T, ...]]]
) -> Tuple[List[_T], Dict[str, _T]]:
    """
    Get the arguments from the dependencies

    :param dependencies: the dependencies to get the arguments from
    :param results: the results of the tasks up until this point
    :return: the args and kwargs to use for the invocation of the task
    """
    args = []
    kwargs = {}
    for dependency in dependencies:
        if dependency.output_names:
            if isinstance(results[dependency], tuple):
                for name, result in zip(dependency.output_names, cast(Iterable[_T], results[dependency])):
                    kwargs[name] = result
            else:
                kwargs[dependency.output_names[0]] = cast(_T, results[dependency])
        else:
            if isinstance(results[dependency], tuple):
                args.extend(cast(Tuple[_T, ...], results[dependency]))
            else:
                args.append(cast(_T, results[dependency]))
    return args, kwargs


class PreCallProtocol(Protocol):
    """Protocol for the pre_call function"""

    def __call__(
        self, task: Task, *args: Tuple[_T, ...], **kwargs: Dict[str, _T]
    ) -> Optional[Dict[str, _T]]: ...  # pragma: no cover


def _execute_pre_call(pre_call: Optional[PreCallProtocol], task: Task, *args, **kwargs) -> Dict[str, _T]:
    """
    Executes the pre_call function and optionally updates the kwargs

    :param pre_call: optional pre_call function, defaults to None
    :param task: the task that will be executed after the pre_call
    :return: the kwargs to use for the invocation of the task
    """
    if pre_call:
        pre_call_kwargs = pre_call(task, *args, **kwargs)
        if pre_call_kwargs:
            kwargs.update(pre_call_kwargs)
    return kwargs


class PostCallProtocol(Protocol):
    """Protocol for the post_call function"""

    def __call__(self, result: _T, *args: Tuple[_T, ...]) -> None: ...  # pragma: no cover


def _execute_post_call(
    post_call: Optional[PostCallProtocol], task: Task, result: _T, results: Dict[Task, Union[Any, Tuple[Any, ...]]]
) -> None:
    """
    Executs the post_call function

    :param post_call: optional pre_call function, defaults to None
    :param task: the completed task
    :param result: result of the completed task
    :param results: results of execution up until this point
    """
    if post_call:
        result_args = []
        for dependent_task in task.dependencies:
            dependent_task_results = results[dependent_task]
            if isinstance(dependent_task_results, tuple):
                result_args.extend(dependent_task_results)
            else:
                result_args.append(dependent_task_results)
        post_call(result, *result_args)


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
        if self.name:
            _get_graph()[self.name] = self

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

    @classmethod
    def from_list(
        cls: Type[Graph],
        graph_name: str,
        tasks_list: List[Dict[str, str]],
        func_map: Optional[Dict[str, Callable[..., Union[_T, Awaitable[_T]]]]] = None,
    ) -> Graph:
        """
        Create a graph from a list of tasks

        :param cls: the class object of the graph
        :param graph_name: the name of the graph to create
        :param tasks_list: the list of tasks to add to the graph
        :param func_map: optional mapping of function names to their function, defaults to None
        :return: the graph object
        """
        graph = cls(name=graph_name)
        for task_dict in tasks_list:
            graph += Task.from_dict(task_dict, func_map)
        return graph

    @property
    def unsorted_graph(self: Graph) -> Dict[Task, Tuple[Task, ...]]:
        """
        The unsorted version of the graph

        :return: the dictionary of task to its dependencies
        """
        return self._node_to_dependencies

    @property
    def is_async(self: Graph) -> bool:
        """
        Indicates if the graph is async

        :return: true if any node in the graph is async, otherwise false
        """
        return self.__is_async

    def __add__(self: Graph, task: Task) -> Graph:
        """
        Adds a task to the graph

        :param task: the task to add to the graph
        :return: the graph itself
        """
        if not self.__is_async:
            self.__is_async = task.is_async
        task._graph = self if not self._node_to_dependencies else weakref.ref(self)
        self._node_to_dependencies[task] = task.dependencies
        self.add(task, *task.dependencies)
        return self

    def __iadd__(self: Graph, task: Task) -> Graph:
        """
        In place addition operator for adding a task to the graph

        :param task: the task to add to the graph
        :return: the graph itself
        """
        return self + task

    def execute(
        self: Graph,
        pre_call: Optional[PreCallProtocol] = None,
        post_call: Optional[PostCallProtocol] = None,
        raise_immediately: bool = True,
        tasks_semaphore: Optional[asyncio.Semaphore] = None,
        concurrency_pool: PoolExecutor = ThreadPoolExecutor,
        n_jobs: Optional[int] = None,
    ) -> Union[GraphResults, Awaitable[GraphResults]]:
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

    def __call__(
        self: Graph,
        pre_call: Optional[PreCallProtocol] = None,
        post_call: Optional[PostCallProtocol] = None,
        raise_immediately: bool = True,
        tasks_semaphore: Optional[asyncio.Semaphore] = None,
        concurrency_pool: PoolExecutor = ThreadPoolExecutor,
        n_jobs: Optional[int] = None,
    ) -> Union[GraphResults, Awaitable[GraphResults]]:
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
        return self.execute(pre_call, post_call, raise_immediately, tasks_semaphore, concurrency_pool, n_jobs)


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


class Task:
    """The task object, wrapping a function and its dependencies"""

    def __init__(
        self,
        func: Callable[..., Union[Any, Awaitable[Any]]],
        dependencies: Optional[Union[Task, Tuple[Task, ...]]] = None,
        output_names: Optional[Tuple[str, ...]] = None,
        *,
        pre_call: Optional[PreCallProtocol] = None,
        post_call: Optional[PostCallProtocol] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        _graph: Optional[Union[Graph, weakref.ref[Graph]]] = None,
    ):
        """
        Initialize a Task object.

        :param func: The function that the task is wrapping
        :param dependencies: The dependencies of the task, defaults to None
        :param output_names: The names of the outputs of the task, defaults to None
        :param pre_call: The function to call with the results of the dependencies for this task, defaults to None
        :param post_call: The function to call with the output of this task, defaults to None
        :param init_kwargs: The optional initialization arguments for the task if not provided all input arguments will
        be provided by the dependency results, defaults to None
        :param name: The optional name for this task, defaults to None
        :param _graph: The optional graph for this task, defaults to None
        """
        self.func = func
        self.output_names: Tuple[str, ...] = output_names if output_names is not None else ()
        self.pre_call = pre_call
        self.post_call = post_call
        self.init_kwargs = init_kwargs
        self.name = name if name is not None else str(uuid4())
        self._graph = _graph

        if dependencies is None:
            self.dependencies = ()
        elif isinstance(self.dependencies, Task):
            self.dependencies = (self.dependencies,)
        else:
            self.dependencies = cast(Tuple[Task, ...], dependencies)

        if len(self.dependencies) > 0:
            for dependent_task in self.dependencies:
                self._set_graph(dependent_task)
        if self._graph is not None:
            # TODO: There is a special case where the task is already part of the graph,
            # but we are still adding it to the graph, handle this better to avoid unnecessary checks
            cast(Graph, self.graph) + self

    def __call__(self, *args, **kwargs) -> Union[_T, Awaitable[_T]]:
        """
        Executes the function within the task

        :return: the results of the execution, if the function is async this will return the awaitable
        """
        return self.func(*args, **kwargs)

    @classmethod
    def from_dict(
        cls: Type[Task],
        task_dict: Dict[str, Any],
        func_map: Optional[Dict[str, Callable[..., Union[_T, Awaitable[_T]]]]] = None,
    ) -> Task:
        """
        Create a task from a dictionary

        :param task_dict: the dictionary of the task
        :param func_map: the mapping of the function names to the functions
        :return: the task object
        """
        func = task_dict.pop("func")
        if func_map and func in func_map:
            task = cls(func_map[func], **task_dict)
        else:
            # Attempt to import the function dynamically
            module_name, func_name = func.rsplit(".", 1)
            module = import_module(module_name)
            # Check type of func to ensure it is a callable
            func = getattr(module, func_name)
            if not isinstance(func, Callable):
                raise ValueError(f"Function {func_name} in module {module_name} is not callable.")
            func = cast(Callable[..., Union[_T, Awaitable[_T]]], func)
            task = cls(func, **task_dict)
        task_dict["func"] = func
        return task

    def _set_graph(self: Task, other: Task) -> None:
        """
        Ensures that this task and an other task are tied to the same graph, whichever task is tied to an existing graph then the other will
        be provided a weak reference to the graph through the task tied to it. If neither task are tied to a graph then a graph will be created
        and this task will contain a strong reference while the other will contain the weak reference

        :param other: the other task tied to this task
        :raises ValueError: if both tasks have a graph and they are not the same graph
        """
        if self._graph is None:
            graph = other.graph
            if graph is not None:
                self._graph = weakref.ref(graph)
                graph + self
            else:
                self._graph = Graph((self, other))
                other._graph = weakref.ref(self._graph)
        else:
            if other.graph is not None and self.graph != other.graph:
                raise ValueError(f"Task {self.name} and Task {other.name} are in different graphs.")
            graph = cast(Graph, self.graph)
            graph + other

    @property
    def is_async(self: Task) -> bool:
        """
        Indicates if the task is async

        :return: true if the task is async, false otherwise
        """
        return asyncio.iscoroutinefunction(self.func)

    @property
    def id(self: Task) -> str:
        """
        The id for the task

        :return: a unique identifier for the task
        """
        return str(id(self))

    @property
    def graph(self: Task) -> Optional[Graph]:
        """
        The underlying graph for the task

        :return: the graph for the task, this will be None if this task is not part of a graph
        """
        return self._graph if self._graph is None or isinstance(self._graph, Graph) else self._graph()

    def __hash__(self: Task) -> int:
        """
        Hash function for the task, this lets it be stored in hashable types (sets, as dict keys etc...)

        :return: the hash for the task, if a name is provided this is a hash of the name otherwise its a hash of the id
        """
        return id(self) if self.name is None else hash(self.name)

    def __and__(self: Task, other: Task) -> Tuple[Task, ...]:
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

    def __rand__(self: Task, other: Task) -> Tuple[Task, ...]:
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
    concurrency_pool: Union[ThreadPoolExecutor, ProcessPoolExecutor],
    pre_call: Optional[PreCallProtocol] = None,
    post_call: Optional[PostCallProtocol] = None,
    raise_immediately: bool = True,
) -> GraphResults:
    """
    Concurrently execute the graph

    :param graph: graph to execute
    :param concurrency_pool: pool for executing a graph concurrently, this pool will be used for executing the individual tasks
    :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to None
    :param post_call: default post_call function to use for execution, task level post_call functions take precendence over this, defaults to None
    :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
    if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True
    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
    :return: the result of the graph execution
    """
    graph.prepare()
    results: Dict[Task, Union[Any, Tuple[Any, ...]]] = {}
    task_futures: Set[Future[Any]] = set()
    task_future_map: Dict[Future, Task] = {}
    while graph.is_active():
        available_tasks = graph.get_ready()
        eligible_tasks = _get_eligble_tasks(available_tasks, results) if not raise_immediately else available_tasks
        for available_task in eligible_tasks:
            available_task = cast(Task, available_task)
            call_args, call_kwargs = _get_args_from_dependencies(available_task.dependencies, results)
            task_pre_call = available_task.pre_call if available_task.pre_call else pre_call
            call_kwargs = _execute_pre_call(task_pre_call, available_task, *call_args, **call_kwargs)
            if available_task.init_kwargs:
                call_kwargs.update(available_task.init_kwargs)
            # TODO: Look for a way around submit as we lose the chunksize behavior offered by pool.map
            task_future = concurrency_pool.submit(available_task.func, *call_args, **call_kwargs)
            task_futures.add(task_future)
            task_future_map[task_future] = available_task

        task_future = next(futures.as_completed(task_futures))
        task = task_future_map[task_future]
        if exception := task_future.exception():
            if raise_immediately:
                # Cancel tasks before raising the exception,
                # this may be caught on the outside and kept within the context of the pool
                for task_future in task_futures:
                    task_future.cancel()
                raise exception
            else:
                result = exception
        else:
            result = task_future.result()
        task_futures.remove(task_future)
        _execute_post_call(post_call, task, result, results)
        graph.done(task)
        results[task] = result
    return GraphResults({hash(task): result for task, result in results.items()})


def _sync_execute_graph(
    graph: Graph,
    pre_call: Optional[PreCallProtocol] = None,
    post_call: Optional[PostCallProtocol] = None,
    raise_immediately: bool = True,
) -> GraphResults:
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
    results: Dict[Task, Union[Any, Tuple[Any, ...]]] = {}
    while graph.is_active():
        available_tasks = graph.get_ready()
        eligible_tasks = _get_eligble_tasks(available_tasks, results) if not raise_immediately else available_tasks
        for available_task in eligible_tasks:
            available_task = cast(Task, available_task)
            call_args, call_kwargs = _get_args_from_dependencies(available_task.dependencies, results)
            task_pre_call = available_task.pre_call if available_task.pre_call else pre_call
            call_kwargs = _execute_pre_call(task_pre_call, available_task, *call_args, **call_kwargs)
            if available_task.init_kwargs:
                call_kwargs.update(available_task.init_kwargs)
            try:
                result = available_task.func(*call_args, **call_kwargs)
            except Exception as e:
                result = e
                if raise_immediately:
                    raise result
            _execute_post_call(post_call, available_task, result, results)
            graph.done(available_task)
            results[available_task] = result
    return GraphResults({hash(task): result for task, result in results.items()})


def execute_graph(
    graph: Graph,
    pre_call: Optional[PreCallProtocol] = None,
    post_call: Optional[PostCallProtocol] = None,
    raise_immediately: bool = True,
    concurrency_pool: Union[
        ThreadPoolExecutor, ProcessPoolExecutor, Type[ThreadPoolExecutor], Type[ProcessPoolExecutor]
    ] = ThreadPoolExecutor,
    n_jobs: Optional[int] = None,
) -> GraphResults:
    """
    Execute the graph with optional concurrency

    :param graph: graph to execute
    :param pre_call: default pre_call function to use for execution, task level pre_call functions take precedence over this, defaults to pass_through
    :param post_call: default post_call function to use for execution, task level post_call functions take precedence over this, defaults to None
    :param raise_immediately: indicates if any exception raised by a node in the graph should be raised immediately,
    if False the graph will continue to execute as long as there are nodes that are not dependent on a failed task, defaults to True
    :param concurrency_pool: pool for executing a graph concurrently, this pool will be used for executing the individual tasks,
    can either provide an instance of a thread or process pool or specify the type of pool and set the n_jobs parameter, defaults to ThreadPoolExecutor type
    :param n_jobs: optional number of jobs for executing a graph concurrently, defaults to None
    :raises FailedDependencyError: if all available nodes are waiting on a dependency that has failed and raise_immmediately is False
    :return: the result of the graph execution
    """
    if isinstance(concurrency_pool, (ThreadPoolExecutor, ProcessPoolExecutor)):
        result = _concurrent_execute_graph(graph, concurrency_pool, pre_call, post_call, raise_immediately)
    elif n_jobs and concurrency_pool in (ThreadPoolExecutor, ProcessPoolExecutor):
        with concurrency_pool(max_workers=n_jobs) as pool:
            result = _concurrent_execute_graph(graph, pool, pre_call, post_call, raise_immediately)
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


async def _aconsumer(result_queue: asyncio.Queue, raise_immediately: bool) -> Tuple[Task, Union[Exception, Any]]:
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
    pre_call: Optional[PreCallProtocol] = None,
    post_call: Optional[PostCallProtocol] = None,
    raise_immediately: bool = True,
    tasks_semaphore: Optional[asyncio.Semaphore] = None,
) -> GraphResults:
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
    results: Dict[Task, Union[Any, Tuple[Any, ...]]] = {}
    while graph.is_active():
        available_tasks = graph.get_ready()
        eligible_tasks = _get_eligble_tasks(available_tasks, results) if not raise_immediately else available_tasks
        for available_task in eligible_tasks:
            available_task = cast(Task, available_task)
            if not available_task.is_async:

                @wraps(available_task.func)
                async def async_wrapper(*args, **kwargs) -> Any:
                    return available_task.func(*args, **kwargs)

                executing_func = async_wrapper
            else:
                executing_func = cast(Callable[..., Awaitable[Any]], available_task.func)
            call_args, call_kwargs = _get_args_from_dependencies(available_task.dependencies, results)
            task_pre_call = available_task.pre_call if available_task.pre_call else pre_call
            call_kwargs = _execute_pre_call(task_pre_call, available_task, *call_args, **call_kwargs)
            if available_task.init_kwargs:
                call_kwargs.update(available_task.init_kwargs)
            # TODO: Look into using asyncio.wait instead of the queue, assumption is possible speed improvement?
            asyncio.create_task(
                _aproducer(available_task, executing_func(*call_args, **call_kwargs), result_queue, tasks_semaphore)
            )
        task, result = await _aconsumer(result_queue, raise_immediately)
        _execute_post_call(post_call, task, result, results)
        graph.done(task)
        results[task] = result
    return GraphResults({hash(task): result for task, result in results.items()})
