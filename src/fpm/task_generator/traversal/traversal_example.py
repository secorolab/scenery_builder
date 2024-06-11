import rdflib

import traversal

EX = rdflib.Namespace("http://example.org/")

g = rdflib.Graph()
g.bind("ex", EX)
g.add((EX.a, EX.p1, EX.b))
g.add((EX.b, EX.p2, EX.c))
g.add((EX.c, EX.p2, EX.d))
g.add((EX.b, EX.p3, EX.e))
g.add((EX.e, EX.p3, EX.f))
g.add((EX.h, EX.p4, EX.e))

print(type(EX.a))
def prefixed(g, node):
    return node.n3(g.namespace_manager)

# Where the traverse start (my point that I want to transform, or the world origin [direction])
root = EX.a
print(type(root), root)
# specify the predicates (properties) that the algorithm is allow to follow (with-respect-on, as-seen-by, of)
pred_filter = traversal.filter_by_predicates([EX.p1, EX.p2, EX.p3, EX.p4])
# Type of traversal
open_set = traversal.BreadthFirst
#open_set = traversal.DepthFirst

# Returns the nodes that are being visited
# No termination criteria, extension that I have to perform 
# Also implement the path finding/cycle free conection
# Idea: calculate from the root the transformations to all points, and then set up a lookup table
t_n = traversal.traverse_nodes(open_set, g, root, pred_filter)
for node in t_n:
    print(prefixed(g, node))
print()

# Same traversal but returns node and parent
t_np = traversal.traverse_nodes_with_parent(open_set, g, root, pred_filter)
for node, parent in ((node, parent) for (node, parent) in t_np if parent):
    print(prefixed(g, node), "<--", prefixed(g, parent))
print()

# "Global" traversal (generator)
# Configuration: bfs/dfs/..., edges to follow and their type (in/out/both), ...
# Return values: current, parent, via edge, edge type (in/out)
t_nep = traversal.traverse_nodes_with_parent_and_edges(open_set, g, root, pred_filter)
for node, edges, parent in ((node, edges, parent) for (node, edges, parent) in t_nep if parent):
    # "Local" traversal (coroutine?)
    for (e, e_dir) in edges:
        if e_dir == traversal.Direction.OUT: 
            print(prefixed(g, node), "--", prefixed(g, e), "-->", prefixed(g, parent))
        else:
            print(prefixed(g, node), "<--", prefixed(g, e), "--", prefixed(g, parent))
print()