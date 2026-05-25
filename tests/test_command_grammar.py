from heyghost.skills.command_grammar import canonicalize_command
from heyghost.skills.registry import SkillRegistry


def test_command_grammar_exact_capabilities_alias():
    match = canonicalize_command("what are your capablties")
    assert match is not None
    assert match.text == "what are your capabilities"
    assert match.intent == "capabilities"

    match = canonicalize_command("what are your capblities")
    assert match is not None
    assert match.text == "what are your capabilities"
    assert match.intent == "capabilities"


def test_command_grammar_fuzzy_capabilities_alias():
    match = canonicalize_command("what are you kiwi b")
    assert match is not None
    assert match.text == "what are your capabilities"


def test_registry_routes_fuzzy_capabilities_before_model():
    result = SkillRegistry().maybe_handle("what are you kiwi b")
    assert result is not None
    assert result.source == "capabilities"


def test_command_grammar_preserves_rag_query_suffix():
    match = canonicalize_command("search local knowledge for usb microphone")
    assert match is not None
    assert match.text == "search your local knowledge for usb microphone"


def test_command_grammar_does_not_capture_unknown_sentence():
    assert canonicalize_command("tell me something vague and unusual") is None


def test_command_grammar_usb_alias():
    match = canonicalize_command("what usb devices are connected")
    assert match is not None
    assert match.text == "what is connected to the usb"


def test_command_grammar_usb_stt_misrecognition_alias():
    match = canonicalize_command("what is coming through today usb")
    assert match is not None
    assert match.text == "what is connected to the usb"


def test_command_grammar_linux_tools_alias():
    match = canonicalize_command("what linux tools are there")
    assert match is not None
    assert match.text == "what tools are there in linux"


def test_terminal_mode_maps_basic_linux_commands():
    registry = SkillRegistry()
    result = registry.maybe_handle("open terminal")
    assert result is not None
    assert result.source == "linux:open_terminal"

    result = registry.maybe_handle("list files")
    assert result is not None
    assert result.source == "terminal_input"
    action = result.metadata.get("action")
    assert action is not None
    assert action["kind"] == "terminal_input"
    assert action["text"] == "ls"

    result = registry.maybe_handle("show disk space")
    assert result is not None
    action = result.metadata.get("action")
    assert action is not None
    assert action["text"] == "df -h"


def test_basic_linux_demo_commands_route_to_terminal_without_mode():
    registry = SkillRegistry()
    cases = {
        "list files": "ls",
        "list all files": "ls -la",
        "show disk space": "df -h",
        "short disk space": "df -h",
        "show memory": "free -h",
        "show processes": "ps aux",
        "show network address": "ip -brief address",
        "list disks": "lsblk",
    }
    for phrase, command in cases.items():
        result = registry.maybe_handle(phrase)
        assert result is not None
        assert result.source == "terminal_input"
        action = result.metadata.get("action")
        assert action is not None
        assert action["text"] == command



def test_public_build_does_not_route_unknown_tool_aliases():
    registry = SkillRegistry()
    for phrase in ("run unknown scanner", "open unknown framework"):
        result = registry.maybe_handle(phrase)
        assert result is None or result.source != "terminal_input"


def test_close_terminal_routes_to_desktop_close_action():
    for phrase in ("close terminal", "close that mean that", "close birmingham", "close the window"):
        result = SkillRegistry().maybe_handle(phrase)
        assert result is not None
        assert result.source == "action"
        action = result.metadata.get("action")
        assert action is not None
        assert action["kind"] == "close_app"
        assert action["target"] == "terminal"


def test_requested_demo_phrases_route_deterministically():
    registry = SkillRegistry()
    cases = {
        "open terminal": ("linux:open_terminal", "terminal"),
        "open the terminal": ("linux:open_terminal", "terminal"),
        "open up the terminal": ("linux:open_terminal", "terminal"),
        "open that data menu": ("linux:open_terminal", "terminal"),
        "open the window": ("linux:open_terminal", "terminal"),
        "open our terminal": ("linux:open_terminal", "terminal"),
        "close terminal": ("action", "close_app"),
        "show disk space": ("terminal_input", "terminal_input"),
        "show ram": ("memory", None),
        "which cpu": ("cpu", None),
        "what operating system": ("os", None),
        "what devices are connected to usb": ("linux:usb_devices", None),
    }
    for phrase, (source, action_kind) in cases.items():
        result = registry.maybe_handle(phrase)
        assert result is not None
        assert result.source == source
        action = result.metadata.get("action")
        if action_kind is None:
            assert action is None
        else:
            assert action is not None
            assert action["kind"] == action_kind
