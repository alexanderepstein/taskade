# 
<div align="center">

<img src="assets/logo_blue.png" alt="Taskade Logo" width="50%" height="50%">

<h3>
Effortless Task Management: Flexible, Fast, Simple and Reliable
</h3>

</div>

## Overview

Taskade is a Python framework designed to simplify the execution of tasks with dependencies. It provides a flexible and efficient way to manage task execution, allowing developers to focus on writing task logic rather than managing dependencies.

### Features

- **High Performance**: Optimized for speed and efficiency.
- **Easy to Use**: Simple and intuitive API.
- **Lightweight**: Taskade has no dependencies on anything outside of the standard library.
- **Flexible Execution**: Choose from various execution strategies, including sequential, concurrent, and asynchronous execution.
- **CGraphLib**: An C Extension intended to replace [python graphlib](https://docs.python.org/3/library/graphlib.html), [cgraphlib](https://github.com/alexanderepstein/taskade/blob/mainline/src/cgraphlib/cgraphlib.c). With up to a ~2.5x performance improvement over the standard library.

### Design Principles

Taskade is designed with the following principles in mind:

* **Separation of Concerns**: Task logic is separate from execution logic.
* **Flexibility**: Support for various execution strategies and task types.
* **Efficiency**: Optimize task execution for performance.

### Use Cases

Taskade is suitable for applications that require:

* **Complex Task Dependencies**: Manage complex task dependencies with ease.
* **High-Performance Execution**: Execute tasks concurrently for improved performance.
* **Asynchronous Tasks**: Support for asynchronous tasks and execution.

## Installation

To install Taskade, you can use pip or your preferred package manager.

```sh
pip install taskade
```

!!! tip

    To get the full speed improvement for larger DAGs execute taskade with the cgraphlib optional dependency. See [cgraphlib](cgraphlib.md) for more information. cgraphlib is enabled by default and python graphlib can be used by setting the environment variable `USE_PYGRAPHLIB` to `true`.

After installation head over to the [quick start](quick_start.md) page to get started with creating and executing graphs.
