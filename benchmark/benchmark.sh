#!/usr/bin/env bash

# This script is used to benchmark the performance of the program.

USE_PYGRAPHLIB=false python3 benchmark.py cgraphlib
USE_PYGRAPHLIB=true python3 benchmark.py pygraphlib