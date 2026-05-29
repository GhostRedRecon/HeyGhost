from __future__ import annotations

import re


CYBER_TOPICS: dict[str, str] = {
    "cybersecurity": "Cybersecurity is the practice of protecting computers, networks, accounts, and data from unauthorized access, misuse, or damage.",
    "phishing": "Phishing is a trick that uses fake messages or sites to steal information. Verify senders, avoid surprise links, and use MFA.",
    "ransomware": "Ransomware locks or steals data for payment. Defend with tested backups, patching, MFA, and least privilege.",
    "spyware": "Spyware secretly monitors activity or steals data. Avoid untrusted downloads, review permissions, and keep systems updated.",
    "malware": "Malware is harmful software. Reduce risk with patching, safe downloads, endpoint protection, and limited privileges.",
    "firewall": "A firewall filters network traffic. Use it to expose only needed services and block unwanted connections.",
    "vpn": "A VPN encrypts traffic to a VPN provider. It helps on untrusted networks but does not make all activity anonymous.",
    "mfa": "MFA adds another proof beyond a password. App codes, passkeys, and hardware keys are stronger than SMS.",
    "password manager": "A password manager helps create and store unique passwords, reducing damage from password reuse.",
    "passkey": "A passkey is a phishing-resistant login method using public-key cryptography instead of reusable passwords.",
    "zero trust": "Zero trust means verify explicitly, limit access, and assume no network is automatically trusted.",
    "least privilege": "Least privilege gives users and services only the access they need, limiting damage from compromise.",
    "patching": "Patching fixes known software weaknesses. Prioritize internet-facing systems and actively exploited vulnerabilities.",
    "encryption": "Encryption protects data by making it unreadable without the right key.",
    "hashing": "Hashing creates a fixed fingerprint of data. Password hashes should use salts and slow password-hashing algorithms.",
    "incident response": "Incident response detects, contains, eradicates, and recovers from security events using a practiced plan.",
    "siem": "A SIEM collects and analyzes logs to help detect and investigate suspicious activity.",
    "soc": "A SOC monitors alerts, investigates threats, and coordinates defensive response.",
    "edr": "EDR monitors endpoints for suspicious behavior and helps contain or investigate attacks.",
    "sql injection": "SQL injection happens when untrusted input changes database queries. Use parameterized queries.",
    "xss": "XSS injects script into web pages. Defend with output encoding, safe frameworks, and content security policy.",
    "csrf": "CSRF tricks a browser into sending unwanted actions. SameSite cookies and CSRF tokens help defend.",
    "ssrf": "SSRF abuses a server into making unintended requests. Use allowlists and protect metadata services.",
    "ssh security": "Secure SSH with keys, limited exposure, disabled password login where possible, MFA, and logs.",
    "wifi security": "Use WPA2 or WPA3, strong passwords, firmware updates, and guest networks for untrusted devices.",
    "backup security": "Backups should be tested, protected from ransomware, and stored offline or immutably when possible.",
}


LINUX_TOPICS: dict[str, str] = {
    "linux": "Linux is a free, open-source operating system family built around the Linux kernel. It powers servers, desktops, phones, embedded devices, and many security tools because it is stable, flexible, and highly configurable.",
    "kernel": "The Linux kernel manages hardware, processes, memory, filesystems, drivers, and networking.",
    "shell": "A shell is a command interface. Bash and zsh let users run commands, scripts, and pipelines.",
    "terminal": "A terminal is a text interface to the shell. HeyGhost can open a whitelisted terminal window.",
    "systemd": "systemd manages Linux services, boot targets, logs, timers, and service supervision.",
    "journalctl": "journalctl reads systemd logs. Use it to inspect service errors and boot messages.",
    "process": "A process is a running program. Tools like ps, top, and systemctl show process and service state.",
    "permissions": "Linux permissions control read, write, and execute access for users, groups, and others.",
    "sudo": "sudo runs allowed commands with elevated privileges. It should be logged and used carefully.",
    "apt": "apt installs, updates, and removes Debian or Kali packages from configured repositories.",
    "networkmanager": "NetworkManager manages Wi-Fi, Ethernet, VPNs, and network profiles on many Linux desktops.",
    "ip address": "The ip command shows interfaces, addresses, routes, and neighbors. HeyGhost can report active IP addresses.",
    "ip neigh": "ip neigh shows the local ARP or neighbor cache, useful for known local devices.",
    "nmcli": "nmcli is NetworkManager's command-line tool for Wi-Fi, connections, and device status.",
    "filesystem": "Linux filesystems organize files under one tree starting at slash, with devices mounted into directories.",
    "mount": "Mounting attaches a filesystem to a directory. The mount and findmnt commands show mounted filesystems.",
    "disk usage": "Disk usage can be checked with df for filesystems and du for directory sizes.",
    "memory": "Linux memory status is visible in /proc/meminfo, free, top, and system monitors.",
    "cpu": "CPU details are visible in /proc/cpuinfo, lscpu, and system monitors.",
    "logs": "Logs help diagnose issues. systemd services usually log through journald and sometimes files under /var/log.",
    "services": "Linux services are background programs managed by systemd. Use systemctl status to inspect them.",
    "environment variables": "Environment variables pass configuration to processes, such as PATH, HOME, DISPLAY, and LANG.",
    "path": "PATH lists directories searched for commands. If a command is not found, PATH may not include its location.",
    "package updates": "Package updates fix bugs and security issues. On Kali, apt update refreshes metadata and apt upgrade applies upgrades.",
    "kali linux": "Kali Linux is a Debian-based security distribution with many defensive and testing tools.",
    "alsa": "ALSA is the Linux audio layer HeyGhost uses for playback through aplay and configured output devices.",
}


QUESTION_VARIANTS = (
    "what is {topic}",
    "explain {topic}",
    "define {topic}",
    "tell me about {topic}",
    "how does {topic} work",
    "why is {topic} important",
    "what should I know about {topic}",
    "give me basics of {topic}",
    "what are safe practices for {topic}",
    "how do I understand {topic}",
)


def answer_qa_bank(text: str) -> tuple[str, str] | None:
    normalized = _normalize(text)
    for topic, answer in {**CYBER_TOPICS, **LINUX_TOPICS}.items():
        if _topic_matches(normalized, topic):
            domain = "cybersecurity" if topic in CYBER_TOPICS else "linux"
            return f"qa_bank:{domain}", answer
    return None


def qa_counts() -> tuple[int, int, int]:
    cyber_count = len(CYBER_TOPICS) * len(QUESTION_VARIANTS)
    linux_count = len(LINUX_TOPICS) * len(QUESTION_VARIANTS)
    return cyber_count, linux_count, cyber_count + linux_count


def sample_questions(limit: int = 20) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for topics in (CYBER_TOPICS, LINUX_TOPICS):
        for topic, answer in topics.items():
            for variant in QUESTION_VARIANTS:
                rows.append((variant.format(topic=topic), answer))
                if len(rows) >= limit:
                    return rows
    return rows


def _topic_matches(text: str, topic: str) -> bool:
    padded = f" {text} "
    if f" {topic} " in padded:
        return True
    topic_words = topic.split()
    if len(topic_words) > 1:
        words = [word for word in topic_words if len(word) >= 3]
        return bool(words) and all(f" {word} " in padded for word in words)
    words = [word for word in topic_words if len(word) >= 4]
    return bool(words) and all(f" {word} " in padded for word in words)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())
