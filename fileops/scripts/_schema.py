import json
from pathlib import Path

import openpyxl

SCHEMA_SUMMARY = "fileops-summary"
SCHEMA_CFG_CONTENT = "fileops-cfg-content"
SUMMARY_SCHEMA_VERSION = 2
CFG_CONTENT_SCHEMA_VERSION = 2


class LegacyFormatError(ValueError):
    """Raised when a file does not match the current schema and cannot be read.

    Users must regenerate the file from its source (media for the summary,
    config files for cfg_content) rather than migrate in place. It subclasses
    ValueError so callers that reject unsupported formats also catch it.
    """


def set_workbook_schema(book, kind, version):
    """Stamp the current schema kind/version into the workbook document properties."""
    payload = {"schema": kind, "schema_version": version}
    book.properties.description = json.dumps(payload)
    book.properties.title = kind
    book.properties.subject = f"{kind} v{version}"


def read_workbook_schema(path):
    """Read (kind, version) from the document properties, or None when absent."""
    path = Path(path)
    try:
        book = openpyxl.load_workbook(path, read_only=True)
    except Exception:
        return None
    try:
        description = book.properties.description
    finally:
        book.close()
    if not description:
        return None
    try:
        payload = json.loads(description)
        return payload["schema"], int(payload["schema_version"])
    except (ValueError, KeyError, TypeError):
        return None


def _require_xlsx_and_existing(path) -> str:
    path = Path(path)
    if path.suffix.casefold() != ".xlsx":
        raise LegacyFormatError(
            f"Only the current xlsx format is supported, got"
            f" {path.suffix or 'no extension'}: {path}")
    if not path.exists():
        raise LegacyFormatError(f"File does not exist: {path}")
    return path


def _sheet_header(path, sheet_name) -> list:
    book = openpyxl.load_workbook(path, read_only=True)
    try:
        if sheet_name not in book.sheetnames:
            return []
        ws = book[sheet_name]
        return [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    finally:
        book.close()


def detect_summary_schema(path):
    """Return (SCHEMA_SUMMARY, version) or raise LegacyFormatError.

    Prefers the document-properties marker; falls back to structure within the
    xlsx when the properties were stripped.
    """
    _require_xlsx_and_existing(path)
    marker = read_workbook_schema(path)
    if marker is not None:
        kind, version = marker
        if kind == SCHEMA_SUMMARY and version >= SUMMARY_SCHEMA_VERSION:
            return SCHEMA_SUMMARY, SUMMARY_SCHEMA_VERSION
        raise LegacyFormatError(
            f"Summary file {path} is marked with a legacy or foreign schema"
            f" ({kind} v{version}) and cannot be read. Regenerate it from the"
            f" media instead of migrating in place.")

    header = _sheet_header(path, "Files-Timeseries")
    if not header:
        raise LegacyFormatError(
            f"Summary file {path} has no Files-Timeseries sheet and cannot be read.")
    if "cfg_path" in header or "cfg_folder" in header:
        raise LegacyFormatError(
            f"Summary file {path} carries the legacy cfg_path/cfg_folder columns;"
            f" regenerate it from the media instead of migrating in place.")
    return SCHEMA_SUMMARY, SUMMARY_SCHEMA_VERSION


def detect_cfg_content_schema(path):
    """Return (SCHEMA_CFG_CONTENT, version) or raise LegacyFormatError.

    Prefers the document-properties marker; falls back to structure within the
    xlsx when the properties were stripped.
    """
    _require_xlsx_and_existing(path)
    marker = read_workbook_schema(path)
    if marker is not None:
        kind, version = marker
        if kind == SCHEMA_CFG_CONTENT and version >= CFG_CONTENT_SCHEMA_VERSION:
            return SCHEMA_CFG_CONTENT, CFG_CONTENT_SCHEMA_VERSION
        raise LegacyFormatError(
            f"Configuration content file {path} is marked with a legacy or"
            f" foreign schema ({kind} v{version}) and cannot be read. Regenerate"
            f" it from the configuration folder instead of migrating in place.")

    book = openpyxl.load_workbook(path, read_only=True)
    try:
        if "Configs" in book.sheetnames:
            return SCHEMA_CFG_CONTENT, CFG_CONTENT_SCHEMA_VERSION
        raise LegacyFormatError(
            f"Configuration content file {path} has no Configs sheet; regenerate"
            f" it from the configuration folder instead of migrating in place.")
    finally:
        book.close()
