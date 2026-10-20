"""Shared PDF upload limit. The HTTP route and both case stores use these constants."""
from __future__ import annotations

PDF_MAX_BYTES = 4 * 1024 * 1024
PDF_TOO_LARGE_DETAIL = 'PDF too large: the limit is 4 MB. Try compressing the file or splitting it.'
