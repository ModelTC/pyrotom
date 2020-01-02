def is_ast_node_type(node):
    return node is not None and type(node).__module__ == '_ast'
