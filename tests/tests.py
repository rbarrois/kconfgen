import io
import os.path
import pathlib
import subprocess
import tempfile
import typing as T
import unittest

import toml

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


class CoreCliTests(unittest.TestCase):
    def test_no_params(self):
        res = subprocess.run(
            ['kconfgen'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
        )
        self.assertEqual(0, res.returncode)
        self.assertEqual('', res.stderr)
        # Description for commands
        self.assertIn('kconfgen', res.stdout)
        self.assertIn(' assemble', res.stdout)
        self.assertIn(' split', res.stdout)
        self.assertIn(' merge', res.stdout)
        self.assertIn(' version', res.stdout)
        self.assertIn(' help', res.stdout)

    def test_version(self):
        res = subprocess.run(
            ['kconfgen', 'version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
        )
        self.assertEqual(0, res.returncode)
        self.assertEqual('', res.stderr)
        self.assertEqual("kconfgen v{}".format(kconfgen.__version__), res.stdout)

    def test_full_help(self):
        res = subprocess.run(
            ['kconfgen', 'help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
        )
        self.assertEqual(0, res.returncode)
        self.assertEqual('', res.stderr)

        # Description of commands
        self.assertIn('kconfgen', res.stdout)
        self.assertIn('kconfgen assemble', res.stdout)
        self.assertIn('kconfgen split', res.stdout)
        self.assertIn('kconfgen merge', res.stdout)
        self.assertIn(' version', res.stdout)
        self.assertIn(' help', res.stdout)

        # Parameters of commands
        self.assertIn('--kernel-source', res.stdout)
        self.assertIn('--arch', res.stdout)
        self.assertIn('--categories', res.stdout)
        self.assertIn('--root', res.stdout)


class AssembleTests(KConfGenTestCase):
    def test_load_config(self):
        raw = """
[include.core]
files = ["defconfig.crypto", "defconfig.fs"]

[profile.example]
arch = "x86"
include = [ "core", "server" ]
extras = ["defconfig.example", "defconfig.wifi_intel"]

[include.server]
files = ["defconfig.net", "defconfig.net_netfilter"]
"""

        loaded = kconfgen.load_configuration(toml.loads(raw))

        self.assertEqual(
            kconfgen.Configuration(
                profiles={
                    'example': kconfgen.CfgProfile(
                        arch='x86',
                        include=['core', 'server'],
                        extras=['defconfig.example', 'defconfig.wifi_intel'],
                    ),
                },
                includes={
                    'core': kconfgen.CfgInclude(
                        files=['defconfig.crypto', 'defconfig.fs'],
                    ),
                    'server': kconfgen.CfgInclude(
                        files=['defconfig.net', 'defconfig.net_netfilter'],
                    ),
                },
            ),
            loaded,
        )

    def assert_assemble_result(self, config: T.Text, defconfigs: T.Dict[T.Text, T.Text], expected: T.Text):
        with open(self.workdir / kconfgen.PROFILES_FILENAME, 'w') as f:
            f.write(config)

        for fname, contents in defconfigs.items():
            with open(self.workdir / 'defconfig.{}'.format(fname), 'w') as f:
                f.write(contents)

        subprocess.check_call([
            'kconfgen', 'assemble',
            '--kernel-source', KCONF_ROOT,
            '--fail-on-unknown',
            '--root', self.workdir,
            '--output', self.workdir / 'output',
            'example',
        ])

        with open(self.workdir / 'output', 'r') as f:
            results = ''.join(f)
        self.assertEqual(expected, results)

    def test_assemble(self):
        self.assert_assemble_result(
            config="""
[profile.example]
arch = "x86"
include = [ "plusplus" ]
extras = [ "defconfig.cheesy" ]
[include.plusplus]
files = [ "defconfig.more", "defconfig.fullsides"]
""",
            defconfigs={
                'cheesy': "CONFIG_CHEDDAR=y\nCONFIG_SAUCE_BLUE_CHEESE=y\nCONFIG_SIDE_FRIES_LOADED=y",
                'more': "CONFIG_EXTRA_CHEDDAR=y",
                'fullsides': "CONFIG_SIDE_FRIES_LOADED=y\nCONFIG_PICKLES=y",
            },
            expected="""CONFIG_SIDE_FRIES_LOADED=y
CONFIG_EXTRA_CHEDDAR=y
CONFIG_SAUCE_BLUE_CHEESE=y
CONFIG_PICKLES=y
""",
        )


class MergeTests(KConfGenTestCase):
    def assert_merge_result(
        self,
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
        kconfgen.defconfig_merge(
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
            'kconfgen', 'merge',
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

    def assert_category_expansion(
            self,
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
            categories=['fillings/extras'],
            expected={
                'defconfig': """CONFIG_SIDE_SALAD=y
CONFIG_DIET_NO_MILK_BASED=y
CONFIG_BREAD_POTATO=y
CONFIG_STEAK_CHICKEN=y
""",
                'defconfig.fillings_extras': 'CONFIG_PICKLES=y\n',
            },
        )

    def test_cli(self):
        with open(self.workdir / 'categories', 'w', encoding='utf-8') as f:
            f.write('bread\nfillings/extras')
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
            'kconfgen', 'split',
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
            'cli_test': "CONFIG_EXTRA_CHEDDAR=y\nCONFIG_STEAK_CHICKEN=y\n",
            'cli_test.fillings_extras': "CONFIG_SAUCE_MAYO=y\nCONFIG_PICKLES=y\n",
        }
        filenames = os.listdir(self.workdir / 'generated')
        self.assertEqual(set(expected.keys()), set(filenames))
        for filename, contents in expected.items():
            with open(self.workdir / 'generated' / filename, 'r') as f:
                actual_contents = ''.join(f)
            self.assertEqual(contents, actual_contents)
