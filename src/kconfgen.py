#!/usr/bin/env python

__version__ = '1.0.1'


import argparse
import enum
import os
import pathlib
import sys
import tempfile
import typing as T

import kconfiglib
import toml


PROFILES_FILENAME = 'profiles.toml'


class InvalidConfiguration(Exception):
    pass


# {{{1 Configuration
# =================


class Profile(T.NamedTuple):
    arch: T.Text
    files: T.List[pathlib.Path]


class CfgProfile(T.NamedTuple):
    arch: T.Text
    include: T.List[T.Text] = []
    extras: T.List[T.Text] = []


class CfgShared(T.NamedTuple):
    files: T.List[T.Text] = []


class Configuration(T.NamedTuple):
    profiles: T.Dict[T.Text, CfgProfile]
    shared: T.Dict[T.Text, CfgShared]


def load_configuration(config: T.Mapping[T.Text, T.Any]) -> Configuration:
    profiles = config.get('profile', {})
    shared = config.get('shared', {})

    errors = []
    for name, profile in sorted(profiles.items()):
        if not profile.get('arch'):
            errors.append("Missing arch for profile {}".format(name))
        if not profile.get('include') and not profile.get('extras'):
            errors.append("Missing 'include' or 'extras' for profile {}".format(name))
        for include in profile.get('include'):
            if not include.startswith('shared.'):
                errors.append("Invalid shared reference {s} in profile {p}".format(s=include, p=name))
            if include[len('shared.'):] not in shared:
                errors.append("Reference to missing group {s} in profile {p}".format(s=include, p=name))

    for name, section in sorted(shared.items()):
        if 'files' not in section:
            errors.append("Missing 'files' for shared group {}".format(name))

    if errors:
        raise InvalidConfiguration(errors)

    return Configuration(
        profiles={
            name: CfgProfile(
                arch=profile['arch'],
                include=[inc[len('shared.'):] for inc in profile.get('include', [])],
                extras=profile.get('extras', []),
            )
            for name, profile in profiles.items()
        },
        shared={
            name: CfgShared(
                files=section['files'] or [],
            )
            for name, section in shared.items()
        },
    )


# {{{1 Kconfig
# ===========


def load_kconf(kernel_sources: pathlib.Path, arch: T.Text):
    os.environ['srctree'] = str(kernel_sources)
    os.environ['SRCARCH'] = arch

    return kconfiglib.Kconfig()


# {{{1 Features
# ============


class Stats(T.NamedTuple):
    nb_symbols: int
    files: T.List[pathlib.Path]


def defconfig_for_target(
        config: Configuration,
        target: T.Text,
        root: pathlib.Path,
) -> Profile:

    profile = config.profiles[target]
    files: T.List[T.Text] = sum(
        (
            config.shared[include].files
            for include in profile.include
        ),
        [],
    )
    files.extend(profile.extras)

    return Profile(
        arch=profile.arch,
        files=[root / filename for filename in files],
    )


def defconfig_merge(
        kconf: kconfiglib.Kconfig,
        sources: T.List[pathlib.Path],
        fail_on_unknown: bool,
        output: T.TextIO,
) -> Stats:

    for path in sources:
        kconf.load_config(str(path), replace=False)
        if kconf.missing_syms and fail_on_unknown:
            raise ValueError("Unknown symbols: {}".format(kconf.missing_syms))

    stats = Stats(
        nb_symbols=len([
            symbol for symbol in kconf.unique_defined_syms if symbol.user_value
        ]),
        files=sources,
    )

    with tempfile.NamedTemporaryFile(mode='r') as f:
        kconf.write_min_config(f.name, header='')
        for line in f:
            output.write(line)

    return stats


def defconfig_split(
        kconf: kconfiglib.Kconfig,
        fail_on_unknown: bool,
        categories: T.List[T.Text],
        destdir: pathlib.Path,
        source: T.TextIO,
        prefix: T.Text,
) -> Stats:

    with tempfile.TemporaryDirectory() as d:
        config_path = os.path.join(d, '.config')
        defconfig_path = os.path.join(d, 'defconfig')
        with open(config_path, 'w', encoding='utf-8') as f:
            for line in source:
                f.write(line)
        kconf.load_config(config_path)

        if fail_on_unknown and kconf.missing_syms:
            raise ValueError("Unknown symbols: {}".format(kconf.missing_syms))

        kconf.write_min_config(defconfig_path)
        kconf.load_config(defconfig_path)

    symbols_by_category: T.Dict[T.Text, T.List[kconfiglib.Symbol]] = {cat: [] for cat in categories}
    symbols_by_category[''] = []
    for symbol in kconf.unique_defined_syms:
        if symbol.user_value is not None:
            category = max(cat for cat in symbols_by_category if symbol.nodes[0].filename.startswith(cat))
            symbols_by_category[category].append(symbol)

    stats = Stats(
        nb_symbols=sum(len(symbols) for symbols in symbols_by_category.values()),
        files=[],
    )

    for category, symbols in sorted(symbols_by_category.items()):
        if category:
            path = destdir / '{}.{}'.format(prefix, category.replace('/', '_'))
        else:
            path = destdir / prefix
        stats.files.append(path)
        with path.open('w', encoding='utf-8') as output:
            for symbol in symbols:
                output.write(symbol.config_string)

    return stats


