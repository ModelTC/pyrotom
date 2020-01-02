import copy
import _ast
import collections.abc
import inspect
import ast

from ..utils import is_ast_node_type


BODY_FIELDS = {'body', 'orelse', 'finalbody'}

SINGLETON_TYPES = (
    _ast.Name, _ast.Constant, _ast.Num,
    _ast.Str, _ast.Bytes, _ast.Ellipsis,
    _ast.Load, _ast.Store
)


class Flattener(object):
    def __init__(self):
        self.temp_id_counter = 0

    def flatten(self, node, stmts=None, direct_assign=False):
        """Extracts function calls into assigments from `node`
        and flattens assignments with multiple targets.

        The nodes of `_ast.Call` in AST will be flattened into assignments.

        And their arguments will also be extracted
        and changed to corresponded nodes of `_ast.Name`.

        Calls of some magic methods will be flattened in the same way with `_ast.Call`,
        such as `__lt__`, `__add__`, `__getitem__`, `__getattr__`.

        Note that the nodes of `_ast.AugAssign` will be changed into nodes of `_ast.Assign`.
        """
        if isinstance(node, collections.abc.Callable):
            node = inspect.getsource(node)
        if isinstance(node, str):
            node = ast.parse(node)
        assert is_ast_node_type(node)
        if isinstance(node, (_ast.Module, _ast.Interactive)):
            node = copy.deepcopy(node)
        visit_method = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, visit_method, self.default_visit)
        return visitor(node, stmts, direct_assign)

    def default_visit(self, node, stmts, direct_assign):
        for field in node._fields:
            if field in BODY_FIELDS:
                continue
            child = getattr(node, field)
            if is_ast_node_type(child):
                setattr(node, field, self.flatten(child, stmts))
            elif child and isinstance(child, collections.abc.Iterable) \
                    and is_ast_node_type(next(iter(child))):
                setattr(node, field, type(child)(map(
                    lambda x: self.flatten(x, stmts), child)))

        for field in BODY_FIELDS:
            if not hasattr(node, field):
                continue
            old_stmts = getattr(node, field)
            new_stmts = []
            setattr(node, field, new_stmts)
            for stmt in old_stmts:
                new_stmts.append(self.flatten(stmt, new_stmts))

        return node

    def new_temp_id(self):
        self.temp_id_counter += 1
        return _ast.Name(id=f'__flat_tmp_{self.temp_id_counter}', ctx=None)

    def new_assign(self, node, stmts):
        node = self.flatten(node, stmts, True)
        if isinstance(node, SINGLETON_TYPES):
            return node
        new_id = self.new_temp_id()
        stmts.append(_ast.Assign([new_id], node))
        return new_id

    def visit_Call(self, node, stmts, direct_assign):
        node.func = self.new_assign(node.func, stmts)
        for i in range(len(node.args)):
            if isinstance(node.args[i], _ast.Starred):
                node.args[i].value = self.new_assign(node.args[i].value, stmts)
            else:
                node.args[i] = self.new_assign(node.args[i], stmts)
        for kw in node.keywords:
            kw.value = self.new_assign(kw.value, stmts)
        if direct_assign:
            return node
        else:
            return self.new_assign(node, stmts)

    def visit_BinOp(self, node, stmts, direct_assign):
        node.left = self.new_assign(node.left, stmts)
        node.right = self.new_assign(node.right, stmts)
        if direct_assign:
            return node
        else:
            return self.new_assign(node, stmts)

    def visit_UnaryOp(self, node, stmts, direct_assign):
        node.operand = self.new_assign(node.operand, stmts)
        if direct_assign:
            return node
        else:
            return self.new_assign(node, stmts)

    def visit_Attribute(self, node, stmts, direct_assign):
        node.value = self.new_assign(node.value, stmts)
        if direct_assign:
            return node
        else:
            return self.new_assign(node, stmts)

    def visit_Subscript(self, node, stmts, direct_assign):
        node.value = self.new_assign(node.value, stmts)
        node.slice = self.flatten(node.slice, stmts, False)
        if direct_assign:
            return node
        else:
            return self.new_assign(node, stmts)

    def visit_Assign(self, node, stmts, direct_assign):
        assert not direct_assign
        node.value = self.flatten(node.value, stmts, True)

        if len(node.targets) == 1 and isinstance(node.targets[0], _ast.Name):
            return node

        cur_id = None
        for target in node.targets:
            if isinstance(target, _ast.Name):
                cur_id = target
                break
        if cur_id is None:
            cur_id = self.new_temp_id()
            node.targets.append(cur_id)

        stmts.append(_ast.Assign(targets=[cur_id], value=node.value))

        node.value = cur_id
        node.targets.remove(cur_id)
        return node

    def visit_AnnAssign(self, node, stmts, direct_assign):
        assert not direct_assign
        node.value = self.flatten(node.value, stmts, True)
        if isinstance(node.target, _ast.Name):
            return _ast.Assign(targets=[node.target], value=node.value)
        cur_id = self.new_temp_id()
        stmts.append(_ast.Assign(targets[cur_id], value=node.value))
        return _ast.Assign(targets[node.target], value=cur_id)

    def visit_AugAssign(self, node, stmts, direct_assign):
        assert not direct_assign
        value = self.flatten(
            _ast.BinOp(
                left=node.target,
                right=node.value,
                op=node.op
            ),
            stmts, True
        )
        if isinstance(node.target, _ast.Name):
            return _ast.Assign(targets=[node.target], value=value)
        cur_id = self.new_temp_id()
        stmts.append(_ast.Assign(targets=[cur_id], value=value))
        return _ast.Assign(targets=[node.target], value=cur_id)
