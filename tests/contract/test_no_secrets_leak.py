"""T021 - no credential reaches any output path (FR-006, SC-004).

The realistic leak is never a deliberate print of a token. It is an exception
message, a repr of a request, or a debug dump that happens to carry a header. So
this asserts on the *values*, through the one path everything printed must use.
"""

import pytest

from review_agent import config as cfg
from review_agent.errors import SetupFailure

PAT = "pat-secret-value"
KEY = "llm-secret-value"


@pytest.fixture(autouse=True)
def _clean_registry():
    cfg.clear_secrets()
    yield
    cfg.clear_secrets()


def test_registered_secrets_are_redacted():
    cfg.register_secret(PAT)
    assert cfg.redact(f"Authorization: Basic {PAT}") == "Authorization: Basic ***"


def test_redaction_covers_every_occurrence():
    cfg.register_secret(PAT)
    out = cfg.redact(f"{PAT} then {PAT}")
    assert PAT not in out
    assert out.count("***") == 2


def test_longer_secrets_are_replaced_first():
    """A short secret inside a long one must not leave a fragment behind."""
    cfg.register_secret("abcdefgh")
    cfg.register_secret("abcdefgh-plus-more")
    out = cfg.redact("token=abcdefgh-plus-more")
    assert "abcdefgh" not in out


def test_trivially_short_values_are_not_registered():
    """Registering "1" would turn all output into a wall of asterisks."""
    cfg.register_secret("abc")
    assert cfg.redact("abc") == "abc"


def test_loading_config_registers_both_secrets(base_env):
    cfg.load_config()
    assert cfg.redact(PAT) == "***"
    assert cfg.redact(KEY) == "***"


def test_emit_redacts(base_env, capsys):
    cfg.load_config()
    cfg.emit(f"about to call with {PAT}")
    assert PAT not in capsys.readouterr().out


def test_emit_error_redacts(base_env, capsys):
    cfg.load_config()
    cfg.emit_error(f"failed using {KEY}")
    assert KEY not in capsys.readouterr().err


def test_config_repr_and_str_hide_secrets(base_env):
    c = cfg.load_config()
    for rendering in (repr(c), str(c), f"{c}"):
        assert PAT not in rendering
        assert KEY not in rendering


def test_full_run_output_contains_no_secret(base_env, capsys, monkeypatch):
    """A whole invocation, including the failure path, stays clean."""
    from review_agent import main as main_module

    monkeypatch.setattr(
        main_module, "load_config", lambda **kw: (_ for _ in ()).throw(
            SetupFailure(f"boom while using {PAT} and {KEY}")
        )
    )
    cfg.register_secret(PAT)
    cfg.register_secret(KEY)
    exit_code = main_module.main(["--dry-run"])
    captured = capsys.readouterr()
    assert exit_code == 2
    for stream in (captured.out, captured.err):
        assert PAT not in stream
        assert KEY not in stream


def test_auth_header_is_not_stored_in_a_loggable_attribute(base_env):
    """The header exists on the session, but nothing formats it into a message."""
    import re
    from pathlib import Path

    agent_dir = Path(__file__).resolve().parents[2] / "review_agent"
    for path in agent_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"(emit|print|log)\w*\(.*(Authorization|headers|tfs_token|api_key)", line):
                pytest.fail(f"{path.name}:{number} formats a credential into output")


# --------------------------------------------------------------------------
# Feature 002 (T031): a credential now also reaches a child process.
#
# Cloning needs the PAT, and the three obvious ways of giving it to git all
# leak: in the URL it lands in the clone's .git/config, in `-c http.extraHeader`
# it lands in an argument list every process on the machine can read, and in a
# credential helper it lands in the user's home directory. Only the environment
# of the child is private to the run - so that is the one carrier, and these
# tests fix it there.
# --------------------------------------------------------------------------

POST_PAT = "post-secret-value"


def test_both_tokens_are_registered_for_redaction(base_env):
    from review_agent.config import load_config

    load_config()
    assert cfg.redact(f"{PAT} {POST_PAT}") == "*** ***"


def test_no_credential_reaches_a_git_argument_list(base_env, tmp_path):
    from review_agent import source_fetch
    from review_agent.config import load_config

    config = load_config()
    calls = []

    def runner(args, env=None, cwd=None, **kwargs):
        calls.append({"args": list(args), "env": dict(env or {})})

        class _R:
            returncode = 0
            stdout = "abc1234"
            stderr = ""

        return _R()

    source_fetch.clone(config, "Repo", into=str(tmp_path), runner=runner)
    assert calls, "expected git to be invoked"
    for call in calls:
        for arg in call["args"]:
            assert PAT not in arg, "a token in argv is world-readable on this machine"
            assert POST_PAT not in arg


