import asyncio
from functools import partial

import pytest

from tanto._base import Task, eat


async def asleep(seconds) -> str:
    await asyncio.sleep(seconds)
    return f"{seconds=}"


@pytest.mark.asyncio
async def test_graph_execution():
    a = Task(partial(asleep, 1))
    b = Task(partial(asleep, 0.5))
    c = Task(partial(asleep, 1), a & b)
    d = Task(partial(asleep, 0.5), b)
    results = await a.graph(pre_call=eat)
    assert results[a] == "seconds=1"
    assert results[b] == "seconds=0.5"
    assert results[c] == "seconds=1"
    assert results[d] == "seconds=0.5"
