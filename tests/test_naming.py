import pytest
from robotbase.naming import to_snake_identifier

def test_hyphen_to_underscore():
    assert to_snake_identifier("warehouse-bot") == "warehouse_bot"

def test_spaces_and_case():
    assert to_snake_identifier("Warehouse Bot") == "warehouse_bot"

def test_already_valid():
    assert to_snake_identifier("obstacle_bot") == "obstacle_bot"

def test_leading_digit_rejected():
    with pytest.raises(ValueError):
        to_snake_identifier("2bot")

def test_empty_rejected():
    with pytest.raises(ValueError):
        to_snake_identifier("")
