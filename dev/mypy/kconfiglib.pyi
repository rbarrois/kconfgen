import typing as T

SymbolValue = T.Union[int, T.Text]


class MenuNode:
    filename: T.Text


class Symbol:
    user_value: T.Optional[SymbolValue]

    config_string: T.Text

    nodes: T.Sequence[MenuNode]


class Kconfig:
    def load_config(self, filename: str = None, replace: bool = True, verbose=None) -> str: ...

    def write_min_config(self, filename: str, header: str = ...) -> str: ...

    missing_syms: T.List[T.Tuple[T.Text, T.Text]]
    unique_defined_syms: T.List[Symbol]
