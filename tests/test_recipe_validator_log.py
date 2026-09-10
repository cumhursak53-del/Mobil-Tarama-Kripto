from engine.recipe_validator import validate_recipes


def test_validate_recipes_logs_rejects():
    state = {"research": {}}
    raw = [{"name": "bad", "long_rules": [{"type": "stage", "value": "unknown"}]}]
    out = validate_recipes(raw, source="test", state=state, log=None)
    assert out == []
    assert state["research"]["validator_rejects"]
