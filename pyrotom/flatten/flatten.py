import inspect

from .flattener import Flattener
from .. import utils


def fetch_func_name(node):
    if isinstance(node, _ast.FunctionDef):
        return node.name
    if hasattr(node, 'body'):
        for i in node.body:
            name = fetch_func_name(i)
            if name:
                return name
    return ''


class Flatten(object):
    def __init__(self, tmp_manager=None, flattener=None, scope_pred=None):
        self.tmp_manager = tmp_manager or utils.TempCodeManager()
        self.flattener = flattener or Flattener()
        self.scope_pred = scope_pred or lambda *_, **__: True

    def flatten_callable(self, func):
        code = utils.remove_indent(inspect.getsource(func))
        flattened = self.flattener.flatten(code)
        func_name = fetch_func_name(flattened)
        code_name = f'{func_name}_flattened'
        glb = func.__globals__.copy()
        module = self.tmp_manager.run_code(
            flattened, code_name, init_globals=glb)
        return module[func_name]
