import unittest

from pyrotom.utils import TempCodeManager


def abs_decorator(func):
    def wrapped(*args, **kwargs):
        ret = func(*args, **kwargs)
        return abs(ret)
    return wrapped


class TestTempCodeManager(unittest.TestCase):
    def setUp(self):
        self.manager = TempCodeManager()

    def test_run_code(self):
        init_globals = {
            'decorator': abs_decorator
        }
        name = 'absolute_difference'
        code = '''
@decorator
def diff(a, b):
    return a - b
'''

        module = self.manager.run_code(name, code, init_globals)

        self.assertIn('diff', module)
        self.assertEqual(module['diff'](391, 1096), abs(391 - 1096))


if __name__ == '__main__':
    unittest.main()
