#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>

// Default initial capacity for the graph
#define DEFAULT_INITIAL_CAPACITY 5000

// Macros for bitset operations
#define BITSET_SIZE(n) (((n) + CHAR_BIT - 1) / CHAR_BIT)
#define BITSET_SET(a, i) ((a)[(i) / CHAR_BIT] |= (1 << ((i) % CHAR_BIT)))
#define BITSET_CLEAR(a, i) ((a)[(i) / CHAR_BIT] &= ~(1 << ((i) % CHAR_BIT)))
#define BITSET_TEST(a, i) ((a)[(i) / CHAR_BIT] & (1 << ((i) % CHAR_BIT)))

// Structure to hold information about each node in the graph
typedef struct {
    PyObject* node;
    int npredecessors;
    int* successors;
    int successors_count;
    int successors_capacity;
} NodeInfo;

// Main TopologicalSorter structure
typedef struct {
    PyObject_HEAD
    NodeInfo* nodes;
    int nodes_count;
    int nodes_capacity;
    int* ready_nodes;
    int ready_nodes_count;
    int ready_nodes_capacity;
    unsigned char* visited;
    unsigned char* done;
    PyObject* node_to_index;
    int npassedout;
    int nfinished;
} TopologicalSorter;

// TopologicalSorter type definition
static PyTypeObject TopologicalSorterType;

/*
 * Helper function to expand capacity of dynamic arrays.
 *
 * @param[in,out] array Pointer to the array to be expanded
 * @param[in,out] capacity Pointer to the current capacity
 * @param[in] element_size Size of each element in the array
 * @return 0 on success, -1 on failure
 */
static int expand_capacity(void** array, int* capacity, size_t element_size) {
    int new_capacity = *capacity * 2;
    void* new_array = realloc(*array, new_capacity * element_size);
    if (new_array == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    *array = new_array;
    *capacity = new_capacity;
    return 0;
}

/*
 * Get or create a node in the graph.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] node The Python object representing the node
 * @return Pointer to the NodeInfo structure for the node, or NULL on failure
 */
static NodeInfo* get_or_create_node(TopologicalSorter* self, PyObject* node) {
    PyObject* index_obj = PyDict_GetItem(self->node_to_index, node);
    int index;
    if (index_obj == NULL) {
        index = self->nodes_count++;
        if (index >= self->nodes_capacity) {
            if (expand_capacity((void**)&self->nodes, &self->nodes_capacity, sizeof(NodeInfo)) < 0) {
                return NULL;
            }
            if (expand_capacity((void**)&self->ready_nodes, &self->ready_nodes_capacity, sizeof(int)) < 0) {
                return NULL;
            }
            size_t new_bitset_size = BITSET_SIZE(self->nodes_capacity);
            self->visited = realloc(self->visited, new_bitset_size);
            self->done = realloc(self->done, new_bitset_size);
            if (self->visited == NULL || self->done == NULL) {
                PyErr_NoMemory();
                return NULL;
            }
            memset(self->visited + BITSET_SIZE(index), 0, new_bitset_size - BITSET_SIZE(index));
            memset(self->done + BITSET_SIZE(index), 0, new_bitset_size - BITSET_SIZE(index));
        }
        PyObject* index_obj = PyLong_FromLong(index);
        if (index_obj == NULL) {
            return NULL;
        }
        if (PyDict_SetItem(self->node_to_index, node, index_obj) < 0) {
            Py_DECREF(index_obj);
            return NULL;
        }
        Py_DECREF(index_obj);
        self->nodes[index] = (NodeInfo){
            .node = node,
            .npredecessors = 0,
            .successors = NULL,
            .successors_count = 0,
            .successors_capacity = 0
        };
        Py_INCREF(node);
    } else {
        index = PyLong_AsLong(index_obj);
    }
    return &self->nodes[index];
}

/*
 * Create a new TopologicalSorter object.
 *
 * @param[in] type Pointer to the TopologicalSorter type object
 * @param[in] args Positional arguments
 * @param[in] kwds Keyword arguments
 * @return Pointer to the new TopologicalSorter object, or NULL on failure
 */
static PyObject* TopologicalSorter_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    TopologicalSorter* self;
    int initial_capacity = DEFAULT_INITIAL_CAPACITY;
    static char* kwlist[] = {"initial_capacity", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|i", kwlist, &initial_capacity)) {
        return NULL;
    }

    if (initial_capacity <= 0) {
        PyErr_SetString(PyExc_ValueError, "initial_capacity must be positive");
        return NULL;
    }

    self = (TopologicalSorter*)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->nodes = malloc(sizeof(NodeInfo) * initial_capacity);
        self->nodes_count = 0;
        self->nodes_capacity = initial_capacity;
        self->ready_nodes = malloc(sizeof(int) * initial_capacity);
        self->ready_nodes_count = 0;
        self->ready_nodes_capacity = initial_capacity;
        self->visited = calloc(BITSET_SIZE(initial_capacity), 1);
        self->done = calloc(BITSET_SIZE(initial_capacity), 1);
        self->node_to_index = PyDict_New();
        self->npassedout = 0;
        self->nfinished = 0;
        if (self->nodes == NULL || self->ready_nodes == NULL || self->visited == NULL || 
            self->done == NULL || self->node_to_index == NULL) {
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject*)self;
}

