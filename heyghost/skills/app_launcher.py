from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

SAFE_SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "openai": "https://openai.com",
}

RESERVED_OPEN_TARGETS = {
    "a",
    "an",
    "ssh",
    "shell",
    "terminal",
    "door",
    "folder",
    "file",
    "files",
    "settings",
}

URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)
SSH_RE = re.compile(
    r"(?:ssh|open ssh|connect ssh|ssh to|ssh into)\s+"
    r"(?:(?P<user>[a-z0-9_.-]+)@)?"
    r"(?P<host>(?:\d{1,3}\.){3}\d{1,3}|[a-z0-9.-]+)"
    r"(?::(?P<port>\d{1,5}))?",
    re.IGNORECASE,
)
SEARCH_RE = re.compile(
    r"(?:search the web for|search web for|search for|look up|find on the web|browse for)\s+(.+)",
    re.IGNORECASE,
)


def maybe_build_action(text: str) -> dict[str, Any] | None:
    normalized = " ".join(text.lower().split())

    if "open browser" in normalized or "open the browser" in normalized:
        return {
            "kind": "browser",
            "message": "Opening the browser.",
        }

    if normalized in {"close browser", "close the browser"}:
        return {
            "kind": "close_app",
            "target": "browser",
            "message": "Closing the browser.",
        }

    if normalized in {"close terminal", "close the terminal"}:
        return {
            "kind": "close_app",
            "target": "terminal",
            "message": "Closing the terminal.",
        }

    if normalized in {"close window", "close this window", "close active window"}:
        return {
            "kind": "close_app",
            "target": "active",
            "message": "Closing the active window.",
        }

    if _looks_like_terminal_request(normalized):
        return {
            "kind": "terminal",
            "message": "Opening a terminal. What should I do in the terminal?",
        }

    if normalized in {"open ssh", "open ssh terminal", "start ssh", "ssh"}:
        return {
            "kind": "noop",
            "message": "Which SSH host should I connect to?",
        }

    ssh_action = _extract_ssh_action(normalized)
    if ssh_action is not None:
        return ssh_action

    search_action = _extract_search_action(normalized)
    if search_action is not None:
        return search_action

    if not any(
        phrase in normalized
        for phrase in (
            "open website",
            "open site",
            "go to ",
            "browse to ",
            "open ",
        )
    ):
        return None

    url = _extract_url(normalized)
    if not url:
        return None

    return {
        "kind": "website",
        "url": url,
        "message": f"Opening {url}.",
    }


def _extract_ssh_action(text: str) -> dict[str, Any] | None:
    match = SSH_RE.search(text)
    if not match:
        return None

    user = match.group('user')
    host = match.group('host')
    port = match.group('port')
    target = host
    if user:
        target = f'{user}@{host}'
    command = ['ssh']
    if port:
        command.extend(['-p', port])
    command.append(target)
    return {
        'kind': 'ssh',
        'target': target,
        'command': command,
        'message': f'Opening SSH session to {target}.',
    }


def _extract_search_action(text: str) -> dict[str, Any] | None:
    match = SEARCH_RE.search(text)
    if not match:
        return None

    query = match.group(1).strip()
    if not query:
        return None
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    return {
        'kind': 'search',
        'url': url,
        'query': query,
        'message': f'Searching the web for {query}.',
    }


def _extract_url(text: str) -> str | None:
    match = URL_RE.search(text)
    if match:
        url = match.group(1)
        if url.startswith("www."):
            return f"https://{url}"
        return url

    for name, url in SAFE_SITES.items():
        if re.search(rf"\b{name}\b", text):
            return url

    site_match = re.search(
        r"(?:open website|open site|go to|browse to|open)\s+([a-z0-9-]+)(?:\s+dot\s+([a-z]{2,6}))?",
        text,
    )
    if not site_match:
        return None

    host = site_match.group(1)
    if host in RESERVED_OPEN_TARGETS:
        return None
    if site_match.group(0).startswith("open ") and "dot" not in site_match.group(0):
        return None
    tld = site_match.group(2) or "com"
    return f"https://{host}.{tld}"


def _looks_like_terminal_request(text: str) -> bool:
    if any(
        phrase in text
        for phrase in (
            "open terminal",
            "open the terminal",
            "open a terminal",
            "launch terminal",
            "start terminal",
            "open shell",
            "open bash",
            "open a door",
            "open the door",
        )
    ):
        return True
    return False
