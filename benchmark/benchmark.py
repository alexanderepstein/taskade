import asyncio
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from multiprocessing import cpu_count
from random import choices, randint, seed
from time import sleep
from typing import Any, Callable, List
from uuid import uuid4

from tqdm import tqdm

from syncra import Graph, Task

logging.basicConfig(level=logging.DEBUG)

SLEEP_TIME = 1e-10
MAX_DEPENDENCIES = 100


def no_op(*args, **kwargs):
    sleep(SLEEP_TIME)
    return "n"


async def ano_op(*args, **kwargs):
    await asyncio.sleep(SLEEP_TIME)
    return "a"


def create_tasks(task_count: int, task_func: Callable[[], None], graph: Any) -> List[Any]:
    assert task_count > 0, "Task count must be greater than 0"
    seed(0)  # Reproducibility
    tasks: List[Task] = [Task(task_func, name="0", _graph=graph)]
    for task_number in range(1, task_count):
        tasks.append(
            Task(
                task_func,
                name=str(task_number),
                _graph=graph,
                dependencies=tuple(set(choices(tasks, k=randint(0, min(MAX_DEPENDENCIES, len(tasks) - 1))))),
            )
        )
    return tasks


def execute_bench(task_count: int, **kwargs) -> float:
    progress = tqdm(total=task_count, desc=f"Executing {task_count} tasks")

    def post_call(result, *args):
        progress.update(n=1)

    graph = Graph(name=str(uuid4()))
    start = datetime.now()
    create_tasks(task_count, no_op, graph=graph)

    results = graph(post_call=post_call, **kwargs)

    end = datetime.now()
    elapsed = (end - start).total_seconds()
    assert len(results) == task_count, "Not all tasks were completed"
    progress.close()
    return elapsed


async def aexecute_bench(task_count: int) -> float:
    progress = tqdm(total=task_count, desc=f"Executing {task_count} async tasks")

    def post_call(result, *args):
        progress.update(n=1)

    graph = Graph(name=str(uuid4()))
    start = datetime.now()
    create_tasks(task_count, ano_op, graph=graph)

    results = await graph(post_call=post_call)

    end = datetime.now()
    elapsed = (end - start).total_seconds()

    progress.close()
    assert len(results) == task_count, "Not all tasks were completed"
    return elapsed


def benchmark():
    task_counts = [1, 10, 100, 500, 1000, 5000, 10000, 50000, 100000]

    sync_results = {task_count: [] for task_count in task_counts}
    threaded_results = {task_count: [] for task_count in task_counts}
    process_results = {task_count: [] for task_count in task_counts}
    async_results = {task_count: [] for task_count in task_counts}

    for _ in range(30):  # Many iterations to average out outliers
        for task_count in task_counts:
            sync_results[task_count].append(execute_bench(task_count))

            threaded_results[task_count].append(execute_bench(task_count, n_jobs=int(2.66 * cpu_count())))

            process_results[task_count].append(
                execute_bench(task_count, concurrency_pool=ProcessPoolExecutor, n_jobs=int(2.66 * cpu_count()))
            )

            async_results[task_count].append(asyncio.run(aexecute_bench(task_count)))
    with open(f"BenchmarkResults-{sys.argv[1]}.json", "w") as out_file:
        json.dump(
            {
                "sync": sync_results,
                "threaded": threaded_results,
                "process": process_results,
                "async": async_results,
            },
            out_file,
            indent=4,
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python benchmark.py <output_file_extension>")
        exit(1)
    benchmark()
