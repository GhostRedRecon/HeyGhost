from heyghost.routing import TurnRouter
from heyghost.skills.arithmetic import maybe_answer_arithmetic
from heyghost.skills.registry import SkillRegistry


def test_arithmetic_answers_digit_question() -> None:
    result = maybe_answer_arithmetic("what is 1 plus 1")

    assert result == ("arithmetic", "1 plus 1 is 2.")


def test_arithmetic_answers_spoken_number_question() -> None:
    result = maybe_answer_arithmetic("what is one plus one")

    assert result == ("arithmetic", "1 plus 1 is 2.")


def test_router_handles_basic_arithmetic_before_model() -> None:
    route = TurnRouter(SkillRegistry()).route("what is 1 plus 1")

    assert route.handled
    assert route.route == "arithmetic"
    assert route.spoken_text == "1 plus 1 is 2."
