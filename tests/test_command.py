from pathlib import Path

from jj_pre_push.cli import Settings, checker_command


def test_command_pre_commit():
    settings = Settings(checker="pre-commit", mode="default", config=None)
    assert checker_command(settings) == ["pre-commit", "run", "--hook-stage", "pre-push"]


def test_command_pre_commit_with_config():
    settings = Settings(checker="pre-commit", mode="default", config=Path("hooks.yaml"))
    assert checker_command(settings) == [
        "pre-commit",
        "run",
        "--hook-stage",
        "pre-push",
        "-c",
        "hooks.yaml",
    ]


def test_command_prek():
    settings = Settings(checker="prek", mode="default", config=None)
    assert checker_command(settings) == ["prek", "run", "--hook-stage", "pre-push"]


def test_command_prek_with_config():
    settings = Settings(checker="prek", mode="default", config=Path("hooks.yaml"))
    assert checker_command(settings) == [
        "prek",
        "run",
        "--hook-stage",
        "pre-push",
        "-c",
        "hooks.yaml",
    ]


def test_command_hk():
    settings = Settings(checker="hk", mode="default", config=None)
    assert checker_command(settings) == ["hk", "run", "pre-push"]


def test_command_hk_with_config():
    settings = Settings(checker="hk", mode="default", config=Path("hooks.yaml"))
    assert checker_command(settings) == ["hk", "run", "pre-push"]
