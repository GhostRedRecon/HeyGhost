from __future__ import annotations

from heyghost.app import build_parser


def test_cli_accepts_doctor_command() -> None:
    args = build_parser().parse_args(["doctor"])

    assert args.command == "doctor"
