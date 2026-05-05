from pathlib import Path

import pytest

_DATASET = Path(__file__).parent.parent / "dataset"
_PLAN_DIR = _DATASET / "images" / "raw"
_SPRINKLERS_DIR = _DATASET / "images" / "sprinklers"

_PLAN_STEM = "001_Fire_Sprinkler_Plan_page_001"


@pytest.fixture(scope="session")
def plan_bytes() -> bytes:
    return (_PLAN_DIR / f"{_PLAN_STEM}.png").read_bytes()


@pytest.fixture(scope="session")
def ref_bytes_1() -> bytes:
    return (_SPRINKLERS_DIR / _PLAN_STEM / "sprinkler_1.png").read_bytes()


@pytest.fixture(scope="session")
def ref_bytes_2() -> bytes:
    return (_SPRINKLERS_DIR / _PLAN_STEM / "sprinkler_2.png").read_bytes()


@pytest.fixture(scope="session")
def ref_bytes_3() -> bytes:
    return (_SPRINKLERS_DIR / _PLAN_STEM / "sprinkler_3.png").read_bytes()
