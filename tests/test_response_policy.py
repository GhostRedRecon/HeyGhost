from heyghost.response_policy import guard_llm_response


def test_llm_cannot_invent_system_status():
    guarded = guard_llm_response(
        "what is my cpu",
        "Your system has a very fast CPU.",
        "local model",
    )
    assert "should not guess system status" in guarded


def test_catalog_answer_passes_through():
    response = "Cybersecurity protects computers and data."
    assert guard_llm_response("what is cybersecurity", response, "knowledge:cybersecurity") == response
