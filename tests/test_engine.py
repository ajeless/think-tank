from think_tank.engine import get_engine_status


def test_get_engine_status_returns_structured_data() -> None:
    assert get_engine_status() == {
        "product": "Think Tank",
        "ready": True,
    }

