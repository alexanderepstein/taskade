from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Type, TypeVar, Union

_T = TypeVar("_T")
"""Type variable for the return type of a task"""

PoolExecutor = TypeVar(
    "PoolExecutor",
    bound=Union[
        Union[Union[ThreadPoolExecutor, ProcessPoolExecutor], Type[ThreadPoolExecutor]], Type[ProcessPoolExecutor]
    ],
)
"""Type variable for the pool type passed to concurrent execution"""
