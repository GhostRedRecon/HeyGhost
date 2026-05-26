from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path


TEST_MODULES = (
    "tests.test_transcript_filter",
    "tests.test_command_grammar",
    "tests.test_router",
    "tests.test_domain_catalog",
    "tests.test_response_policy",
    "tests.test_linux_system",
    "tests.test_structured_llm",
    "tests.test_rag",
    "tests.test_self_echo",
    "tests.test_attention_gate",
)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    passed = 0
    for module_name in TEST_MODULES:
        module = importlib.import_module(module_name)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            func()
            print(f"PASS {module_name}.{name}")
            passed += 1
    print(f"{passed} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
