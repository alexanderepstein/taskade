import asyncio
from time import sleep

import pytest

from syncra import get_graph, task


@task(graph_name="my_graph2", name="task_a_1")
@task(graph_name="my_graph", name="task_a_2")
async def task_a() -> str:
    """
    An asynchronous task that sleeps for 1 second and returns a completion message.

    :return: A string indicating task completion
    """
    await asyncio.sleep(0.1)
    return "Task A completed"


@task(graph_name="my_graph", name="task_b_1")
@task(graph_name="my_graph2", name="task_b_1", dependencies="task_a_1")
@task(graph_name="my_graph2", name="task_b_2", dependencies=("task_a_1"))
async def task_b(*args) -> str:
    """
    An asynchronous task that sleeps for 0.5 seconds and returns a completion message.

    :return: A string indicating task completion
    """
    await asyncio.sleep(0.5)
    return "Task B completed"


@task(graph_name="my_graph", dependencies=("task_a_2", "task_b_1"))
async def task_c(a_output: str, b_output: str) -> str:
    """
    An asynchronous task that depends on task_a and task_b, sleeps for 1 second, and returns a completion message.

    :param a_output: The output from task_a
    :param b_output: The output from task_b
    :return: A string indicating task completion
    """
    await asyncio.sleep(0.1)
    return "Task C completed"


@task(graph_name="my_graph", dependencies="task_c")
@task(graph_name="my_graph2", dependencies="task_b_1")
def task_d(*args, **kwargs):
    sleep(0.1)
    return "Task D completed"


@task(graph_name="init_kwargs_graph", init_kwargs={"value": "init"})
async def task_e(value):
    return value


@pytest.mark.asyncio
async def test_graph_execution():
    """
    Test the execution of a graph.
    """
    # Retrieve the graph by name
    graph = get_graph("my_graph")

    # Execute the graph if it exists
    results = await graph()
    assert tuple(results.values()) == (
        "Task A completed",
        "Task B completed",
        "Task C completed",
        "Task D completed",
    )


@pytest.mark.asyncio
async def test_init_kwargs_graph_execution():
    """
    Test the execution of a graph.
    """
    # Retrieve the graph by name
    graph = get_graph("init_kwargs_graph")

    # Execute the graph if it exists
    results = await graph()
    assert tuple(results.values()) == ("init",)


@pytest.mark.asyncio
async def test_graph2_execution():
    """
    Test the execution of a graph.
    """
    # Retrieve the graph by name
    graph = get_graph("my_graph2")

    # Execute the graph if it exists
    results = await graph()
    assert tuple(results.values()) == (
        "Task A completed",
        "Task B completed",
        "Task B completed",
        "Task D completed",
    )


@pytest.mark.asyncio
async def test_misaligned_graph():
    try:

        @task(graph_name="no_use_graph", dependencies="task_c")
        async def task_z():
            pass
    except ValueError:
        return
    assert False


@pytest.mark.asyncio
async def test_async_task_execution():
    # Call tasks directly
    result_a = await task_a()
    assert result_a == "Task A completed"


def test_sync_task_execution():
    # Call tasks directly
    result_d = task_d()
    assert result_d == "Task D completed"
