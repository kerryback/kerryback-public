"""External scholarly discovery (OpenAlex, Semantic Scholar).

Thin urllib clients that return the same normalized record shape as the Zotero
adapter, so external results flow through the existing dedup / keyword /
embedding pipeline. No third-party dependencies; kept in-house so the plugin
stays self-contained across macOS and Windows.
"""
