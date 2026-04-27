from think_tank.model_client import _new_aisuite_client


def test_aisuite_client_can_be_constructed_without_model_call() -> None:
    client = _new_aisuite_client()

    assert hasattr(client, "chat")
