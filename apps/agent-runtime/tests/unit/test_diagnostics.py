import logging

from agent_runtime.api.internal.dependencies import build_runtime
from agent_runtime.config.settings import Settings
from agent_runtime.infrastructure.diagnostics import describe_error, log_unexpected

SECRET = "student-text-or-secret-sentinel"


def _inner():
    raise KeyError(SECRET)


def _outer():
    try:
        _inner()
    except KeyError as error:
        raise RuntimeError(SECRET) from error


def test_describes_type_and_location_but_never_the_message():
    try:
        _outer()
    except RuntimeError as error:
        text = describe_error(error)
    assert SECRET not in text
    assert text.startswith("RuntimeError at test_diagnostics.py:")
    assert ":_outer" in text and "caused by KeyError at" in text and ":_inner" in text


def test_a_cause_hidden_with_from_none_stays_hidden():
    try:
        try:
            _inner()
        except KeyError:
            raise ValueError(SECRET) from None
    except ValueError as error:
        assert "KeyError" not in describe_error(error)


def test_log_unexpected_writes_one_error_line(caplog):
    caplog.set_level(logging.ERROR)
    try:
        _inner()
    except KeyError as error:
        log_unexpected(logging.getLogger("test"), "turn failed", error)
    assert [record.levelno for record in caplog.records] == [logging.ERROR]
    assert caplog.records[0].getMessage().startswith("turn failed: KeyError at")
    assert SECRET not in caplog.text


def test_build_runtime_names_the_unreadable_keyring_without_its_value(caplog):
    caplog.set_level(logging.ERROR)
    assert build_runtime(Settings(_env_file=None, RUNTIME_INTERNAL_KEYRING=SECRET)) is None
    assert "RUNTIME_INTERNAL_KEYRING unreadable" in caplog.text
    assert SECRET not in caplog.text


def test_build_runtime_says_when_the_database_is_not_configured(caplog):
    caplog.set_level(logging.ERROR)
    keyring = '{"k1": "' + "A" * 44 + '"}'
    runtime = build_runtime(Settings(_env_file=None, RUNTIME_INTERNAL_KEYRING=keyring, RUNTIME_DATABASE_URL=None))
    assert runtime is not None and runtime.policy is None
    assert "RUNTIME_DATABASE_URL is not set" in caplog.text
