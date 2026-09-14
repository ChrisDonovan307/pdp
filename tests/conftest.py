from pathlib import Path

import pytest

from pdp.pdp_config import PDPConfig


@pytest.fixture
def config(fs):
    config = PDPConfig("test", Path("pdp.yml"))

    yield config