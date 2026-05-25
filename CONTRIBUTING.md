# Contributing To HeyGhost

Thanks for helping improve HeyGhost. Keep changes practical, safe, and easy to test on Linux.

## Development Setup

```bash
git clone https://github.com/GhostRedRecon/HeyGhost.git
cd HeyGhost
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 tests/run_tests.py
```

## Pull Request Checklist

Before opening a pull request:

- Run `python3 tests/run_tests.py`.
- Keep public defaults safe and local-first.
- Do not add secrets, API keys, model files, generated audio, logs, or cache files.
- Avoid hardcoded user-specific paths.
- Document new dependencies or setup steps in `README.md`.
- Add or update tests when changing routing, filters, config, or skills.

## Safety Rules

Do not contribute features that enable unauthorized access, malware activity, credential theft, evasion, phishing, persistence, or harmful automation. Cybersecurity content must remain defensive, educational, and authorized.

## Code Style

- Prefer simple Python and explicit local skills.
- Keep configuration in YAML or environment variables.
- Keep voice responses short by default.
- Avoid adding heavy dependencies unless they are necessary.
