import asyncio
from time import sleep

import pytest

from tanto import get_graph, task


@task(graph_name="my_graph")
async def task_a() -> str:
    """
    An asynchronous task that sleeps for 1 second and returns a completion message.

    :return: A string indicating task completion
    """
    await asyncio.sleep(0.1)
    return "Task A completed"


@task(graph_name="my_graph")
async def task_b() -> str:
    """
    An asynchronous task that sleeps for 0.5 seconds and returns a completion message.

    :return: A string indicating task completion
    """
    await asyncio.sleep(0.5)
    return "Task B completed"


@task(graph_name="my_graph", dependencies=(task_a, task_b))
async def task_c(a_output: str, b_output: str) -> str:
    """
    An asynchronous task that depends on task_a and task_b, sleeps for 1 second, and returns a completion message.

    :param a_output: The output from task_a
    :param b_output: The output from task_b
    :return: A string indicating task completion
    """
    await asyncio.sleep(0.1)
    return "Task C completed"


@task(graph_name="my_graph", dependencies=task_c)
# @task(graph_name="my_graph2")
def task_d(*args, **kwargs):
    sleep(0.1)
    return "Task D completed"


@pytest.mark.asyncio
async def test_graph_execution():
    """
    Test the execution of a graph.
    """
    # Retrieve the graph by name
    graph = get_graph("my_graph")

    # Execute the graph if it exists
    if graph is not None:
        results = await graph()
        assert tuple(results.values()) == (
            "Task A completed",
            "Task B completed",
            "Task C completed",
            "Task D completed",
        )


@pytest.mark.asyncio
async def test_async_task_execution():
    # Call tasks directly
    result_a = await task_a()
    assert result_a == "Task A completed"


def test_sync_task_execution():
    # Call tasks directly
    result_d = task_d()
    assert result_d == "Task D completed"
