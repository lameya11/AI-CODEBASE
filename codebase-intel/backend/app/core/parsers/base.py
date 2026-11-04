"""Shared dataclasses for parser results."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ImportInfo:
    """Represents a single import statement."""
    module: str
    names: list[str] = field(default_factory=list)
    alias: Optional[str] = None
    level: int = 0  # relative import level (0 = absolute)
    is_external: bool = False  # set during graph building


@dataclass
class SymbolInfo:
    """A function, class, method, component, or route."""
    name: str
    kind: str  # function | class | method | component | route
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    parent_name: Optional[str] = None
    route_method: Optional[str] = None
    route_path: Optional[str] = None


@dataclass
class CallInfo:
    """A function call found inside a symbol."""
    caller_symbol: str
    callee: str


@dataclass
class RouteInfo:
    """HTTP route found in source."""
    method: str
    path: str
    function_name: str
    start_line: int


@dataclass
class ParseResult:
    """Complete result from parsing one file."""
    language: str
    imports: list[ImportInfo] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)
    parse_error: Optional[str] = None
