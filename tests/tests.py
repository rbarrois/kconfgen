import io
import os.path
import pathlib
import tempfile
import typing as T
import subprocess
import unittest

import kconfgen


TESTS_ROOT = os.path.abspath(os.path.dirname(__file__))
KCONF_ROOT = os.path.join(TESTS_ROOT, 'kconf')


class KConfGenTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self._workdir = tempfile.TemporaryDirectory()
        self.workdir = pathlib.Path(self._workdir.name)
        self.kconf = kconfgen.load_kconf(
            kernel_sources=KCONF_ROOT,
            arch='x86',
        )

    def tearDown(self):
        self._workdir.cleanup()
        super().tearDown()


class MergeTests(KConfGenTestCase):
    def assert_merge_result(self,
            sources: T.List[T.Text],
            expected: T.Text,
            ) -> None:

        files = {
            self.workdir / "defconfig_{}".format(i): contents
            for i, contents in enumerate(sources)
        }
        for path, contents in files.items():
            with open(path, 'w', encoding='utf-8') as f:
                f.write(contents)

        result = io.StringIO()
        stats = kconfgen.defconfig_merge(
            kconf=self.kconf,
            fail_on_unknown=True,
            sources=sorted(files.keys()),
            output=result,
        )

        self.assertEqual(expected, result.getvalue())

    def test_empty(self):
        self.assert_merge_result(
            sources=[],
            expected='',
        )

    def test_minimal(self):
        self.assert_merge_result(
            sources=[
                """CONFIG_SIDE_FRIES=y
CONFIG_STEAK_BEEF=y
CONFIG_CHEDDAR=y""",
            ],
            expected='',
        )

    def test_duplicate(self):
        self.assert_merge_result(
            sources=[
                "CONFIG_SIDE_SALAD=y\n",
                "CONFIG_SIDE_SALAD=y\nCONFIG_BREAD_POTATO=y\n",
                "CONFIG_BREAD_POTATO=y\n",
            ],
            expected="CONFIG_SIDE_SALAD=y\nCONFIG_BREAD_POTATO=y\n",
        )

    def test_cli(self):
        with open(self.workdir / 'defconfig_extras', 'w', encoding='utf-8') as f:
            f.write("CONFIG_EXTRA_CHEDDAR=y\n")
        with open(self.workdir / 'defconfig', 'w', encoding='utf-8') as f:
            f.write("CONFIG_SIDE_SALAD=y\n")

        subprocess.check_call([
            'python', '-m', 'kconfgen', 'merge',
            '--kernel-source', KCONF_ROOT,
            '--arch', 'x86',
            '--fail-on-unknown',
            self.workdir / 'defconfig_extras',
            self.workdir / 'defconfig',
            '--output', self.workdir / 'defconfig_merged',
        ])
        with open(self.workdir / 'defconfig_merged', 'r') as f:
            generated = ''.join(f)
        self.assertEqual("CONFIG_SIDE_SALAD=y\nCONFIG_EXTRA_CHEDDAR=y\n", generated)


class SplitTests(KConfGenTestCase):

    def assert_category_expansion(self,
            source: T.Text,
            categories: T.List[T.Text],
            expected: T.Dict[T.Text, T.Text],
            ) -> None:

        stats = kconfgen.defconfig_split(
            kconf=self.kconf,
            fail_on_unknown=True,
            categories=categories,
            destdir=self.workdir,
            source=io.StringIO(source),
            prefix='defconfig',
        )

        self.assertEqual(
            set(self.workdir / filename for filename in expected),
            set(stats.files),
        )
        for filename, expected_contents in sorted(expected.items()):
            with open(self.workdir / filename, 'r') as f:
                contents = ''.join(f)
            self.assertEqual(expected_contents, contents)

    def test_empty(self):
        self.assert_category_expansion(
            source='',
            categories=[],
            expected={'defconfig': ''}
        )

    def test_validation(self):
        with self.assertRaises(ValueError):
            kconfgen.defconfig_split(
                kconf=self.kconf,
                fail_on_unknown=True,
                categories=[],
                destdir=self.workdir,
                source=io.StringIO('CONFIG_INVALID=y'),
                prefix='defconfig',
            )

    def test_no_split(self):
        self.assert_category_expansion(
            source='CONFIG_SIDE_SALAD=y',
            categories=[],
            expected={'defconfig': 'CONFIG_SIDE_SALAD=y\n'},
        )

    def test_minimal(self):
        self.assert_category_expansion(
            source="""CONFIG_EXTRA_CHEDDAR=y
CONFIG_CHEDDAR=y""",
            categories=[],
            expected={'defconfig': 'CONFIG_EXTRA_CHEDDAR=y\n'},
        )

    def test_split_fillings(self):
        self.assert_category_expansion(
            source="""CONFIG_SIDE_SALAD=y
CONFIG_DIET_NO_MILK_BASED=y
CONFIG_PICKLES=y
CONFIG_STEAK_CHICKEN=y
CONFIG_BREAD_POTATO=y""",
            categories=['fillings'],
            expected={
                'defconfig': """CONFIG_SIDE_SALAD=y
CONFIG_DIET_NO_MILK_BASED=y
CONFIG_BREAD_POTATO=y
CONFIG_PICKLES=y
""",
                'defconfig.fillings': 'CONFIG_STEAK_CHICKEN=y\n',
            },
        )

    def test_cli(self):
        with open(self.workdir / 'categories', 'w', encoding='utf-8') as f:
            f.write('bread\nfillings')
        with open(self.workdir / 'defconfig', 'w', encoding='utf-8') as f:
            f.write("""
CONFIG_CHEDDAR=y
CONFIG_EXTRA_CHEDDAR=y
CONFIG_BREAD_POTATO=y
CONFIG_STEAK_CHICKEN=y
CONFIG_SAUCE_MAYO=y
CONFIG_PICKLES=y""")

        os.mkdir(self.workdir / 'generated')

        subprocess.check_call([
            'python', '-m', 'kconfgen', 'split',
            '--kernel-source', KCONF_ROOT,
            '--arch', 'x86',
            '--fail-on-unknown',
            '--categories', self.workdir / 'categories',
            '--prefix', 'cli_test',
            '--destdir', self.workdir / 'generated',
            self.workdir / 'defconfig',
        ])

        expected = {
            'cli_test.bread': "CONFIG_BREAD_POTATO=y\n",
            'cli_test.fillings': "CONFIG_EXTRA_CHEDDAR=y\nCONFIG_STEAK_CHICKEN=y\n",
            'cli_test': "CONFIG_SAUCE_MAYO=y\nCONFIG_PICKLES=y\n",
        }
        filenames = os.listdir(self.workdir / 'generated')
        self.assertEqual(set(expected.keys()), set(filenames))
        for filename, contents in expected.items():
            with open(self.workdir / 'generated' / filename, 'r') as f:
                actual_contents = ''.join(f)
            self.assertEqual(contents, actual_contents)
