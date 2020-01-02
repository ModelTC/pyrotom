import pathlib
import tempfile
import contextlib
import runpy
import astor

from .ast_node import is_ast_node_type
from ..settings import default_settings


class TempCodeManager(object):
    """Manager of temporary files to execute modified python code."""

    def __init__(self, root=None, do_close=True):
        if root is None:
            root = default_settings.get('temp_code_default_root', None)

        self.root = root

        if self.root:
            root = pathlib.Path(root)
            root.mkdir(parents=True, exist_ok=True)

        self._do_close = do_close and bool(self.root)

    @contextlib.contextmanager
    def get_file(self, name):
        """Gets a temporary writable file opened in bytes."""
        if self.root:
            filename = self.root / f'{name}.py'
            f = open(filename, 'wb')

            yield filename, f

            if self._do_close:
                f.close()
        else:
            f = tempfile.NamedTemporaryFile()

            yield f.name, f

    def run_code(self, code, name, init_globals=None):
        """Runs the code and returns the module."""
        if is_ast_node_type(code):
            code = astor.to_source(code)
        if isinstance(code, str):
            code = code.encode('utf8')

        with self.get_file(name) as (filename, f):
            f.write(code)
            f.flush()
            module = runpy.run_path(filename, init_globals)

        return module