# {{{1 Main


def main() -> None:
    class Mode(enum.Enum):
        MERGE = 'merge'
        SPLIT = 'split'
        ASSEMBLE = 'assemble'

    # {{{ Parser

    parser = argparse.ArgumentParser(
        description="Split a defconfig file based on chosen categories"
    )
    parser.set_defaults(mode=None)
    subparsers = parser.add_subparsers(help="Modes")

    assemble_parser = subparsers.add_parser(
        'assemble',
        help="Assemble a defconfig file for a chosen target",
    )
    assemble_parser.set_defaults(mode=Mode.ASSEMBLE)
    assemble_parser.add_argument(
        '--root', '-r', type=pathlib.Path,
        default='.', help="Profiles repository root",
    )
    assemble_parser.add_argument(
        '--output', '-o', type=argparse.FileType('w', encoding='utf-8'),
        default=sys.stdout, help="Path of the generated defconfig file",
    )
    assemble_parser.add_argument(
        'target', help="Assemble a defconfig file for TARGET",
    )

    merge_parser = subparsers.add_parser('merge', help="Merge deconfig files")
    merge_parser.set_defaults(mode=Mode.MERGE)
    merge_parser.add_argument(
        'sources', type=pathlib.Path, nargs='+',
        help="Source files to read, in order",
    )
    merge_parser.add_argument(
        '--output', '-o', type=argparse.FileType('w', encoding='utf-8'),
        default=sys.stdout, help="Path of the generated defconfig file",
    )
    merge_parser.add_argument(
        '--arch', type=str, required=True,
        help="Target architecture",
    )

    split_parser = subparsers.add_parser(
        'split',
        help="Split a defconfig file based on chosen categories"
    )
    split_parser.set_defaults(mode=Mode.SPLIT)
    split_parser.add_argument(
        '--categories', '-c', type=argparse.FileType('r', encoding='utf-8'), required=True,
        help="File containing categories, one per line.",
    )
    split_parser.add_argument(
        '--destdir', '-d', type=str, required=True,
        help="Directory where generated files should be written",
    )
    split_parser.add_argument(
        '--prefix', '-p', type=str, default='defconfig',
        help="Prefix for generated files",
    )
    split_parser.add_argument(
        'source', type=argparse.FileType('r', encoding='utf-8'),
        help="Source file to read",
    )
    split_parser.add_argument(
        '--arch', type=str, required=True,
        help="Target architecture",
    )

    # Common options
    for subparser in [assemble_parser, merge_parser, split_parser]:
        subparser.add_argument(
            '--kernel-source', '-k', type=str, required=True,
            help="Path to the kernel source tree",
        )
        subparser.add_argument(
            '--fail-on-unknown', action='store_true', default=False,
            help="Don't allow symbols unknown from the target kernel.",
        )

    # }}}

    args = parser.parse_args()

    # {{{ Launchers

    if args.mode == Mode.MERGE:
        kconf = load_kconf(
            kernel_sources=pathlib.Path(args.kernel_source),
            arch=args.arch,
        )
        stats = defconfig_merge(
            kconf=kconf,
            fail_on_unknown=args.fail_on_unknown,
            sources=args.sources,
            output=args.output,
        )
        sys.stderr.write(">>> Written {ns} symbols.\n".format(
            ns=stats.nb_symbols,
        ))

    elif args.mode == Mode.SPLIT:
        kconf = load_kconf(
            kernel_sources=pathlib.Path(args.kernel_source),
            arch=args.arch,
        )
        try:
            categories = [line.strip() for line in args.categories]

            stats = defconfig_split(
                kconf=kconf,
                fail_on_unknown=args.fail_on_unknown,
                categories=categories,
                destdir=pathlib.Path(args.destdir),
                source=args.source,
                prefix=args.prefix,
            )
            sys.stderr.write(">>> Written {ns} symbols to files {files}.\n".format(
                ns=stats.nb_symbols,
                files=', '.join(str(path) for path in stats.files),
            ))
        finally:
            args.categories.close()
            args.source.close()

    elif args.mode == Mode.ASSEMBLE:
        profiles = toml.load(args.root / PROFILES_FILENAME)
        config = load_configuration(profiles)
        profile = defconfig_for_target(
            config=config,
            target=args.target,
            root=args.root,
        )
        kconf = load_kconf(
            kernel_sources=pathlib.Path(args.kernel_source),
            arch=profile.arch,
        )
        stats = defconfig_merge(
            kconf=kconf,
            fail_on_unknown=args.fail_on_unknown,
            sources=profile.files,
            output=args.output,
        )
        sys.stderr.write(">>> Written {ns} symbols for {t}.\n".format(
            ns=stats.nb_symbols,
            t=args.target,
        ))
    else:
        assert args.mode is None
        parser.print_help()

    # }}}


if __name__ == '__main__':
    main()
