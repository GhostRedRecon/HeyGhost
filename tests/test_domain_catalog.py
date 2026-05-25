from heyghost.skills.domain_catalog import answer_domain_question, topic_counts


def test_domain_catalog_has_required_size():
    yoga_count, cyber_count = topic_counts()
    assert yoga_count >= 100
    assert cyber_count >= 100


def test_short_topic_matches_whole_word_only():
    assert answer_domain_question("what is om")[0] == "knowledge:yoga_catalog"
    assert answer_domain_question("what is ransomware")[0] == "knowledge:cybersecurity_catalog"
