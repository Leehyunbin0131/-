from __future__ import annotations

from app.ingestion.parsers.base import BaseExcelParser


class XlsxParser(BaseExcelParser):
    extensions = (".xlsx", ".xlsm")
    parser_name = "xlsx"
    parser_version = "1.1"
    engine = "openpyxl"
