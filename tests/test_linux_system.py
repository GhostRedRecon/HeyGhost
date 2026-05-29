from heyghost.skills.linux_system import maybe_linux_skill
from heyghost.skills.qa_bank import answer_qa_bank
from heyghost.skills.qa_bank import qa_counts


def test_qa_bank_has_500_entries():
    cyber, linux, total = qa_counts()
    assert cyber >= 250
    assert linux >= 250
    assert total >= 500


def test_linux_app_terminal_is_whitelisted():
    result = maybe_linux_skill("open terminal")
    assert result is not None
    source, spoken, action = result
    assert source == "linux:open_terminal"
    assert action is not None
    assert action["kind"] == "terminal"
    assert "prompt" in action
    assert "terminal" in spoken.lower()
    assert "command" in spoken.lower()


def test_linux_hardware_skill_answers():
    result = maybe_linux_skill("tell me about this hardware")
    assert result is not None
    source, spoken, action = result
    assert source == "linux:hardware"
    assert action is None
    assert "kernel" in spoken.lower() or "ram" in spoken.lower()


def test_linux_usb_skill_answers():
    result = maybe_linux_skill("what is connected to the usb")
    assert result is not None
    source, spoken, action = result
    assert source == "linux:usb_devices"
    assert action is None
    assert "usb" in spoken.lower()


def test_linux_tools_skill_answers():
    result = maybe_linux_skill("what tools are there in linux")
    assert result is not None
    source, spoken, action = result
    assert source == "linux:tools"
    assert action is None
    assert "tools" in spoken.lower()


def test_qa_bank_answers_what_is_linux():
    result = answer_qa_bank("what is linux")
    assert result is not None
    source, spoken = result
    assert source == "qa_bank:linux"
    assert "operating system" in spoken.lower()


def test_qa_bank_answers_what_is_cybersecurity():
    result = answer_qa_bank("what is cybersecurity")
    assert result is not None
    source, spoken = result
    assert source == "qa_bank:cybersecurity"
    assert "protect" in spoken.lower() or "security" in spoken.lower()


def test_prompt_injection_does_not_match_sql_injection():
    result = answer_qa_bank("what is prompt injection in an ai assistant")
    assert result is None or "sql injection" not in result[1].lower()