def test_the_posting_credential_never_reaches_git_at_all(base_env, tmp_path):
    """Cloning is a reading operation; the posting token has no business here."""
    from review_agent import source_fetch
    from review_agent.config import load_config

    config = load_config()
    seen = []

    def runner(args, env=None, cwd=None, **kwargs):
        seen.append(dict(env or {}))

        class _R:
            returncode = 0
            stdout = "abc1234"
            stderr = ""

        return _R()

    source_fetch.clone(config, "Repo", into=str(tmp_path), runner=runner)
    for env in seen:
        assert POST_PAT not in env.values()


def test_exactly_one_environment_variable_carries_the_token(base_env, tmp_path):
    from review_agent import source_fetch
    from review_agent.config import load_config

    config = load_config()
    captured = {}

    def runner(args, env=None, cwd=None, **kwargs):
        captured.update(env or {})

        class _R:
            returncode = 0
            stdout = "abc1234"
            stderr = ""

        return _R()

    source_fetch.clone(config, "Repo", into=str(tmp_path), runner=runner)

    # Feature 003 (R13): the credential now travels in TWO variables and two
    # forms - the raw token for askpass, and its base64 Basic encoding for the
    # header this collection requires. Both are checked, because asserting only
    # on the raw form would let the encoded one spread unnoticed.
    import base64

    encoded = base64.b64encode(f":{PAT}".encode("utf-8")).decode("ascii")
    carriers = sorted(k for k, v in captured.items() if PAT in str(v) or encoded in str(v))
    expected = sorted([source_fetch.TOKEN_ENV, source_fetch.HEADER_CONFIG_ENV[2]])
    assert carriers == expected, (
        f"the credential must travel in {expected} alone, found {carriers}"
    )


def test_a_git_failure_message_is_redacted_before_it_is_emitted(base_env, capsys):
    """git's stderr is not trusted: it is printed through the redaction path."""
    from review_agent.config import load_config

    load_config()
    cfg.emit_error(f"fatal: authentication failed for https://x:{PAT}@host/repo")
    captured = capsys.readouterr()
    assert PAT not in captured.err
    assert "***" in captured.err


def test_the_helper_script_embeds_no_secret(tmp_path):
    from review_agent import source_fetch

    path = source_fetch._write_askpass(str(tmp_path))
    content = open(path, encoding="ascii").read()
    assert PAT not in content
    assert POST_PAT not in content


# --------------------------------------------------------------------------
# T057 follow-up (feature 003, R13): the header form is a credential too.
#
# Added after the live run, where the askpass route failed and an Authorization
# header had to be presented unasked. The encoded form is exactly as sensitive as
# the raw one and is far easier to let slip, because it does not *look* like a
# token.
# --------------------------------------------------------------------------


def test_the_encoded_credential_never_reaches_a_git_argument_list(base_env, tmp_path):
    import base64

    from review_agent import source_fetch
    from review_agent.config import load_config

    config = load_config()
    encoded = base64.b64encode(f":{PAT}".encode("utf-8")).decode("ascii")
    seen = []

    def runner(args, env=None, cwd=None, **kwargs):
        seen.extend(args)

        class _R:
            returncode = 0
            stdout = "abc1234"
            stderr = ""

        return _R()

    source_fetch.clone(config, "Repo", into=str(tmp_path), runner=runner)
    for argument in seen:
        assert PAT not in argument
        assert encoded not in argument


def test_the_encoded_credential_is_registered_as_unprintable(base_env):
    """An error message that echoed the header would leak just as completely."""
    from review_agent import source_fetch
    from review_agent.config import redact

    header = source_fetch.basic_auth_header(PAT)
    assert PAT not in redact(header)
    assert redact(f"git failed: {header}") == "git failed: ***"


def test_no_credential_is_written_beside_the_working_copy(base_env, tmp_path):
    """Neither form may reach the askpass helper, or any other file on disk."""
    import base64

    from review_agent import source_fetch
    from review_agent.config import load_config

    config = load_config()
    encoded = base64.b64encode(f":{PAT}".encode("utf-8")).decode("ascii")

    def runner(args, env=None, cwd=None, **kwargs):
        class _R:
            returncode = 0
            stdout = "abc1234"
            stderr = ""

        return _R()

    source_fetch.clone(config, "Repo", into=str(tmp_path), runner=runner)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
            assert PAT not in content
            assert encoded not in content
