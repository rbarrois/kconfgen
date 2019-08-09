import os
import pathlib
import tempfile
import typing as T

import kconfiglib


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


class CfgInclude(T.NamedTuple):
    files: T.List[T.Text] = []


class Configuration(T.NamedTuple):
    profiles: T.Dict[T.Text, CfgProfile]
    includes: T.Dict[T.Text, CfgInclude]


def load_configuration(config: T.Mapping[T.Text, T.Any]) -> Configuration:
    profiles = config.get('profile', {})
    includes = config.get('include', {})

    errors = []
    for name, profile in sorted(profiles.items()):
        if not profile.get('arch'):
            errors.append("Missing arch for profile {}".format(name))
        if not profile.get('include') and not profile.get('extras'):
            errors.append("Missing 'include' or 'extras' for profile {}".format(name))
        for include in profile.get('include'):
            if include not in includes:
                errors.append("Reference to missing group {s} in profile {p}".format(s=include, p=name))

    for name, section in sorted(includes.items()):
        if 'files' not in section:
            errors.append("Missing 'files' for include group {}".format(name))

    if errors:
        raise InvalidConfiguration(errors)

    return Configuration(
        profiles={
            name: CfgProfile(
                arch=profile['arch'],
                include=profile.get('include', []),
                extras=profile.get('extras', []),
            )
            for name, profile in profiles.items()
        },
        includes={
            name: CfgInclude(
                files=section['files'] or [],
            )
            for name, section in includes.items()
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
            config.includes[include].files
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
