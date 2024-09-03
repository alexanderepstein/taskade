#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define _NODE_OUT -1
#define _NODE_DONE -2
typedef struct {
    PyObject_HEAD
    PyObject *node;
    int npredecessors;
    PyObject *successors;
} NodeInfoObject;

static void NodeInfo_dealloc(NodeInfoObject *self) {
    Py_XDECREF(self->node);
    Py_XDECREF(self->successors);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *NodeInfo_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    NodeInfoObject *self;
    self = (NodeInfoObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->node = NULL;
        self->npredecessors = 0;
        self->successors = PyList_New(0);
        if (self->successors == NULL) {
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject *)self;
}

static int NodeInfo_init(NodeInfoObject *self, PyObject *args, PyObject *kwds) {
    PyObject *node = NULL;
    if (!PyArg_ParseTuple(args, "O", &node)) {
        return -1;
    }
    if (node) {
        Py_INCREF(node);
        Py_XDECREF(self->node);
        self->node = node;
    }

    // Ensure 'successors' is correctly set up
    if (self->successors == NULL) {
        self->successors = PyList_New(0);  // Initialize if not already done
        if (self->successors == NULL) {
            return -1;
        }
    }

    return 0;
}

static PyTypeObject NodeInfoType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "cgraphlib.NodeInfo",
    .tp_basicsize = sizeof(NodeInfoObject),
    .tp_dealloc = (destructor)NodeInfo_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = NodeInfo_new,
    .tp_init = (initproc)NodeInfo_init,
    .tp_getattro = PyObject_GenericGetAttr,
    .tp_setattro = PyObject_GenericSetAttr,
};

typedef struct {
    PyObject_HEAD
    PyObject *node2info;
    PyObject *ready_nodes;
    int npassedout;
    int nfinished;
} TopologicalSorterObject;

static void TopologicalSorter_dealloc(TopologicalSorterObject *self) {
    Py_XDECREF(self->node2info);
    Py_XDECREF(self->ready_nodes);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *TopologicalSorter_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    TopologicalSorterObject *self;
    self = (TopologicalSorterObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->node2info = PyDict_New();
        self->ready_nodes = NULL;
        self->npassedout = 0;
        self->nfinished = 0;
    }
    return (PyObject *)self;
}

static PyObject *TopologicalSorter_get_nodeinfo(TopologicalSorterObject *self, PyObject *node) {
    PyObject *nodeinfo = PyDict_GetItem(self->node2info, node);
    if (nodeinfo == NULL) {
        nodeinfo = PyObject_CallFunction((PyObject *) &NodeInfoType, "O", node);
        if (nodeinfo == NULL) {
            return NULL;
        }
        PyDict_SetItem(self->node2info, node, nodeinfo);
        Py_DECREF(nodeinfo);
    }
    return nodeinfo;
}

static PyObject *TopologicalSorter_add(TopologicalSorterObject *self, PyObject *args) {
    PyObject *node;
    PyObject *predecessors = NULL;
    if (!PyArg_ParseTuple(args, "O|O", &node, &predecessors))
        return NULL;

    if (self->ready_nodes != NULL) {
        PyErr_SetString(PyExc_ValueError, "Nodes cannot be added after a call to prepare()");
        return NULL;
    }

    // Get the NodeInfo for the current node
    PyObject *nodeinfo = TopologicalSorter_get_nodeinfo(self, node);
    if (nodeinfo == NULL) return NULL;

    if (predecessors != NULL) {
        if (!PyTuple_Check(predecessors)) {
            PyErr_SetString(PyExc_TypeError, "predecessors must be a tuple");
            return NULL;
        }

        Py_ssize_t num_preds = PyTuple_Size(predecessors);
        ((NodeInfoObject *) nodeinfo)->npredecessors += num_preds;

        for (Py_ssize_t i = 0; i < num_preds; i++) {
            PyObject *pred = PyTuple_GetItem(predecessors, i);
            PyObject *pred_info = TopologicalSorter_get_nodeinfo(self, pred);
            if (pred_info == NULL) return NULL;
            
            if (PyList_Append(((NodeInfoObject *)pred_info)->successors, node) < 0) {
                return NULL;  // Error occurred during append
            }
            
            Py_INCREF(node);  // Increment reference count for the appended node
        }
    }

    Py_RETURN_NONE;
}

