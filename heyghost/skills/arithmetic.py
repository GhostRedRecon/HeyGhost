from __future__ import annotations

import ast
import operator
import re
from fractions import Fraction
from typing import Callable


_OPERATORS: dict[type[ast.operator], Callable[[Fraction, Fraction], Fraction]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_QUESTION_PREFIXES = (
    "what is",
    "whats",
    "what's",
    "calculate",
    "compute",
    "solve",
)


def maybe_answer_arithmetic(text: str) -> tuple[str, str] | None:
    expression = _spoken_expression(text)
    if expression is None:
        return None
    try:
        value = _evaluate(expression)
    except (ArithmeticError, ValueError, SyntaxError):
        return None
    return "arithmetic", f"{_format_expression(expression)} is {_format_value(value)}."


def _spoken_expression(text: str) -> str | None:
    normalized = text.lower().strip()
    normalized = re.sub(r"[^a-z0-9.+\-*/x ]+", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return None

    for prefix in _QUESTION_PREFIXES:
        if normalized.startswith(prefix + " "):
            normalized = normalized.removeprefix(prefix).strip()
            break

    replacements = {
        "divided by": "/",
        "over": "/",
        "multiplied by": "*",
        "times": "*",
        "x": "*",
        "plus": "+",
        "add": "+",
        "minus": "-",
        "subtract": "-",
    }
    for word, value in _NUMBER_WORDS.items():
        normalized = re.sub(rf"\b{word}\b", str(value), normalized)
    for phrase, symbol in replacements.items():
        normalized = re.sub(rf"\b{re.escape(phrase)}\b", symbol, normalized)

    normalized = normalized.replace(" ", "")
    if not re.fullmatch(r"[0-9.+\-*/()]+", normalized):
        return None
    if not re.search(r"\d\s*[+\-*/]\s*\d", normalized):
        return None
    return normalized


def _evaluate(expression: str) -> Fraction:
    if len(expression) > 80:
        raise ValueError("expression too long")
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand)
    if isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("operator not allowed")
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ArithmeticError("division by zero")
        return op(_eval_node(node.left), right)
    raise ValueError("expression not allowed")


def _format_expression(expression: str) -> str:
    return (
        expression.replace("*", " times ")
        .replace("/", " divided by ")
        .replace("+", " plus ")
        .replace("-", " minus ")
        .replace("  ", " ")
        .strip()
    )


def _format_value(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    decimal = value.numerator / value.denominator
    return f"{decimal:.4f}".rstrip("0").rstrip(".")
