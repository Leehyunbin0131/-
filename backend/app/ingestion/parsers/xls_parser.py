from __future__ import annotations

from app.ingestion.parsers.base import BaseExcelParser


class XlsParser(BaseExcelParser):
    extensions = (".xls",)
    parser_name = "xls"
    parser_version = "1.1"
    engine = "xlrd"
