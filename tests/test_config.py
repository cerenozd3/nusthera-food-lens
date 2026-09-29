from src.config import _as_bool


def test_mock_mode_parses_common_truthy_values():
    assert _as_bool("true", default=False) is True
    assert _as_bool("TRUE", default=False) is True
    assert _as_bool("1", default=False) is True
    assert _as_bool("false", default=True) is False
    assert _as_bool(None, default=True) is True
