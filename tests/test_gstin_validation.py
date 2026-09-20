import pytest

from app.services.compliance_service import validate_gstin


@pytest.mark.parametrize("gstin", ["29ABCDE1234F1Z5", "27AAPFU0939F1ZV", " 07aabcu9603r1zm "])
def test_valid_gstins(gstin):
    valid, _ = validate_gstin(gstin)
    assert valid


@pytest.mark.parametrize("gstin, reason", [
    (None, "missing"),
    ("", "missing"),
    ("29ABCDE1234F1Z", "15 characters"),          # too short
    ("29ABCDE1234F1X5", "format"),                # 14th character must be Z
    ("2912345ABCDF1Z5", "format"),                # PAN part in wrong order
    ("00ABCDE1234F1Z5", "state code"),            # state code 00 does not exist
    ("45ABCDE1234F1Z5", "state code"),
])
def test_invalid_gstins(gstin, reason):
    valid, message = validate_gstin(gstin)
    assert not valid
    assert reason in message
