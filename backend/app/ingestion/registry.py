from __future__ import annotations

from pathlib import Path

from app.ingestion.parsers import XlsParser, XlsxParser
from app.ingestion.parsers.base import DataParser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, DataParser] = {}

    def register(self, parser: DataParser) -> None:
        for extension in parser.extensions:
            self._parsers[extension.lower()] = parser

    def get_parser(self, path: Path) -> DataParser:
        extension = path.suffix.lower()
        if extension not in self._parsers:
            raise ValueError(f"No parser registered for extension: {extension}")
        return self._parsers[extension]

    @classmethod
    def default(cls) -> "ParserRegistry":
        registry = cls()
        registry.register(XlsParser())
        registry.register(XlsxParser())
        return registry
