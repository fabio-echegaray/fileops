SCHEMA_SUMMARY = "fileops-summary"
SCHEMA_CFG_CONTENT = "fileops-cfg-content"
SUMMARY_SCHEMA_VERSION = 2
CFG_CONTENT_SCHEMA_VERSION = 2


class LegacyFormatError(Exception):
    """Raised when a file does not match the current schema and cannot be read.

    Users must regenerate the file from its source (media for the summary,
    config files for cfg_content) rather than migrate in place.
    """


def set_workbook_schema(book, kind, version):
    """Stamp the current schema kind/version into the workbook document properties."""
    raise NotImplementedError("Stage B")


def read_workbook_schema(path):
    """Read (kind, version) from the document properties, or None when absent."""
    raise NotImplementedError("Stage B")


def detect_summary_schema(path):
    """Return (SCHEMA_SUMMARY, version) or raise LegacyFormatError.

    Prefers the document-properties marker; falls back to structure within the
    xlsx when the properties were stripped.
    """
    raise NotImplementedError("Stage B")


def detect_cfg_content_schema(path):
    """Return (SCHEMA_CFG_CONTENT, version) or raise LegacyFormatError.

    Prefers the document-properties marker; falls back to structure within the
    xlsx when the properties were stripped.
    """
    raise NotImplementedError("Stage B")