/*
 * Deallocate a TopologicalSorter object.
 *
 * @param[in] self Pointer to the TopologicalSorter object to be deallocated
 */
static void TopologicalSorter_dealloc(TopologicalSorter* self) {
    for (int i = 0; i < self->nodes_count; i++) {
        Py_XDECREF(self->nodes[i].node);
        free(self->nodes[i].successors);
    }
    free(self->nodes);
    free(self->ready_nodes);
    free(self->visited);
    free(self->done);
    Py_XDECREF(self->node_to_index);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

/*
 * Add a node and its predecessors to the graph.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] args Tuple containing the node and its predecessors
 * @return Py_None on success, NULL on failure
 */
static PyObject* TopologicalSorter_add(TopologicalSorter* self, PyObject* args) {
    PyObject* node;
    PyObject* predecessors = NULL;
    if (!PyArg_ParseTuple(args, "O|O", &node, &predecessors)) {
        return NULL;
    }

    NodeInfo* node_info = get_or_create_node(self, node);
    if (node_info == NULL) {
        return NULL;
    }

    if (predecessors != NULL) {
        if (!PyTuple_Check(predecessors)) {
            PyErr_SetString(PyExc_TypeError, "predecessors must be a tuple");
            return NULL;
        }

        Py_ssize_t num_preds = PyTuple_GET_SIZE(predecessors);
        node_info->npredecessors += num_preds;

        for (Py_ssize_t i = 0; i < num_preds; i++) {
            PyObject* pred = PyTuple_GET_ITEM(predecessors, i);
            NodeInfo* pred_info = get_or_create_node(self, pred);
            if (pred_info == NULL) {
                return NULL;
            }

            if (pred_info->successors_count >= pred_info->successors_capacity) {
                int new_capacity = pred_info->successors_capacity == 0 ? 4 : pred_info->successors_capacity * 2;
                int* new_successors = realloc(pred_info->successors, new_capacity * sizeof(int));
                if (new_successors == NULL) {
                    PyErr_NoMemory();
                    return NULL;
                }
                pred_info->successors = new_successors;
                pred_info->successors_capacity = new_capacity;
            }

            pred_info->successors[pred_info->successors_count++] = PyLong_AsLong(PyDict_GetItem(self->node_to_index, node));
        }
    }

    Py_RETURN_NONE;
}

// Stack structure for iterative DFS
typedef struct {
    int* data;
    int top;
    int capacity;
} Stack;

/*
 * Create a new Stack object.
 *
 * @param[in] capacity Initial capacity of the stack
 * @return Pointer to the new Stack object, or NULL on failure
 */
static Stack* Stack_new(int capacity) {
    Stack* stack = (Stack*)malloc(sizeof(Stack));
    stack->data = (int*)malloc(sizeof(int) * capacity);
    stack->top = -1;
    stack->capacity = capacity;
    return stack;
}

/*
 * Push a value onto the stack.
 *
 * @param[in] stack Pointer to the Stack object
 * @param[in] value Value to push onto the stack
 */
static void Stack_push(Stack* stack, int value) {
    if (stack->top == stack->capacity - 1) {
        stack->capacity *= 2;
        stack->data = (int*)realloc(stack->data, sizeof(int) * stack->capacity);
    }
    stack->data[++stack->top] = value;
}

/*
 * Pop a value from the stack.
 *
 * @param[in] stack Pointer to the Stack object
 * @return The value popped from the stack
 */
static int Stack_pop(Stack* stack) {
    return stack->data[stack->top--];
}

/*
 * Check if the stack is empty.
 *
 * @param[in] stack Pointer to the Stack object
 * @return True if the stack is empty, false otherwise
 */
static bool Stack_is_empty(Stack* stack) {
    return stack->top == -1;
}

/*
 * Free a Stack object.
 *
 * @param[in] stack Pointer to the Stack object to be freed
 */
static void Stack_free(Stack* stack) {
    free(stack->data);
    free(stack);
}

/*
 * Perform iterative DFS to detect cycles and prepare the graph.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @return 0 if no cycle is detected, 1 if a cycle is detected, -1 on memory allocation failure
 */
static int dfs_iterative(TopologicalSorter* self) {
    Stack* stack = Stack_new(self->nodes_count);
    unsigned char* on_stack = calloc(BITSET_SIZE(self->nodes_capacity), 1);

    for (int start = 0; start < self->nodes_count; start++) {
        if (!BITSET_TEST(self->visited, start)) {
            Stack_push(stack, start);
            
            while (!Stack_is_empty(stack)) {
                int node = Stack_pop(stack);

                if (!BITSET_TEST(self->visited, node)) {
                    BITSET_SET(self->visited, node);
                    BITSET_SET(on_stack, node);
                    Stack_push(stack, node);

                    NodeInfo* node_info = &self->nodes[node];
                    for (int i = 0; i < node_info->successors_count; i++) { // Process successors
                        int successor = node_info->successors[i];
                        if (!BITSET_TEST(self->visited, successor)) { // Not visited
                            Stack_push(stack, successor);
                        } else if (BITSET_TEST(on_stack, successor)) { // On stack
                            Stack_free(stack);
                            free(on_stack);
                            return 1; // Cycle detected
                        }
                    }
                } else if (BITSET_TEST(on_stack, node)) { // On stack
                    BITSET_CLEAR(on_stack, node);
                    BITSET_SET(self->done, node);
                    if (self->nodes[node].npredecessors == 0) { // No predecessors
                        if (self->ready_nodes_count >= self->ready_nodes_capacity) {
                            if (expand_capacity((void**)&self->ready_nodes, &self->ready_nodes_capacity, sizeof(int)) < 0) { // Expand capacity
                                Stack_free(stack);
                                free(on_stack);
                                return -1;
                            }
                        }
                        self->ready_nodes[self->ready_nodes_count++] = node; // Add to ready nodes
                    }
                }
            }
        }
    }

    Stack_free(stack);
    free(on_stack);
    return 0;
}

/*
 * Prepare the graph for processing.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] ignored Unused argument
 * @return Py_None on success, NULL on failure
 */
static PyObject* TopologicalSorter_prepare(TopologicalSorter* self, PyObject* Py_UNUSED(ignored)) {
    memset(self->visited, 0, BITSET_SIZE(self->nodes_capacity)); // Reset visited
    memset(self->done, 0, BITSET_SIZE(self->nodes_capacity)); // Reset done
    self->ready_nodes_count = 0;
    self->npassedout = 0;
    self->nfinished = 0;
    
    if (dfs_iterative(self)) { // Cycle detected
        PyErr_SetString(PyExc_ValueError, "Cycle detected in graph");
        return NULL;
    }
    
    Py_RETURN_NONE;
}

/*
 * Get the next set of ready nodes.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] ignored Unused argument
 * @return List of ready nodes, or NULL on failure
 */
static PyObject* TopologicalSorter_get_ready(TopologicalSorter* self, PyObject* Py_UNUSED(ignored)) {
    PyObject* ready_list = PyList_New(self->ready_nodes_count);
    if (ready_list == NULL) {
        return NULL;
    }

    for (int i = 0; i < self->ready_nodes_count; i++) {
        int node_index = self->ready_nodes[i];
        PyObject* node = self->nodes[node_index].node;
        Py_INCREF(node);
        PyList_SET_ITEM(ready_list, i, node);
    }

    self->npassedout += self->ready_nodes_count;
    self->ready_nodes_count = 0;

    return ready_list;
}

/*
 * Mark a node as done and update the graph.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] args Tuple containing the node to be marked as done
 * @return Py_None on success, NULL on failure
 */
static PyObject* TopologicalSorter_done(TopologicalSorter* self, PyObject* args) {
    PyObject* node;
    if (!PyArg_ParseTuple(args, "O", &node)) {
        return NULL;
    }

    PyObject* index_obj = PyDict_GetItem(self->node_to_index, node);
    if (index_obj == NULL) {
        PyErr_SetString(PyExc_ValueError, "Node not in graph");
        return NULL;
    }
    int index = PyLong_AsLong(index_obj);
    NodeInfo* node_info = &self->nodes[index];

    if (node_info->npredecessors != 0) {
        PyErr_SetString(PyExc_ValueError, "Node was not ready");
        return NULL;
    }

    node_info->npredecessors = -1;  // Mark as done
    self->nfinished++;

    for (int i = 0; i < node_info->successors_count; i++) {
        int successor = node_info->successors[i];
        NodeInfo* successor_info = &self->nodes[successor];
        successor_info->npredecessors--;
        if (successor_info->npredecessors == 0) {
            self->ready_nodes[self->ready_nodes_count++] = successor;
        }
    }

    Py_RETURN_NONE;
}

/*
 * Check if the sorter is still active.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] ignored Unused argument
 * @return Py_True if the sorter is still active, Py_False otherwise
 */
static PyObject* TopologicalSorter_is_active(TopologicalSorter* self, PyObject* Py_UNUSED(ignored)) {
    if (self->nfinished < self->npassedout || self->ready_nodes_count > 0) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

/*
 * Return a static ordering of the graph.
 *
 * @param[in] self Pointer to the TopologicalSorter object
 * @param[in] ignored Unused argument
 * @return List of nodes in static order, or NULL on failure
 */
static PyObject* TopologicalSorter_static_order(TopologicalSorter* self, PyObject* Py_UNUSED(ignored)) {
    if (TopologicalSorter_prepare(self, NULL) == NULL) {
        return NULL;  // Error in prepare, it will have set the exception
    }

    PyObject* result = PyList_New(self->nodes_count);
    if (result == NULL) {
        return NULL;
    }

    int index = 0;
    while (self->ready_nodes_count > 0 || self->nfinished < self->nodes_count) {
        PyObject* ready = TopologicalSorter_get_ready(self, NULL);
        if (ready == NULL) {
            Py_DECREF(result);
            return NULL;
        }

        Py_ssize_t ready_count = PyList_GET_SIZE(ready);
        for (Py_ssize_t i = 0; i < ready_count; i++) {
            PyObject* node = PyList_GET_ITEM(ready, i);
            Py_INCREF(node);
            PyList_SET_ITEM(result, index++, node);
            if (TopologicalSorter_done(self, Py_BuildValue("(O)", node)) == NULL) {
                Py_DECREF(ready);
                Py_DECREF(result);
                return NULL;
            }
        }
        Py_DECREF(ready);
    }

    if (index != self->nodes_count) {
        PyErr_SetString(PyExc_ValueError, "Cycle detected in graph");
        Py_DECREF(result);
        return NULL;
    }

    return result;
}

// Method definitions for the TopologicalSorter type
static PyMethodDef TopologicalSorter_methods[] = {
    {"add", (PyCFunction)TopologicalSorter_add, METH_VARARGS, "Add a node to the graph"},
    {"prepare", (PyCFunction)TopologicalSorter_prepare, METH_NOARGS, "Prepare the graph for processing"},
    {"get_ready", (PyCFunction)TopologicalSorter_get_ready, METH_NOARGS, "Get ready nodes"},
    {"done", (PyCFunction)TopologicalSorter_done, METH_VARARGS, "Mark a node as done"},
    {"is_active", (PyCFunction)TopologicalSorter_is_active, METH_NOARGS, "Check if the sorter is still active"},
    {"static_order", (PyCFunction)TopologicalSorter_static_order, METH_NOARGS, "Return a static ordering of the graph"},
    {NULL}  /* Sentinel */
};

// TopologicalSorter type definition
static PyTypeObject TopologicalSorterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "cgraphlib.TopologicalSorter",
    .tp_doc = "TopologicalSorter object",
    .tp_basicsize = sizeof(TopologicalSorter),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = TopologicalSorter_new,
    .tp_dealloc = (destructor)TopologicalSorter_dealloc,
    .tp_methods = TopologicalSorter_methods,
};

// Module definition
static PyModuleDef cgraphlibmodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "cgraphlib",
    .m_doc = "C implementation of TopologicalSorter",
    .m_size = -1,
};

/*
 * Module initialization function.
 *
 * @return The module object on success, or NULL on failure
 */
PyMODINIT_FUNC PyInit_cgraphlib(void) {
    PyObject* m;
    if (PyType_Ready(&TopologicalSorterType) < 0)
        return NULL;

    m = PyModule_Create(&cgraphlibmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&TopologicalSorterType);
    if (PyModule_AddObject(m, "TopologicalSorter", (PyObject*)&TopologicalSorterType) < 0) {
        Py_DECREF(&TopologicalSorterType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}