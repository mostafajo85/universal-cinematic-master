import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'skills' / 'ucm'

class PackageTests(unittest.TestCase):
    def test_required_files(self):
        for name in ['SKILL.md', 'resources/MASTER.md', 'release_pin.json', 'scripts/ucm.py', 'scripts/vendor_p6/run_validator.py']:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_parse_python(self):
        for file in ROOT.rglob('*.py'):
            ast.parse(file.read_text(encoding='utf8'), filename=str(file))

    def test_no_kb_payloads(self):
        self.assertEqual(sorted(x.name for x in (ROOT / 'knowledge_base').glob('*')), ['README.txt'])

if __name__ == '__main__':
    unittest.main()