static PyObject* TopologicalSorter_find_cycle(TopologicalSorterObject *self, PyObject *Py_UNUSED(ignored)) {
    PyObject *n2i = self->node2info;
    PyObject *stack = PyList_New(0);
    PyObject *itstack = PyList_New(0);
    PyObject *seen = PySet_New(NULL);
    PyObject *node2stacki = PyDict_New();

    if (!stack || !itstack || !seen || !node2stacki) {
        Py_XDECREF(stack);
        Py_XDECREF(itstack);
        Py_XDECREF(seen);
        Py_XDECREF(node2stacki);
        PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory for cycle detection");
        return NULL;
    }

    PyObject *nodes = PyDict_Keys(n2i);
    for (Py_ssize_t i = 0; i < PyList_Size(nodes); i++) {
        PyObject *node = PyList_GetItem(nodes, i);
        if (PySet_Contains(seen, node) == 1) {
            continue;
        }

        while (1) {
            int in_seen = PySet_Contains(seen, node);
            if (in_seen == -1) {
                goto cleanup;
            }

            if (in_seen == 1) {
                PyObject *stacki = PyDict_GetItem(node2stacki, node);
                if (stacki != NULL) {
                    Py_ssize_t start = PyLong_AsSsize_t(stacki);
                    PyObject *cycle = PyList_GetSlice(stack, start, PyList_Size(stack));
                    if (PyList_Append(cycle, node) < 0) {
                        Py_DECREF(cycle);
                        goto cleanup;
                    }
                    goto success;
                }
            } else {
                if (PySet_Add(seen, node) < 0) {
                    goto cleanup;
                }

                NodeInfoObject *nodeinfo = (NodeInfoObject *)PyDict_GetItem(n2i, node);
                PyObject *successors = nodeinfo->successors;
                PyObject *iterator = PyObject_GetIter(successors);
                if (!iterator) {
                    goto cleanup;
                }

                if (PyList_Append(itstack, iterator) < 0) {
                    Py_DECREF(iterator);
                    goto cleanup;
                }
                Py_DECREF(iterator);

                PyObject *stacki = PyLong_FromSsize_t(PyList_Size(stack));
                if (PyDict_SetItem(node2stacki, node, stacki) < 0) {
                    Py_DECREF(stacki);
                    goto cleanup;
                }
                Py_DECREF(stacki);

                if (PyList_Append(stack, node) < 0) {
                    goto cleanup;
                }
            }

            while (PyList_Size(stack) > 0) {
                PyObject *iterator = PyList_GetItem(itstack, PyList_Size(itstack) - 1);
                PyObject *next_node = PyIter_Next(iterator);
                if (next_node) {
                    node = next_node;
                    Py_DECREF(next_node);
                    break;
                } else if (PyErr_Occurred()) {
                    goto cleanup;
                } else {
                    if (PyList_SetSlice(itstack, PyList_Size(itstack) - 1, PyList_Size(itstack), NULL) < 0) {
                        goto cleanup;
                    }
                    PyObject *last_node = PyList_GetItem(stack, PyList_Size(stack) - 1);
                    if (PyDict_DelItem(node2stacki, last_node) < 0) {
                        goto cleanup;
                    }
                    if (PyList_SetSlice(stack, PyList_Size(stack) - 1, PyList_Size(stack), NULL) < 0) {
                        goto cleanup;
                    }
                }
            }

            if (PyList_Size(stack) == 0) {
                break;
            }
        }
    }

    Py_DECREF(nodes);
    Py_DECREF(stack);
    Py_DECREF(itstack);
    Py_DECREF(seen);
    Py_DECREF(node2stacki);
    Py_RETURN_NONE;

cleanup:
    Py_XDECREF(nodes);
    Py_XDECREF(stack);
    Py_XDECREF(itstack);
    Py_XDECREF(seen);
    Py_XDECREF(node2stacki);
    return NULL;

success:
    Py_DECREF(nodes);
    Py_DECREF(stack);
    Py_DECREF(itstack);
    Py_DECREF(seen);
    Py_DECREF(node2stacki);
    Py_RETURN_NONE;
}

