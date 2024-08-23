<div align="center">

![logo](docs/assets/logo.png)

### Effortless Task Management: Flexible, Fast, and Reliable Execution

</div>

## Overview

Syncra is a Python framework designed to simplify the execution of tasks with dependencies. It provides a flexible and efficient way to manage task execution, allowing developers to focus on writing task logic rather than managing dependencies.

### Key Features

* **Task Graphs**: Define tasks and their dependencies using a simple API.
* **Concurrent Execution**: Execute tasks concurrently using threads or processes.
* **Async Support**: Supports asynchronous tasks and execution.
* **Flexible Execution**: Choose from various execution strategies, including sequential, concurrent, and asynchronous execution.

### Design Principles
Syncra is designed with the following principles in mind:

* **Separation of Concerns**: Task logic is separate from execution logic.
* **Flexibility**: Support for various execution strategies and task types.
* **Efficiency**: Optimize task execution for performance.

### Use Cases
Syncra is suitable for applications that require:

* **Complex Task Dependencies**: Manage complex task dependencies with ease.
* **High-Performance Execution**: Execute tasks concurrently for improved performance.
* **Asynchronous Tasks**: Support for asynchronous tasks and execution.

## Getting Started

### Install Syncra

```python
pip install syncra
```

### Sync Tasks

To create a Task, the simplest way is through the @task decorator:

```python
from syncra import task

@task(graph_name='my_graph')
def my_task():
    # Task implementation
    return "example_output"

@task(graph_name='my_graph', dependencies=my_task)
def my_second_task():
    # Task implementation
    return "example_output"

@task(graph_name='my_graph')
def my_third_task():
    # Task implementation
    return "example_output"

@task(graph_name="my_graph", dependencies=(my_second_task, my_third_task))
def my_final_task(dependent_result)
    print(dependent_result)
    return "final_example_output"
```

Using the decorator automatically creates a Graph and allows it to be executed.

```python
from syncra import get_graph

def main():
    results = get_graph("my_graph")() # Call the execution of the graph
    print(results[my_task]) # Prints `example_output`
    print(results[my_final_task]) # Prints `final_example_output`

if __name__ == "__main__":
    main()
```

### Combine Sync & Async Tasks

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

