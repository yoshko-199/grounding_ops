"""cli/signoff.py's store-backed path: list, then confirm by claim id."""

from __future__ import annotations

import pathlib

from cli.verify import main as verify_main
from engine.store.events import RetrievalStore

CLAIM = "prices rose over the last three years due to governmental incompetence"


def _run_and_get_claim_id(store_path: str, capsys) -> str:
    assert verify_main([CLAIM, "--jurisdiction", "ZZ", "--packs", "packs/fixture",
                         "--store", store_path]) == 0
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("claim id:"))
    return line.split()[2]


def test_list_then_confirm_by_claim_id(tmp_path, capsys) -> None:
    from cli.signoff import main as signoff_main

    store_path = str(tmp_path / "store.db")
    claim_id = _run_and_get_claim_id(store_path, capsys)

    assert signoff_main(["list", "--store", store_path]) == 0
    assert claim_id in capsys.readouterr().out

    assert signoff_main(
        ["confirm", "--claim-id", claim_id, "--reviewer", "a reviewer", "--store", store_path]
    ) == 0
    out = capsys.readouterr().out
    assert "state:     confirmed" in out

    assert signoff_main(["list", "--store", store_path]) == 0
    assert "Nothing is awaiting review." in capsys.readouterr().out


def test_confirming_an_unknown_claim_id_fails_cleanly(tmp_path, capsys) -> None:
    from cli.signoff import main as signoff_main

    store_path = str(tmp_path / "store.db")
    RetrievalStore(store_path).close()  # an empty but valid store

    assert signoff_main(
        ["confirm", "--claim-id", "not-a-real-id", "--reviewer", "x", "--store", store_path]
    ) == 2


def test_confirming_the_same_claim_twice_fails_the_second_time(tmp_path, capsys) -> None:
    from cli.signoff import main as signoff_main

    store_path = str(tmp_path / "store.db")
    claim_id = _run_and_get_claim_id(store_path, capsys)

    assert signoff_main(
        ["confirm", "--claim-id", claim_id, "--reviewer", "a", "--store", store_path]
    ) == 0
    assert signoff_main(
        ["confirm", "--claim-id", claim_id, "--reviewer", "a", "--store", store_path]
    ) == 2


def test_requires_exactly_one_of_claim_id_or_proposed(capsys) -> None:
    from cli.signoff import main as signoff_main

    assert signoff_main(["confirm", "--reviewer", "a"]) == 2
    assert "exactly one" in capsys.readouterr().err


def test_ad_hoc_mode_still_writes_nothing(tmp_path, capsys) -> None:
    """The legacy path stays available and, correctly, touches no store."""
    from cli.signoff import main as signoff_main

    assert signoff_main(["confirm", "--reviewer", "a", "--proposed", "accurate"]) == 0
    out = capsys.readouterr().out
    assert "claim id:" not in out
