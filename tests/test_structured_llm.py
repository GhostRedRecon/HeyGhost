from heyghost.llm.structured import parse_json_object, validate_intent_classification


def test_valid_intent_classification_is_clamped():
    parsed = parse_json_object('{"route":"rag","confidence":1.4,"domain":"rag","reason":"local docs"}')
    decision = validate_intent_classification(parsed)
    assert decision.route == "rag"
    assert decision.confidence == 1.0
    assert decision.domain == "rag"


def test_invalid_intent_route_is_rejected():
    parsed = parse_json_object('{"route":"shell","confidence":0.9,"domain":"system","reason":"bad"}')
    try:
        validate_intent_classification(parsed)
    except ValueError:
        return
    raise AssertionError("invalid route should fail validation")


def test_json_object_can_be_extracted_from_fenced_text():
    parsed = parse_json_object('```json\n{"route":"general","confidence":0.5,"domain":"general","reason":"ok"}\n```')
    assert parsed["route"] == "general"
