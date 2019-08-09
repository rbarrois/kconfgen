__version__ = '1.0.2.dev0'


from .core import (  # noqa: F401
    load_kconf,
    load_configuration,
    Configuration,
    CfgProfile,
    CfgInclude,
    PROFILES_FILENAME,
    defconfig_for_target,
    defconfig_merge,
    defconfig_split,
)
