"""T022 - TLS verification is never disabled (FR-034).

A gate, not a unit test. The spec forbids skipping certificate verification
outright, and the tempting shortcut when a private CA fails to validate is
exactly `verify=False`. This makes that shortcut fail the build.
"""

import re
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "review_agent"

FORBIDDEN = [
    re.compile(r"verify\s*=\s*False"),
    re.compile(r"verify\s*=\s*0"),
    re.compile(r"REQUESTS_CA_BUNDLE\s*=\s*['\"]{2}"),
    re.compile(r"urllib3\.disable_warnings"),
    re.compile(r"InsecureRequestWarning"),
    re.compile(r"ssl\._create_unverified_context"),
    re.compile(r"CERT_NONE"),
]


def _python_sources():
    return sorted(AGENT_DIR.rglob("*.py"))


def test_agent_has_sources_to_scan():
    assert _python_sources(), "no agent sources found - the gate would pass vacuously"


def test_no_verification_bypass_anywhere():
    offenders = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line} {match.group(0)!r}")
    assert not offenders, "TLS verification bypass found: " + "; ".join(offenders)


def test_verify_argument_is_never_passed():
    """Even `verify=True` is a smell: it means someone was thinking about it."""
    offenders = []
    for path in _python_sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bverify\s*=", line) and "test" not in path.name:
                offenders.append(f"{path.name}:{number}")
    assert not offenders, "a verify= argument is passed at: " + "; ".join(offenders)


def test_truststore_is_a_declared_dependency():
    requirements = (AGENT_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "truststore" in requirements, (
        "truststore is what lets requests validate an internal CA; without it "
        "FR-034 is unsatisfiable except by disabling verification"
    )


def test_trust_injection_happens_before_a_session_exists():
    source = (AGENT_DIR / "tfs_client.py").read_text(encoding="utf-8")
    inject_at = source.index("inject_system_trust()", source.index("def __init__"))
    session_at = source.index("requests.Session()")
    assert inject_at < session_at, "trust must be injected before the session is built"


# --------------------------------------------------------------------------
# Feature 002 (T032): git is a second transport, and it has its own bypass.
#
# `git -c http.sslVerify=false` is the exact analogue of `verify=False`, and the
# same private-CA frustration produces it. git on Windows validates against the
# machine trust store - the same store truststore points requests at - so the
# shortcut is never needed here either.
# --------------------------------------------------------------------------

GIT_FORBIDDEN = [
    re.compile(r"sslVerify"),
    re.compile(r"GIT_SSL_NO_VERIFY"),
    re.compile(r"--no-check-certificate"),
]


def test_git_certificate_verification_is_never_disabled():
    offenders = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        for pattern in GIT_FORBIDDEN:
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line} {match.group(0)!r}")
    assert not offenders, "git TLS bypass found: " + "; ".join(offenders)
