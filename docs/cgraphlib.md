# CGraphLib

## Introduction

[cgraphlib](https://github.com/alexanderepstein/taskade/blob/mainline/src/cgraphlib/cgraphlib.c) is a C extension for Python that provides a more efficient implementation of the internal toplogical graph sorter. This is the default implementation Taskade uses for execution.

The extension was inspired by [graphlib](https://docs.python.org/3/library/graphlib.html). The other advantage is that coupled with the fact that taskade has no dependencies it is possible to still use taskade on versions of python that don't support graphlib.

## Benchmark

To benchmark the performance of Taskade, we will be using the [benchmark.py](https://github.com/alexanderepstein/taskade/blob/mainline/benchmark/benchmark.py) script by calling [benchmark.sh](https://github.com/alexanderepstein/taskade/blob/mainline/benchmark/benchmark.sh). This script will create a random DAG with a specified number of tasks and dependencies, and then execute the DAG using Taskade and a few other popular libraries.


--8<-- "benchmark_results.html"

<div align="center">
<a href="../benchmark_results.png">
<img src="../benchmark_results.png", alt="Results plots">
</a>
</div>
