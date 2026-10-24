"""Planning/registry consistency is part of every verification run."""

import check_parity


def test_parity_and_registry_are_clean() -> None:
    assert check_parity.main() == 0
