import pytest
from src.core.redactor import PIIRedactor

def test_redact_person_name():
    redactor = PIIRedactor()
    text = "John Doe is the CEO."
    anonymized_text, token_map = redactor.redact_text(text)
    
    assert "John Doe" not in anonymized_text
    assert "[PERSON_1]" in anonymized_text
    assert token_map.get("[PERSON_1]") == "John Doe"

def test_redact_ssn():
    redactor = PIIRedactor()
    # Presidio uses generic entities or we might need specific recognizers.
    # By default, Presidio recognizes US_SSN or crypto etc. But let's assume it catches it.
    text = "My SSN is 123-456-7890."
    anonymized_text, token_map = redactor.redact_text(text)
    
    # Check that the raw SSN is not in the text
    assert "123-456-7890" not in anonymized_text
    assert len(token_map) > 0
    # SSN might be caught as US_SSN or similar, but the exact token doesn't matter, just that it's replaced.
    assert list(token_map.values())[0] == "123-456-7890"

def test_redact_credit_card():
    redactor = PIIRedactor()
    # Mocking standard CC. Wait, Presidio's CC recognizer looks for 16-19 digits usually.
    text = "Payment using card 4111-1111-1111-1111."
    anonymized_text, token_map = redactor.redact_text(text)
    
    assert "4111-1111-1111-1111" not in anonymized_text
    assert len(token_map) > 0
    assert list(token_map.values())[0] == "4111-1111-1111-1111"

def test_restore_text():
    redactor = PIIRedactor()
    redacted_text = "Hello [PERSON_1], your balance is [MONEY_1]."
    token_map = {"[PERSON_1]": "Alice", "[MONEY_1]": "$500"}
    
    restored = redactor.restore_text(redacted_text, token_map)
    assert restored == "Hello Alice, your balance is $500."
