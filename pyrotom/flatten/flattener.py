import copy
import _ast
import collections.abc
import inspect
import ast


BODY_FIELDS = {'body', 'orelse', 'finalbody'}

SINGLETON_TYPES = (
    _ast.Name, _ast.Constant, _ast.Num,
    _ast.Str, _ast.Bytes, _ast.Ellipsis,
    _ast.Load, _ast.Store
)


def is_ast_node_type(node):
    return node is not None and type(node).__module__ == '_ast'


class Flattener(object):
    def __init__(self):
        self.temp_id_counter = 0

    def flatten(self, node, stmts=None, direct_assign=False):
        """This method extracts some function calls into assigments from `node` and flattens assignments with multiple targets.

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
        visitor = getattr(self, f'visit_{node.__class__.__name__}', self.default_visit)
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


'''
    visit_Module = flatten_body
    visit_Interactive = flatten_body
    visit_Sutie = flatten_body

    def visit_If(self, node):
        node.test = self.flatten_stmt(node.test)
        return self.flatten_body(node)

    visit_While = visit_if

    def visit_For(self, node):
        node.iter = self.flatten_stmt(node.iter)
        return self.flatten_body(node)

    @after_copied
    def visit_With(self, node):
        for item in node.items:
            item.context_expr = self.flatten_stmt(item.context_expr)
        return self.flatten_body(node)

    @after_copied
    def visit_ClassDef(self, node):
        node.bases = list(map(self.flatten_stmt, node.bases))
        node.keywords = list(map(copy.copy, node.keywords))
        for kw in node.keywords:
            kw.value = self.flatten_stmt(kw.value)
        node.decorator_list = list(map(self.flatten_stmt, node.decorator_list))
        return self.flatten_body(node)

    @after_copied
    def visit_FunctionDef(self, node):
        node.args = copy.copy(node.args)
        node.args.defaults = list(map(self.flatten_stmt, node.args.defaults))
        node.args.kw_defaults = list(map(self.flatten_stmt, node.args.kw_defaults))
        node.decorator_list = list(map(self.flatten_stmt, node.decorator_list))
        return self.flatten_body(node)


    def visit_Pass(self, node):
        self.insert_stmt(node)

    visit_Break = visit_Pass
    visit_Continue = visit_Pass
    visit_Import = visit_Pass
    visit_ImportFrom = visit_Pass
    visit_Global = visit_Pass
    visit_Nonlocal = visit_Pass
    visit_Delete = visit_Pass

    def visit_Delete(self, node):
        raise NotImplemented

    @after_copied
    def visit_effective(self, node):
        for field in node._fields:
            val = getattr(node, field)
            if not self.is_ast_node_type(val):
                continue
            setattr(node, field, self.flatten_stmt(val))
        self.insert_stmt(node)

    visit_Return = visit_effective
    visit_Raise = visit_effective
    visit_Assert = visit_effective

    @after_copied
    def visit_all_fields(self, node):
        for field in node._fields:
            val = getattr(node, field)
            if not self.is_ast_node_type(val):
                continue
            setattr(node, field, self.flatten_stmt(val))
        return node

    visit_Slice = visit_all_fields
    visit_Index = visit_all_fields
    visit_Starred = visit_all_fields
    visit_JoinedStr = visit_all_fields
    visit_FormattedValue = visit_all_fields
    visit_Yield = visit_all_fields
    visit_YieldFrom = visit_all_fields
    visit_IfExp = visit_all_fields

    @after_copied
    def visit_magic_call(self, node):
        for field in node._fields:
            val = getattr(node, field)
            if not self.is_ast_node_type(val):
                continue
            setattr(node, field, self.assignize(val))
        return self.new_assign(node)

    visit_Subscript = visit_magic_call
    visit_Attribute = visit_magic_call

    @after_copied
    def visit_ExtSlice(self, node):
        node.dims = list(map(self.flatten_stmt, node.dims))
        return node

    def assignize_stmt(self, node):
        """This method transforms `node`, except `_ast.Name`, into an assignment and returns the target."""
        method_name = f'insert_{type(node).__name__}'
        if hasattr(self, method_name):
            return getattr(self, method_name)(node)
        node = self.flatten_stmt(node)
        if node is None:
            return None
        if isinstance(node, _ast.Name):
            return node
        return self.new_assign(node)

    @after_copied
    def flatten_body(self, node):
        for field in ('body', 'orelse', 'finalbody'):
            val = getattr(node, field)
            self.push_stmts(val)
            for stmt in val:
                self.assignize_stmt(stmt)
            self.pop_stmts()
        if self.current_stmts:
            self.insert_stmt(node)
        else:
            # root
            return node

    visit_Module = flatten_body
    visit_Interactive = flatten_body
    visit_Sutie = flatten_body

    @after_copied
    def visit_If(self, node):
        node.test = self.flatten_stmt(node.test)
        return self.flatten_body(node)

    visit_While = visit_if

    @after_copied
    def visit_For(self, node):
        node.iter = self.flatten_stmt(node.iter)
        return self.flatten_body(node)

    @after_copied
    def visit_With(self, node):
        for item in node.items:
            item.context_expr = self.flatten_stmt(item.context_expr)
        return self.flatten_body(node)

    @after_copied
    def visit_ClassDef(self, node):
        node.bases = list(map(self.flatten_stmt, node.bases))
        node.keywords = list(map(copy.copy, node.keywords))
        for kw in node.keywords:
            kw.value = self.flatten_stmt(kw.value)
        node.decorator_list = list(map(self.flatten_stmt, node.decorator_list))
        return self.flatten_body(node)

    @after_copied
    def visit_FunctionDef(self, node):
        node.args = copy.copy(node.args)
        node.args.defaults = list(map(self.flatten_stmt, node.args.defaults))
        node.args.kw_defaults = list(map(self.flatten_stmt, node.args.kw_defaults))
        node.decorator_list = list(map(self.flatten_stmt, node.decorator_list))
        return self.flatten_body(node)

    def visit_singleton(self, node):
        return node

    visit_Name = visit_singleton
    visit_Constant = visit_singleton
    visit_Str = visit_singleton
    visit_Bytes = visit_singleton
    visit_Num = visit_singleton
    visit_Ellipsis = visit_singleton
    visit_Lambda = visit_singleton

    def visit_Expr(self, node):
        return self.flatten(node.value)

    @after_copied
    def visit_iteratable(self, node):
        node.elts = list(map(self.flatten_stmt, node.elts))
        return node

    visit_Tuple = visit_iteratable
    visit_List = visit_iteratable
    visit_Set = visit_iteratable

    @after_copied
    def visit_Dict(self, node):
        node.keys = list(map(self.flatten_stmt, node.keys))
        node.values = list(map(self.flatten_stmt, node.values))
        return node
'''