static PyObject *TopologicalSorter_prepare(TopologicalSorterObject *self, PyObject *Py_UNUSED(ignored)) {
    if (self->ready_nodes != NULL) {
        PyErr_SetString(PyExc_ValueError, "cannot prepare() more than once");
        return NULL;
    }

    self->ready_nodes = PyList_New(0);
    if (self->ready_nodes == NULL) {
        PyErr_SetString(PyExc_MemoryError, "Failed to create ready_nodes list");
        return NULL;
    }

    PyObject *node2info = self->node2info;
    PyObject *items = PyDict_Items(node2info);
    if (items == NULL) {
        Py_DECREF(self->ready_nodes);
        self->ready_nodes = NULL;
        return NULL;
    }

    for (Py_ssize_t i = 0; i < PyList_Size(items); i++) {
        PyObject *item = PyList_GetItem(items, i);
        PyObject *node = PyTuple_GetItem(item, 0);
        NodeInfoObject *info = (NodeInfoObject *)PyTuple_GetItem(item, 1);

        if (info->npredecessors == 0) {
            if (PyList_Append(self->ready_nodes, node) < 0) {
                Py_DECREF(items);
                Py_DECREF(self->ready_nodes);
                self->ready_nodes = NULL;
                return NULL;
            }
        }
    }
    Py_DECREF(items);

    PyObject *cycle = TopologicalSorter_find_cycle(self, NULL);
    if (cycle == NULL) {
        Py_DECREF(self->ready_nodes);
        self->ready_nodes = NULL;
        return NULL;
    }
    if (cycle != Py_None) {
        PyObject *cycle_error = PyObject_CallFunction(PyExc_ValueError, "sO", "nodes are in a cycle", cycle);
        Py_DECREF(cycle);
        Py_DECREF(self->ready_nodes);
        self->ready_nodes = NULL;
        PyErr_SetObject(PyExc_ValueError, cycle_error);
        Py_XDECREF(cycle_error);
        return NULL;
    }
    Py_DECREF(cycle);

    Py_RETURN_NONE;
}

static PyObject *TopologicalSorter_get_ready(TopologicalSorterObject *self, PyObject *Py_UNUSED(ignored)) {
    if (self->ready_nodes == NULL) {
        PyErr_SetString(PyExc_ValueError, "prepare() must be called first");
        return NULL;
    }

    PyObject *result = PyTuple_New(PyList_Size(self->ready_nodes));
    for (Py_ssize_t i = 0; i < PyTuple_Size(result); i++) {
        PyObject *node = PyList_GetItem(self->ready_nodes, i);
        NodeInfoObject *nodeinfo = (NodeInfoObject *) PyDict_GetItem(self->node2info, node);
        nodeinfo->npredecessors = _NODE_OUT;
        PyTuple_SetItem(result, i, node);
        Py_INCREF(node);
    }

    PyList_SetSlice(self->ready_nodes, 0, PyList_Size(self->ready_nodes), NULL);
    self->npassedout += PyTuple_Size(result);
    return result;
}

