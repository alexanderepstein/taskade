# Usage


## Task Creation

You can create tasks by initializing a [Task][syncra.Task]:

```python
from syncra import Task

def task_a_func():
    return "Task A"

def task_b_func(result_a):
    return f"Task B received {result_a}"

def task_c_func(result_a, result_b):
    return f"Task C recieved {result_a} & {result_b}

def main():
    task_a = Task(
        name="task_a",
        func=task_a_func,
    )

    # You can set output names, one per output of the function, 
    # these will be passed as kwargs to all of its dependencies
    task_b = Task(
        name="task_b",
        func=task_b_func,
        dependencies=task_a
        output_names="task_b" 
    )

    task_c = Task(
        name="task_c",
        func=task_b_func,
        dependencies=task_a & task_b, # Notice how dependencies can be tied together with &
        output_names="task_c"
    )

    # A graph is implicitly created once task_b is created
    # because it has a dependency on task_a
    # The graph can be accessed using any task part of the graph.
    graph = task_a.graph

    # Now you can execute the graph
    results = graph()
    print(results)

if __name__ == "__main__":
    main()
```

Tasks can be sync, async or a mixture of the two. 

!!! Implicit Graph Creation
    Note that we don't need to set the graph_name argument when creating the tasks, because a graph is implicitly created once task_b is created due to its dependency on task_a.

!!! note Task Creation Without Graph Name
    When tasks are created without a `graph_name` the graph cannot be retrieved with the [get_graph][syncra.get_graph] method.



## Task Decorators

You can create tasks using the [@task][syncra.task] decorator:

```python
from syncra import task

@task(graph_name="my_graph")
def task_a():
    return "Task A"

@task(graph_name="my_graph", dependencies=task_a, name="b") 
def task_b():
    return "Task B"

@task(graph_name="my_graph", dependencies="b") # Task b can be referred to by name
def task_c():
    return "Task C"
```

## Explict Graph Creation

Creating a [Graph][syncra.Graph] object and adding tasks to it:

```python
from syncra import Graph

graph = Graph(name="my_graph")
graph += task_a
graph += task_b
graph += task_c
```

## Executing a Graph

You can execute a graph using the `__call__` method:

```python
results = graph()
```
If the graph had any async tasks then the `__call__` will return an [Awaitable] so we have to `await` the call method.

```python
results = await graph()
```

Or with custom pre and post call functions:

```
results = graph()
```

## Retrieving Task Results

When a graph is executed, the execution method returns a dictionary where the keys are the task objects and the values are the results of the tasks.
You can retrieve the result of a task by indexing the dictionary with the task object itself:

```python
results = graph()

# Get the result of task_a
result_a = results[task_a]
print(result_a)  # Output: "Task A"

# Get the result of task_b
result_b = results[task_b]
print(result_b)  # Output: "Task B"

# Get the result of task_c
result_c = results[task_c]
print(result_c)  # Output: "Task C"
```

This allows you to easily access the results of individual tasks after executing the graph.
Note that if a task raises an exception during execution, the corresponding value in the results dictionary will be the exception object itself. You can check if a task raised an exception by using the isinstance function:


```python
if isinstance(results[task_a], Exception):
    print("Task A raised an exception")
else:
    print("Task A executed successfully")
```


## Pre and Post Call Functions

Pre and post call functions are optional functions that can be executed before and after a task is executed, respectively. They can be used to perform setup or teardown operations, logging, or any other actions that need to be taken in conjunction with the task execution.

Using Pre and Post Call Functions
You can pass pre and post call functions to the graph execution method:

```python
def pre_call(task, *args, **kwargs):
    print(f"Pre-call for {task=}")

def post_call(result, *args):
    print("Post-call")

results = graph(pre_call=pre_call, post_call=post_call)
```

Pre and Post Call functions can be set either at the task level, graph execution level or both.
The task level Pre and Post call functions will always take precendence over the graph level version.


## Calling Tasks Outside of Syncra

Even though a function is decorated with [@task][syncra.task], it can still be called outside of the Syncra framework just like a normal function:

```python
result = task_a()
print(result)  # Output: "Task A"
```

This allows you to test or use your tasks independently of the Syncra framework.


To see even more advanced functionality check out the [advanced usage](advanced_usage.md)