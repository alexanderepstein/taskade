import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from time import sleep
from typing import TypeVar, cast

import pytest

from syncra import Task
from syncra._exceptions import FailedDependencyError
from syncra._execution import Graph, GraphResults

_T = TypeVar("_T")


class ExampleException(Exception):
    pass


async def asleep(seconds, *args, **kwargs) -> str:
    await asyncio.sleep(seconds)
    return f"{seconds=}"


def sync_sleep(seconds, *args, **kwargs) -> str:
    sleep(seconds)
    return f"{seconds=}"


def sync_sleep_output_seconds(seconds, *args, **kwargs):
    sleep(seconds)
    return seconds


def kwargs_sleep(*args, seconds=0, **kwargs):
    sleep(seconds)
    return f"{seconds=}"


def throw_exception():
    raise ExampleException("This is an exception")


def example_pre_call(task: Task, *args, **kwargs):
    return {"new_key": "new_value"}


def example_post_call(result: _T, *args):
    pass


def test_graph_single_execution():
    g = Graph(name="test")
    a = Task(partial(sync_sleep, 0.5), post_call=example_post_call, _graph=g)
    graph = cast(Graph, a.graph)
    results = graph.execute()
    results = cast(GraphResults, results)
    assert results[a] == "seconds=0.5"


@pytest.mark.asyncio
async def test_graph_aexecution():
    a = Task(partial(asleep, 1))
    b = Task(partial(asleep, 0.5))
    c = Task(partial(asleep, 1), a & b)
    d = Task(partial(asleep, 0.5), b)
    graph = cast(Graph, a.graph)
    results = await graph.execute()
    results = cast(GraphResults, results)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


@pytest.mark.asyncio
async def test_graph_aexecution_added():
    graph = Graph()
    a = Task(partial(asleep, 1))
    b = Task(partial(asleep, 0.5))
    graph += a & b  # Need to add these task to the graph and c & d will be implicitly added through the dependencies
    c = Task(partial(asleep, 1), a & b)
    d = Task(partial(asleep, 0.5), b)
    results = await graph.execute()
    results = cast(GraphResults, results)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


def test_graph_sync_execution():
    a = Task(partial(sync_sleep, 1))
    b = Task(partial(sync_sleep, 0.5))
    c = Task(partial(sync_sleep, 1), a & b)
    d = Task(partial(sync_sleep, 0.5), b)
    graph = cast(Graph, a.graph)
    results = graph.execute()
    results = cast(GraphResults, results)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


def test_graph_sync_execution_pre_post_call():
    a = Task(partial(sync_sleep, 1))
    b = Task(partial(sync_sleep_output_seconds, 0.5), output_names=("seconds",))
    c = Task(kwargs_sleep, a & b)
    d = Task(kwargs_sleep, b)
    graph = cast(Graph, a.graph)
    results = graph.execute(pre_call=example_pre_call, post_call=example_post_call)
    results = cast(GraphResults, results)
    assert results[a] == "seconds=1"
    assert results[b] == 0.5
    assert results[c] == "seconds=0.5"
    assert results[d] == "seconds=0.5"


def test_graph_concurrent_execution_n_jobs():
    a = Task(partial(sync_sleep, 1))
    b = Task(partial(sync_sleep, 0.5))
    c = Task(partial(sync_sleep, 1), a & b)
    d = Task(partial(sync_sleep, 0.5), b)
    graph = cast(Graph, a.graph)
    results = graph.execute(n_jobs=2)
    results = cast(GraphResults, results)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


def test_graph_concurrent_execution_pool():
    a = Task(partial(sync_sleep, 1))
    b = Task(partial(sync_sleep, 0.5))
    c = Task(partial(sync_sleep, 1), a & b)
    d = Task(partial(sync_sleep, 0.5), b)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = a.graph.execute(concurrency_pool=pool)
    results = cast(GraphResults, results)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


@pytest.mark.asyncio
async def test_graph_aexecution_with_failed_dependency():
    failed_dependency = Task(throw_exception)
    a = Task(partial(asleep, 1), dependencies=(failed_dependency,))
    graph = cast(Graph, a.graph)
    try:
        await graph.execute(raise_immediately=False)
    except FailedDependencyError:
        return
    assert False, "FailedDependencyError not raised"


@pytest.mark.asyncio
async def test_graph_aexecution_with_failed_task_immediately():
    failed_dependency = Task(throw_exception)
    a = Task(partial(asleep, 1), dependencies=(failed_dependency,))
    graph = cast(Graph, a.graph)
    try:
        await graph.execute(raise_immediately=True)
    except ExampleException:
        return
    assert False, "TestException not raised"


def test_graph_sync_execution_with_failed_dependency():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    graph = cast(Graph, a.graph)
    try:
        graph.execute(raise_immediately=False)
    except FailedDependencyError:
        return
    assert False, "FailedDependencyError not raised"


def test_graph_sync_execution_with_failed_task_immediately():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    graph = cast(Graph, a.graph)
    try:
        graph.execute(raise_immediately=True)
    except ExampleException:
        return
    assert False, "TestException not raised"


def test_graph_concurrent_execution_with_failed_dependency():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    graph = cast(Graph, a.graph)
    try:
        graph.execute(raise_immediately=False, n_jobs=2)
    except FailedDependencyError:
        return
    assert False, "FailedDependencyError not raised"


def test_graph_concurrent_execution_with_failed_task_immediately():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    graph = cast(Graph, a.graph)
    try:
        graph.execute(raise_immediately=True, n_jobs=2)
    except ExampleException:
        return
    assert False, "TestException not raised"
