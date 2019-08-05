#!/usr/bin/env python

__version__ = '0.1.0'


import argparse
import enum
import os
import pathlib
import sys
import tempfile
import typing as T

import kconfiglib


class Stats(T.NamedTuple):
    nb_symbols: int
    files: T.List[pathlib.Path]


def load_kconf(kernel_sources: pathlib.Path, arch: T.Text):
    os.environ['srctree'] = str(kernel_sources)
    os.environ['SRCARCH'] = arch

    return kconfiglib.Kconfig()


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


def main() -> None:
    class Mode(enum.Enum):
        MERGE = 'merge'
        SPLIT = 'split'
        ASSEMBLE = 'assemble'

    parser = argparse.ArgumentParser(
        description="Split a defconfig file based on chosen categories"
    )
    subparsers = parser.add_subparsers(help="Modes")
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

    # Common options
    for subparser in [merge_parser, split_parser]:
        subparser.add_argument(
            '--kernel-source', '-k', type=str, required=True,
            help="Path to the kernel source tree",
        )
        subparser.add_argument(
            '--arch', type=str, required=True,
            help="Target architecture",
        )
        subparser.add_argument(
            '--fail-on-unknown', action='store_true', default=False,
            help="Don't allow symbols unknown from the target kernel.",
        )

    args = parser.parse_args()
    kconf = load_kconf(
        kernel_sources=pathlib.Path(args.kernel_source),
        arch=args.arch,
    )
    if args.mode == Mode.MERGE:
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


if __name__ == '__main__':
    main()
