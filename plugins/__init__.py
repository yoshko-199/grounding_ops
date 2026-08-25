"""Plugins — code that runs beside the engine and is never part of it.

Everything under this package sits on the **claim-input** side of the system.
A plugin may reach the network, parse untrusted markup, and produce text.  It
may not produce a figure, a retrieval, or anything that becomes evidence.

That boundary is not a convention here, it is asserted:
``tests/conformance/test_plugin_isolation.py`` fails if any ``engine`` module
can reach any ``plugins`` module by any import path, and if any harvest module
can reach the custodian adapters, the retrieval layer, or the event store.

The reason for the separation is AC-14, which the engine states in
``engine/custodians/base.py``: "no web search, no news source, no model prior,
no operator-supplied URL."  A harvester is all four of the things that
sentence excludes.  Keeping it in the repository is useful; keeping it
reachable from a verification path would dissolve the one distinction every
other guarantee rests on.
"""
