import pytest

from tablekit import render_table


def test_aligns_ascii_columns():
    out = render_table([["name", "qty"], ["apple", "3"]])
    assert out == "| name  | qty |\n| apple | 3   |"


def test_empty_rows_returns_empty_string():
    assert render_table([]) == ""


def test_ragged_rows_raise():
    with pytest.raises(ValueError):
        render_table([["a", "b"], ["c"]])
