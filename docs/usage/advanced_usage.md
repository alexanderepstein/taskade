# Advanced Usage

## Using Multiple Task Decorators

You can use multiple task decorators on a single function to create multiple tasks with different dependencies and settings:

```python
from taskade import task

@task(graph_name="graph1", dependencies=("task_b",), name="task_a_1", output_names=("result_a",))
@task(graph_name="graph1", dependencies=("task_c",), name="task_a_2", output_names=("result_b",))
@task(graph_name="graph2", dependencies=("task_d",), name="task_a_3", output_names=("result_c",))
def task_a(arg):
    return arg

@task(graph_name="graph1")
def task_b():
    return "Task B"

@task(graph_name="graph1")
def task_c():
    return "Task C"

@task(graph_name="graph2")
def task_d():
    return "Task D"

@task(graph_name="graph1", dependencies=("task_a_1", "task_a_2"))
def task_e(result_a, result_b):
    return result_a, result_b
```

In this example, `task_a` takes an argument arg and returns it. The output names are specified as `result_a`, `result_b`, and `result_c` for each of the tasks created by the multiple decorators.
`task_e` depends on `task_a_1` and `task_a_2`, and takes two arguments `result_a` and `result_b`, which are the outputs of `task_a_1` and `task_a_2` respectively.
Note that the number of arguments in task_e matches the number of outputs from the dependencies `task_a_1` and `task_a_2`.

## Init Kwargs

You can pass initialization keyword arguments to tasks using the `init_kwargs` parameter:

```python
from taskade import task

@task(graph_name="graph", init_kwargs={"foo": "bar"})
def task_a(foo):
    return foo

graph = task_a.graph
results = graph()
print(results[task_a])  # Output: "bar"
```

This passes the foo keyword argument to `task_a` when it's executed.

## Using Output Names
You can specify output names for tasks using the `output_names` parameter:

```python
from taskade import task

@task(graph_name="graph", output_names=["result_a", "result_b"])
def task_a():
    return "Result A", "Result B"

@task(graph_name="graph", dependencies=["task_a"], init_kwargs={"result_a": None, "result_b": None})
def task_b(result_a, result_b):
    return result_a, result_b

graph = task_a.graph
results = graph()
print(results[task_b])  # Output: ("Result A", "Result B")
```

This sets the output names of `task_a` to `result_a` and `result_b`, and passes these outputs as keyword arguments to `task_b`.

## Creation from Dictionary
You can create a graph from a dictionary of tasks:

```python
from taskade import Graph, task

tasks = {
    "task_a": task_a,
    "task_b": task_b,
    "task_c": task_c,
}

graph = Graph.from_dict(tasks, name="my_graph")
results = graph()
print(results)
```

This creates a graph with the tasks in the dictionary and executes it.


## Controlling Concurrency

### Async Execution

You can control the concurrency of async execution by passing an async semaphore to the graph's `__call__` method:

```python
from taskade import task, get_graph

@task(graph_name="my_graph", output_names=["result_a"])
async def task_a():
    return "Result A"

@task(graph_name="my_graph", dependencies=(task_a, ), input_names=["result_a"])
async def task_b(result_a):
    return f"Task B received {result_a}"

async def main():
    graph = get_graph("my_graph")
    async with asyncio.Semaphore(5) as semaphore:
        results = await graph(tasks_semaphore=semaphore)
        print(results)
```

### Sync Execution

You can control the concurrency of sync execution by passing a pool to the graph's `__call__` method:

```python
from taskade import task, get_graph
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

@task(graph_name="my_graph", output_names=("result_a",))
def task_a():
    return "Result A"

@task(graph_name="my_graph", dependencies=(task_a,))
def task_b(result_a):
    return f"Task B received {result_a}"

graph = get_graph("my_graph")

with ThreadPoolExecutor(max_workers=5) as pool:
    results = graph(concurrency_pool=pool)
    print(results)

# or

with ProcessPoolExecutor(max_workers=5) as pool:
    results = graph(concurrency_pool=pool)
    print(results)
```

Or you can let taskade manage the pool for you by just passing in the `n_jobs` parameter. When executing a sync graph concurrently this way you can also pass in the type of pool into the `concurency_pool` parameter. By default it is set to [ThreadPoolExecutor][concurrent.futures.ThreadPoolExecutor].


```python
from taskade import task, get_graph
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

@task(graph_name="my_graph", output_names=("result_a",))
def task_a():
    return "Result A"

@task(graph_name="my_graph", dependencies=(task_a,))
def task_b(result_a):
    return f"Task B received {result_a}"

graph = get_graph("my_graph")

results = graph(n_jobs=5)
print(results)

# or

results = graph(n_jobs=5, concurrency_pool=ProcessPoolExecutor)
print(results)
```

In both examples, the `graph_name` parameter is used to set the name of the graph, and the [get_graph][taskade.get_graph] function is used to retrieve the graph. The graph is then called with the concurrency control parameters.