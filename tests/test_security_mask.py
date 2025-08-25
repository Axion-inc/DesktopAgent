import pytest

# This import will fail initially - expected for TDD red phase
try:
    from app.security import mask
except ImportError:
    # Expected during red phase
    pass


@pytest.mark.xfail(reason="TDD red phase - mask function not implemented yet")
def test_mask_email_phone_path_and_name():
    text = "Contact John Doe at john.doe@example.com or +1-202-555-0123. File at /Users/john/secret/report.pdf"
    m = mask(text)
    assert "@" not in m
    assert "202-555-0123" not in m
    assert "/Users/john/secret" not in m
    assert "John Doe" not in m

