# Quick Start

Creating and exeucting graphs in Syncra is simple and flexible.

## Sync Tasks

To create a [Task][syncra.Task], use the [@task][syncra.task] decorator:

```python
from syncra import task

@task(graph_name='my_graph')
def my_task():
    # Task implementation
    return "example_output"

@task(graph_name="my_graph", dependencies=my_task)
def my_final_task(dependent_result)
    print(dependent_result)
    return "final_example_output"
```

Using the decorator automatically creates a [Graph][syncra.Graph] and allows it to be executed.

```python
from syncra import get_graph

def main():
    results = get_graph("my_graph")() # Call the execution of the graph
    print(results[my_task]) # Prints `example_output`
    print(results[my_final_task]) # Prints `final_example_output`

if __name__ == "__main__":
    main()
```

## Async Tasks

Allowing for async execution is as easy as having tasks that are async functions and using the `await` keyword when calling the graph execution.

```python
from syncra import task, get_graph
import asyncio

@task(graph_name='my_graph')
async def my_task():
    # Task implementation
    return "example_output"

@task(graph_name="my_graph", dependencies=my_task)
async def my_final_task(dependent_result)
    print(dependent_result)
    return "final_example_output"

async def main():
    results = await get_graph("my_graph")() # Call the execution of the graph with await
    print(results[my_task]) # Prints `example_output`
    print(results[my_final_task]) # Prints `final_example_output`

if __name__ == "__main__":
    asyncio.run(main())
```

## Combine Sync & Async Tasks

Syncra graphs also allow for mixing async and sync tasks within the same graph. Blocking will occur only when an sync function is executing, but otherwise the same async behavior will be preserved. 

```python
from syncra import task

@task(graph_name='my_graph')
async def my_task():
    # Task implementation
    return "example_output"

@task(graph_name="my_graph", dependencies=my_task)
def my_final_task(dependent_result)
    print(dependent_result)
```

you will still need to execute the graph using `await` as some of the nodes are async.

```python
from syncra import get_graph
import asyncio

async def main():
    results = await get_graph("my_graph")() # Call the execution of the graph
    print(results[my_task]) # Prints `example_output`
    print(results[my_final_task]) # Prints `final_example_output`

if __name__ == "__main__":
    asyncio.run(main())
```

