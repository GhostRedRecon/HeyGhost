# Security Policy

## Educational And Authorized Use

HeyGhost is provided for educational, research, and authorized personal automation use only. Do not use it for unauthorized access, credential theft, malware activity, network abuse, or illegal activity.

## Supported Versions

Security updates are handled on the default branch until formal releases are created.

## Reporting A Vulnerability

Please open a private security advisory on GitHub if available, or create an issue with minimal public detail and request maintainer contact. Do not publish exploit details for an unresolved vulnerability.

When reporting, include:

- Affected file or component.
- Steps to reproduce.
- Expected and actual behavior.
- Impact and suggested fix if known.

## Security Design Goals

- Local-first operation.
- No cloud dependency for the core voice loop.
- LLM output is never treated as executable code.
- Local skills are explicit Python code paths.
- Risky manual console commands require confirmation.
- Public defaults avoid offensive-tool launch aliases.
