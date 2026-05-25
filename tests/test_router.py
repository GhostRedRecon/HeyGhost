from heyghost.routing import TurnRouter
from heyghost.skills.registry import SkillRegistry


def test_router_uses_exact_skill_before_model():
    route = TurnRouter(SkillRegistry()).route("what time is it")
    assert route.handled
    assert route.route == "time"


def test_router_uses_domain_catalog():
    route = TurnRouter(SkillRegistry()).route("what is spyware")
    assert route.handled
    assert route.route == "knowledge:cybersecurity_catalog"


def test_router_falls_back_when_unknown():
    route = TurnRouter(SkillRegistry()).route("tell me something vague and unusual")
    assert not route.handled
    assert route.route == "ollama_fallback"
