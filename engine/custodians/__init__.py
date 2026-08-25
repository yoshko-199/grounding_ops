"""Custodian adapters — the only boundary permitted to originate a figure.

AC-14 guards this package: no retrieval path may reach a source that is not a
declared custodian in a loaded pack. There is no adapter accepting a URL and
no fallback adapter answering when no custodian is declared.
"""
