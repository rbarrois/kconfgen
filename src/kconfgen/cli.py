#!/usr/bin/env python

import argparse
import enum
import pathlib
import sys

import toml

from . import (
    PROFILES_FILENAME,
    __version__,
    defconfig_for_target,
    defconfig_merge,
    defconfig_split,
    load_configuration,
    load_kconf,
)


class Mode(enum.Enum):
    ASSEMBLE = 'assemble'
    HELP = 'help'
    MERGE = 'merge'
    SPLIT = 'split'
    VERSION = 'version'


def main() -> None:
    # {{{ Parser

    parser = argparse.ArgumentParser(
        description="Split a defconfig file based on chosen categories"
    )
    parser.set_defaults(mode=None)
    subparsers = parser.add_subparsers(help="Modes")

    version_parser = subparsers.add_parser(
        'version',
        help="Display the version number",
    )
    version_parser.set_defaults(mode=Mode.VERSION)

    help_parser = subparsers.add_parser(
        'help',
        help="Display the full documentation",
    )
    help_parser.set_defaults(mode=Mode.HELP)

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

    elif args.mode == Mode.VERSION:
        sys.stdout.write("kconfgen v{}".format(__version__))

    elif args.mode == Mode.HELP:
        parser.print_help()
        for subparser in [assemble_parser, merge_parser, split_parser]:
            sys.stdout.write('\n\n')
            sys.stdout.write('{}\n'.format(subparser.prog))
            sys.stdout.write('{}\n'.format('-' * len(subparser.prog)))
            subparser.print_help()

    else:
        assert args.mode is None
        parser.print_help()

    # }}}


if __name__ == '__main__':
    main()
