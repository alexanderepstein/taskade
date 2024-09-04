# 
<div align="center">

<img src="assets/logo_blue.png" alt="Syncra Logo" width="50%" height="50%">

### Effortless Task Management: Flexible, Fast, Simple and Reliable

</div>

## Overview

Syncra is a Python framework designed to simplify the execution of tasks with dependencies. It provides a flexible and efficient way to manage task execution, allowing developers to focus on writing task logic rather than managing dependencies.


### Features

- **High Performance**: Optimized for speed and efficiency.
- **Easy to Use**: Simple and intuitive API.
- **Lightweight**: Syncra has no dependencies on anything outside of the standard library.
- **Flexible Execution**: Choose from various execution strategies, including sequential, concurrent, and asynchronous execution.
- **CGraphLib**: An optional dependency written for Syncra [cgraphlib](https://github.com/alexanderepstein/syncra/blob/mainline/src/cgraphlib/cgraphlib.c). With up to a ~2.5x performance improvement over the standard library.


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
## Installation

To install Syncra, you can use pip or your preferred package manager.

!!! tip

    To get the full speed improvement for larger DAGs install syncra with the cgraphlib optional dependency. See [cgraphlib](cgraphlib.md) for more information.

=== "cgraphlib"

    ```sh
    pip install syncra[cgraphlib]
    ```

=== "std"

    ```sh
    pip install syncra
    ```

!!! note

    syncra is compatible with versions of python 3.8 and greater, however for 3.8 its only available with the cgraphlib optional dependency



After installation head over to the [quick start](quick_start.md) page to get started with creating and executing graphs.
