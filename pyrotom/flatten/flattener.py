import _ast


def is_ast_node_type(node):
    return node is not None and val.__module__ == '_ast'


class Flattener(object):
    def __init__(self):
        self.statements_stack = []
        self.temp_id_counter = 0

    def push_statements(self, statements):
        self.statements_stack.append(statements)

    def pop_statements(self):
        return self.statements_stack.pop()

    @property
    def current_statements(self):
        return self.statements_stack[-1]

    def insert_statement(self, statement):
        self.current_statements.append(statement)

    def flatten(self, node):
        assert is_ast_node_type(node)
        visitor = getattr(self, f'visit_{node.__class__.__name__}')
        return visitor(node)

    def new_assign(self, node):
        for field in node._fields:
            val = getattr(node, field)
            if not self.is_ast_node_type(val):
                continue
            setattr(node, field, self.flatten(val))
        new_id = self.new_temp_id()
        self.insert_statement(_ast.Assign([new_id], node))
        return new_id

    def assignize(self, node):
        if isinstance(node, _ast.AnnAssign) and isinstance(node.target, _ast.Name):
            node.value = self.flatten(node.value)
            insert_statement(node)
            return node.target
        if isinstance(node, _ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], _ast.Name):
            node.value = self.flatten(node.value)
            insert_statement(node)
            return node.targets[0]
        if isinstance(node, (_ast.Assign, _ast.AnnAssign)):
            node.value = self.assignize(node.value)
            insert_statement(node)
            return node.value
    # TODO: distinct from `flatten`

    def visit_body(self, node):
        for field in ('body', 'orelse'):
            val = getattr(node, field)
            self.push_statements(val)
            for stmt in val:
                self.assignize(stmt)
            self.pop_statements()
        return node

    visit_Module = visit_body
    # TODO: if, for, ...

    def new_temp_id(self):
        self.temp_id_counter += 1
        return _ast.Name(f'__flat_{self.temp_id_counter}')

    def visit_singleton(self, node):
        return node

    visit_Name = visit_singleton
    visit_Constant = visit_singleton
    visit_JoinedStr = visit_singleton
    visit_Str = visit_singleton
    visit_Bytes = visit_singleton
    visit_Num = visit_singleton

    def visit_iteratable(self, node):
        # TODO: Tuple, ...
        pass
