"""Python 3.7 guard for test and production source.

The text-I/O heuristic checks direct open/read_text/write_text calls, assumes
literal modes (or omitted modes) are text, and exempts literal binary modes.
It does not resolve aliases, wrappers, or dynamically computed modes. The mock
check tracks simple assignments and loop/comprehension targets from call_args
or call_args_list; it does not resolve aliases through helper functions.
"""
import ast
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def parse_source(path):
    source = path.read_text(encoding='utf-8')
    if sys.version_info >= (3, 8):
        return ast.parse(source, filename=str(path), feature_version=(3, 7))
    return ast.parse(source, filename=str(path))


class PortabilityTests(unittest.TestCase):
    def test_python37_syntax(self):
        failures = []
        paths = list((ROOT / 'tests').glob('*.py'))
        paths.extend((ROOT / 'src').rglob('*.py'))
        for path in sorted(paths):
            try:
                parse_source(path)
            except SyntaxError as error:
                failures.append('{}:{}: {}'.format(path.name, error.lineno, error.msg))
        self.assertEqual(failures, [])

    def test_mock_call_tuple_access(self):
        failures = []
        for path in sorted((ROOT / 'tests').glob('*.py')):
            tree = parse_source(path)
            bound = set()
            for node in ast.walk(tree):
                value = None
                targets = []
                if isinstance(node, (ast.For, ast.comprehension)):
                    value, targets = node.iter, [node.target]
                elif isinstance(node, ast.Assign):
                    value, targets = node.value, node.targets
                if isinstance(value, ast.Attribute) and value.attr in ('call_args', 'call_args_list'):
                    for target in targets:
                        if isinstance(target, ast.Name):
                            bound.add(target.id)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in ('args', 'kwargs'):
                    value = node.value
                    if (isinstance(value, ast.Name) and value.id in bound) or (
                            isinstance(value, ast.Attribute) and value.attr == 'call_args'):
                        failures.append('{}:{}: .{}'.format(path.name, node.lineno, node.attr))
        self.assertEqual(failures, [])

    def test_explicit_text_encoding(self):
        failures = []
        for path in sorted((ROOT / 'tests').glob('*.py')):
            for node in ast.walk(parse_source(path)):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                name = function.attr if isinstance(function, ast.Attribute) else (
                    function.id if isinstance(function, ast.Name) else None)
                if name not in ('open', 'read_text', 'write_text'):
                    continue
                if any(keyword.arg == 'encoding' for keyword in node.keywords):
                    continue
                if name == 'open':
                    mode = node.args[1] if len(node.args) > 1 else None
                    for keyword in node.keywords:
                        if keyword.arg == 'mode':
                            mode = keyword.value
                    if isinstance(mode, ast.Str) and 'b' in mode.s:
                        continue
                failures.append('{}:{}: {}'.format(path.name, node.lineno, name))
        self.assertEqual(failures, [])


if __name__ == '__main__':
    unittest.main()
