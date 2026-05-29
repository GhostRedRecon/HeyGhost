from heyghost.skills.domain_catalog import answer_domain_question, topic_counts


def test_domain_catalog_has_required_size():
    yoga_count, cyber_count = topic_counts()
    assert yoga_count >= 100
    assert cyber_count >= 100


def test_short_topic_matches_whole_word_only():
    assert answer_domain_question("what is om")[0] == "knowledge:yoga_catalog"
    assert answer_domain_question("what is ransomware")[0] == "knowledge:cybersecurity_catalog"


def test_ai_catalog_answers_prompt_injection():
    result = answer_domain_question("what is prompt injection in an AI assistant")
    assert result is not None
    source, spoken = result
    assert source == "knowledge:ai_catalog"
    assert "prompt injection" in spoken.lower()


def test_ai_catalog_keeps_local_ai_privacy_specific():
    result = answer_domain_question("why can local AI be better for privacy than cloud AI")
    assert result is not None
    source, spoken = result
    assert source == "knowledge:ai_catalog"
    assert "own machine" in spoken.lower() or "cloud provider" in spoken.lower()
