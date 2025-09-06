import os
import pytest


pytestmark = pytest.mark.skipif(os.environ.get('E2E_ENABLE') != '1', reason='E2E disabled by default')


def test_placeholder_cookie_transfer():
    assert True

