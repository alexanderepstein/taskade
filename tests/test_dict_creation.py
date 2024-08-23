from syncra._execution import Graph


def task_a():
    return "Task A completed"


func_map = {"task_a": task_a}


def test_graph_creation():
    test_dict = {"my_graph": [{"name": "task_a", "func": "task_a"}]}
    for graph_name, task_list in test_dict.items():
        graph = Graph.from_list(graph_name, task_list, func_map)
        assert graph.name == graph_name
