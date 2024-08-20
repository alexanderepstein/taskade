import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from time import sleep

import pytest

from tanto import Task, eat
from tanto._exceptions import FailedDependencyError


class TestException(Exception):
    pass


async def asleep(seconds) -> str:
    await asyncio.sleep(seconds)
    return f"{seconds=}"


def sync_sleep(seconds) -> str:
    sleep(seconds)
    return f"{seconds=}"


def throw_exception():
    raise TestException("This is an exception")


@pytest.mark.asyncio
async def test_graph_aexecution():
    a = Task(partial(asleep, 1))
    b = Task(partial(asleep, 0.5))
    c = Task(partial(asleep, 1), a & b)
    d = Task(partial(asleep, 0.5), b)
    results = await a.graph(pre_call=eat)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


def test_graph_sync_execution():
    a = Task(partial(sync_sleep, 1))
    b = Task(partial(sync_sleep, 0.5))
    c = Task(partial(sync_sleep, 1), a & b)
    d = Task(partial(sync_sleep, 0.5), b)
    results = a.graph(pre_call=eat)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


def test_graph_concurrent_execution_n_jobs():
    a = Task(partial(sync_sleep, 1))
    b = Task(partial(sync_sleep, 0.5))
    c = Task(partial(sync_sleep, 1), a & b)
    d = Task(partial(sync_sleep, 0.5), b)
    results = a.graph(pre_call=eat, n_jobs=2)
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
        results = a.graph(pre_call=eat, concurrency_pool=pool)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"


@pytest.mark.asyncio
async def test_graph_aexecution_with_failed_dependency():
    failed_dependency = Task(throw_exception)
    a = Task(partial(asleep, 1), dependencies=(failed_dependency,))
    try:
        await a.graph(pre_call=eat, raise_immediately=False)
    except FailedDependencyError:
        return
    assert False, "FailedDependencyError not raised"


@pytest.mark.asyncio
async def test_graph_aexecution_with_failed_task_immediately():
    failed_dependency = Task(throw_exception)
    a = Task(partial(asleep, 1), dependencies=(failed_dependency,))
    try:
        await a.graph(pre_call=eat, raise_immediately=True)
    except TestException:
        return
    assert False, "TestException not raised"


def test_graph_sync_execution_with_failed_dependency():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    try:
        a.graph(pre_call=eat, raise_immediately=False)
    except FailedDependencyError:
        return
    assert False, "FailedDependencyError not raised"


def test_graph_sync_execution_with_failed_task_immediately():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    try:
        a.graph(pre_call=eat, raise_immediately=True)
    except TestException:
        return
    assert False, "TestException not raised"


def test_graph_concurrent_execution_with_failed_dependency():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    try:
        a.graph(pre_call=eat, raise_immediately=False, n_jobs=2)
    except FailedDependencyError:
        return
    assert False, "FailedDependencyError not raised"


def test_graph_concurrent_execution_with_failed_task_immediately():
    failed_dependency = Task(throw_exception)
    a = Task(partial(sleep, 1), dependencies=(failed_dependency,))
    try:
        a.graph(pre_call=eat, raise_immediately=True, n_jobs=2)
    except TestException:
        return
    assert False, "TestException not raised"
