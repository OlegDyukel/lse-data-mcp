"""Tests for the command-line entry point."""

import getpass

import pytest

from lse_data_mcp import cli, credentials


@pytest.fixture(autouse=True)
def no_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)


def test_no_subcommand_runs_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """An MCP client spawns the bare command, so it must still serve."""
    started: list[bool] = []
    monkeypatch.setattr(cli, "run_server", lambda: started.append(True))

    assert cli.main([]) == 0
    assert started == [True]


def test_login_stores_the_prompted_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stored: list[str] = []

    def record(key: str) -> str:
        stored.append(key)
        return "Backend"

    monkeypatch.setattr(cli, "_prompt_for_api_key", lambda: "prompted-key")
    monkeypatch.setattr(credentials, "store_api_key", record)

    assert cli.main(["login"]) == 0

    assert stored == ["prompted-key"]
    assert "Stored the API key in Backend." in capsys.readouterr().out


def test_login_never_echoes_the_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_prompt_for_api_key", lambda: "super-secret-key")
    monkeypatch.setattr(credentials, "store_api_key", lambda key: "Backend")

    cli.main(["login"])

    captured = capsys.readouterr()
    assert "super-secret-key" not in captured.out
    assert "super-secret-key" not in captured.err


def test_login_rejects_an_empty_entry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_prompt_for_api_key", lambda: "")

    assert cli.main(["login"]) == 1
    assert "Nothing was stored." in capsys.readouterr().err


def test_login_warns_when_the_environment_would_win(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LSE_API_KEY", "environment-key")
    monkeypatch.setattr(cli, "_prompt_for_api_key", lambda: "prompted-key")
    monkeypatch.setattr(credentials, "store_api_key", lambda key: "Backend")

    assert cli.main(["login"]) == 0
    assert "takes precedence" in capsys.readouterr().out


def test_login_reports_an_unusable_credential_store(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(key: str) -> str:
        raise credentials.CredentialStoreError("no usable credential store")

    monkeypatch.setattr(cli, "_prompt_for_api_key", lambda: "prompted-key")
    monkeypatch.setattr(credentials, "store_api_key", refuse)

    assert cli.main(["login"]) == 1
    assert "no usable credential store" in capsys.readouterr().err


def test_logout_removes_a_stored_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(credentials, "delete_stored_api_key", lambda: True)

    assert cli.main(["logout"]) == 0
    assert "Removed the stored API key." in capsys.readouterr().out


def test_logout_is_quiet_when_there_was_no_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(credentials, "delete_stored_api_key", lambda: False)

    assert cli.main(["logout"]) == 0
    assert "nothing to remove" in capsys.readouterr().out


def test_logout_reports_an_unusable_credential_store(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse() -> bool:
        raise credentials.CredentialStoreError("no usable credential store")

    monkeypatch.setattr(credentials, "delete_stored_api_key", refuse)

    assert cli.main(["logout"]) == 1
    assert "no usable credential store" in capsys.readouterr().err


def test_status_reports_the_environment_as_the_source(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LSE_API_KEY", "environment-key")

    assert cli.main(["status"]) == 0

    captured = capsys.readouterr().out
    assert "API key source: the LSE_API_KEY environment variable" in captured
    assert "environment-key" not in captured


def test_status_reports_the_credential_store_as_the_source(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        credentials,
        "read_credential",
        lambda: credentials.Credential(credentials.CredentialStatus.STORED, "stored-key"),
    )

    assert cli.main(["status"]) == 0

    captured = capsys.readouterr().out
    assert "API key source: this system's credential store" in captured
    assert "stored-key" not in captured


def test_status_fails_when_no_key_is_configured(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status"]) == 1
    assert "no API key is available" in capsys.readouterr().out


def test_the_prompt_hides_input_and_trims_it(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake_getpass(prompt: str) -> str:
        prompts.append(prompt)
        return "  typed-key  "

    monkeypatch.setattr(getpass, "getpass", fake_getpass)

    assert cli._prompt_for_api_key() == "typed-key"
    assert prompts == [cli._PROMPT]


def test_status_reports_an_unreachable_store_as_unknown_not_absent(
    capsys: pytest.CaptureFixture[str], inaccessible_credential_store: None
) -> None:
    """The misreport that sent a sandboxed agent chasing a key it had already stored."""
    assert cli.main(["status"]) == 1

    captured = capsys.readouterr().out
    assert "Key stored there: unknown - this process cannot reach the credential store" in captured
    assert "Key stored there: no" not in captured
    assert "cannot reach it" in captured


def test_status_reports_a_host_with_no_store_as_unknown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["status"]) == 1

    captured = capsys.readouterr().out
    assert "Key stored there: unknown - there is no credential store to ask" in captured
    assert "no credential store" in captured


def test_status_reports_a_reachable_empty_store_as_no(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        credentials,
        "read_credential",
        lambda: credentials.Credential(credentials.CredentialStatus.ABSENT, None),
    )

    assert cli.main(["status"]) == 1

    captured = capsys.readouterr().out
    assert "Key stored there: no" in captured
    assert "unknown" not in captured


def test_status_stays_quiet_about_the_store_when_the_environment_supplies_the_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    inaccessible_credential_store: None,
) -> None:
    """An unreachable store is not a problem worth reporting if the key came from elsewhere."""
    monkeypatch.setenv("LSE_API_KEY", "environment-key")

    assert cli.main(["status"]) == 0
    assert "cannot reach it" not in capsys.readouterr().out
