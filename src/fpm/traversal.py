import enum
import collections
import itertools
import rdflib.plugins.sparql

class Direction(enum.Enum):
    IN = 1
    OUT = 2
    IN_OUT = 3

def __inout_neighbours(graph, node):
    # All out-going predicates
    p1 = ((o, p, Direction.OUT) for p, o in graph.predicate_objects(node))
    # All incoming predicates
    p2 = ((s, p, Direction.IN) for s, p in graph.subject_predicates(node))
    # Compose both iterables
    return itertools.chain(p1, p2)

def __inout_predicates(graph, node1, node2):
    # All predicates node1->node2
    p1 = ((p, Direction.OUT) for p in graph.predicates(subject=node1, object=node2))
    # All predicates node1<-node2
    p2 = ((p, Direction.IN) for p in graph.predicates(subject=node2, object=node1))
    # Compose both iterables
    return itertools.chain(p1, p2)

def filter_by_predicates(predicates):
    def exec(tup):
        child, edge, edge_direction = tup
        return edge in predicates
    return exec

def filter_by_predicates_direction(predicate_direction):
    def exec(tup):
        child, edge, edge_direction = tup
        return (edge, edge_direction) in predicate_direction
    return exec

def filter_by_direction(direction):
    def exec(tup):
        child, edge, edge_direction = tup
        return (direction == Direction.IN_OUT) or (edge_direction == direction)
    return exec

class BreadthFirst:
    def __init__(self):
        self.queue = collections.deque()

    def is_empty(self):
        return len(self.queue) <= 0

    def insert(self, node):
        self.queue.append(node)

    def remove(self):
        return self.queue.popleft()

class DepthFirst:
    def __init__(self):
        self.stack = []

    def is_empty(self):
        return len(self.stack) <= 0

    def insert(self, node):
        self.stack.append(node)

    def remove(self):
        return self.stack.pop()

def traverse_nodes(open_set_ds, graph, root, neighbour_filter=None):
    visited = {}
    open_set = open_set_ds()
    open_set.insert(root)

    while not open_set.is_empty():
        node = open_set.remove()
        if node not in visited:
            yield node
            visited[node] = True

            neigh = filter(neighbour_filter, __inout_neighbours(graph, node))
            for (child, edge, edge_direction) in neigh:
                open_set.insert(child)

def traverse_nodes_with_parent(open_set_ds, graph, root, neighbour_filter=None):
    visited = {}
    open_set = open_set_ds()
    open_set.insert(root)
    #parent = {root: None}
    parent = {root: root}

    while not open_set.is_empty():
        node = open_set.remove()
        if node not in visited:
            yield (node, parent[node])
            visited[node] = True

            neigh = filter(neighbour_filter, __inout_neighbours(graph, node))
            for (child, _, _) in neigh:
                parent[child] = node
                open_set.insert(child)

def traverse_nodes_with_parent_sparql(open_set_ds, graph, root, neighbour_selector):
    visited = {}
    open_set = open_set_ds()
    open_set.insert(root)
    parent = {root: root} # {root: None}
    neighbours = rdflib.plugins.sparql.prepareQuery(neighbour_selector)

    while not open_set.is_empty():
        node = open_set.remove()
        if node not in visited:
            yield (node, parent[node])
            visited[node] = True

            neigh = list(graph.query(neighbours, initBindings={"root": root, "node": node}))
            for (child, selected_parent) in neigh:
                parent[child] = selected_parent
                open_set.insert(child)


def traverse_nodes_with_parent_and_edges(open_set_ds, graph, root, neighbour_filter=None):
    # There could be multiple edges between two nodes (want to visit all _edges!)
    # Parent then is related to the order of discovery/traversal
    # For example, what is _the_ parent in the following setup?
    #   (a, e1, b)
    #   (b, e2, a)
    visited = {}
    open_set = open_set_ds()
    #open_set.insert((root, None)) # (node, parent)
    open_set.insert((root, root)) # (node, parent)

    while not open_set.is_empty():
        node, parent = open_set.remove()
        if (node, parent) not in visited:
            # Find all (in & out) predicates between node and its parent
            pred = __inout_predicates(graph, node, parent)
            yield (node, pred, parent)

            visited[(node, parent)] = True
            visited[(parent, node)] = True # TODO: do want to have this? configuration option?

            # More efficient: not filter, but only select requested
            neigh = filter(neighbour_filter, __inout_neighbours(graph, node))
            for (child, _, _) in neigh:
                open_set.insert((child, node))
