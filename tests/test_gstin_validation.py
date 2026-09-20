import pytest

from app.services.compliance_service import gstin_check_character, validate_gstin


@pytest.mark.parametrize("gstin", [
    "27AAPFU0939F1ZV",          # real-world example GSTIN
    "29ABCDE1234F1ZW",
    " 29pqrsx5678k1zu ",        # whitespace and lower case are tolerated
])
def test_valid_gstins(gstin):
    valid, message = validate_gstin(gstin)
    assert valid, message


@pytest.mark.parametrize("gstin, reason", [
    (None, "missing"),
    ("", "missing"),
    ("29ABCDE1234F1Z", "15 characters"),          # too short
    ("29ABCDE1234F1XW", "format"),                # 14th character must be Z
    ("2912345ABCDF1ZW", "format"),                # PAN part in wrong order
    ("00ABCDE1234F1ZW", "state code"),            # state code 00 does not exist
    ("45ABCDE1234F1ZW", "state code"),
    ("29ABCDE1234F1Z5", "check-digit"),           # right shape, wrong check character
    ("27AAPFU0939F1ZX", "check-digit"),           # one character of a real GSTIN changed
])
def test_invalid_gstins(gstin, reason):
    valid, message = validate_gstin(gstin)
    assert not valid
    assert reason in message


def test_check_character_matches_known_gstins():
    # the 15th character is derived from the first 14
    assert gstin_check_character("27AAPFU0939F1Z") == "V"
    assert gstin_check_character("29ABCDE1234F1Z") == "W"


def test_check_digit_catches_a_single_typo():
    """Any one-character typo in the first 14 should change the expected check character."""
    gstin = "27AAPFU0939F1ZV"
    typo = "27AAPEU0939F1ZV"          # F -> E in the PAN part
    assert validate_gstin(gstin)[0]
    assert not validate_gstin(typo)[0]