static PyObject *TopologicalSorter_is_active(TopologicalSorterObject *self, PyObject *Py_UNUSED(ignored)) {
    if (self->ready_nodes == NULL) {
        PyErr_SetString(PyExc_ValueError, "prepare() must be called first");
        return NULL;
    }
    if (self->nfinished < self->npassedout || PyList_Size(self->ready_nodes) > 0) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyObject *TopologicalSorter_done(TopologicalSorterObject *self, PyObject *args) {
    if (self->ready_nodes == NULL) {
        PyErr_SetString(PyExc_ValueError, "prepare() must be called first");
        return NULL;
    }
    PyObject *node = NULL;
    if (!PyArg_ParseTuple(args, "O", &node)) {
        PyErr_Format(PyExc_ValueError, "node was not found in done() call");
    }
    
    NodeInfoObject *nodeinfo = (NodeInfoObject *) PyDict_GetItem(self->node2info, node);

    if (nodeinfo == NULL) {
        PyErr_Format(PyExc_ValueError, "node %R was not added using add()", node);
        return NULL;
    }

    int stat = nodeinfo->npredecessors;
    if (stat != _NODE_OUT) {
        if (stat >= 0) {
            PyErr_Format(PyExc_ValueError, "node %R was not passed out (still not ready)", node);
            return NULL;
        } else if (stat == _NODE_DONE) {
            PyErr_Format(PyExc_ValueError, "node %R was already marked done", node);
            return NULL;
        } else {
            PyErr_Format(PyExc_SystemError, "node %R: unknown status %d", node, stat);
            return NULL;
        }
    }

    nodeinfo->npredecessors = _NODE_DONE;

    for (Py_ssize_t j = 0; j < PyList_Size(nodeinfo->successors); j++) {
        PyObject *successor = PyList_GetItem(nodeinfo->successors, j);
        NodeInfoObject *successor_info = (NodeInfoObject *) PyDict_GetItem(self->node2info, successor);
        successor_info->npredecessors -= 1;
        if (successor_info->npredecessors == 0) {
            PyList_Append(self->ready_nodes, successor);
        }
    }
    self->nfinished += 1;
    Py_RETURN_NONE;
}

static PyObject* TopologicalSorter_static_order(TopologicalSorterObject *self, PyObject *Py_UNUSED(ignored)) {
    // Prepare the graph
    PyObject *prepare_result = TopologicalSorter_prepare(self, NULL);
    if (prepare_result == NULL) {
        return NULL;  // Error during preparation
    }
    Py_DECREF(prepare_result);

    // Create a generator for the topological order
    PyObject *generator = PyList_New(0);
    if (generator == NULL) {
        return NULL;  // Memory allocation failure
    }

    while (TopologicalSorter_is_active(self, NULL) == Py_True) {
        PyObject *node_group = TopologicalSorter_get_ready(self, NULL);
        if (node_group == NULL) {
            Py_DECREF(generator);
            return NULL;  // Error retrieving ready nodes
        }

        for (Py_ssize_t i = 0; i < PyTuple_Size(node_group); i++) {
            PyObject *node = PyTuple_GetItem(node_group, i);
            PyObject *done_result = TopologicalSorter_done(self, Py_BuildValue("(O)", node));
            if (done_result == NULL) {
                Py_DECREF(generator);
                Py_DECREF(node_group);
                return NULL;  // Error marking nodes as done
            }
            Py_DECREF(done_result);
        }
    }

    // Return the generator as a Python iterable
    PyObject *iterable = PyObject_GetIter(generator);
    Py_DECREF(generator);
    return iterable;
}

// Define methods table
static PyMethodDef TopologicalSorter_methods[] = {
    {"add", (PyCFunction) TopologicalSorter_add, METH_VARARGS, "Add a new node and its predecessors to the graph"},
    {"prepare", (PyCFunction) TopologicalSorter_prepare, METH_NOARGS, "Prepare the graph for sorting"},
    {"get_ready", (PyCFunction) TopologicalSorter_get_ready, METH_NOARGS, "Get the list of nodes ready for processing"},
    {"is_active", (PyCFunction) TopologicalSorter_is_active, METH_NOARGS, "Check if the sorter is active"},
    {"done", (PyCFunction) TopologicalSorter_done, METH_VARARGS, "Mark nodes as done"},
    {"_find_cycle", (PyCFunction) TopologicalSorter_find_cycle, METH_NOARGS, "Find cycles in the graph"},
    {"static_order", (PyCFunction) TopologicalSorter_static_order, METH_NOARGS, "Return nodes in topological order"},
    {NULL, NULL, 0, NULL}  // Sentinel entry
};

static PyTypeObject TopologicalSorterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "cgraphlib.TopologicalSorter",
    .tp_basicsize = sizeof(TopologicalSorterObject),
    .tp_dealloc = (destructor) TopologicalSorter_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = TopologicalSorter_new,
    .tp_methods = TopologicalSorter_methods,
};

// Module definition
static PyModuleDef cgraphlibmodule = {
    PyModuleDef_HEAD_INIT,
    "cgraphlib",
    "C Rewrite of graphlib",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC PyInit_cgraphlib(void) {
    PyObject *m;
    if (PyType_Ready(&NodeInfoType) < 0)
        return NULL;

    if (PyType_Ready(&TopologicalSorterType) < 0)
        return NULL;

    m = PyModule_Create(&cgraphlibmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&NodeInfoType);
    PyModule_AddObject(m, "NodeInfo", (PyObject *) &NodeInfoType);

    Py_INCREF(&TopologicalSorterType);
    PyModule_AddObject(m, "TopologicalSorter", (PyObject *) &TopologicalSorterType);

    return m;
}
