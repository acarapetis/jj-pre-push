import pytest

from jj_pre_push.cli import command


def test_command_pre_commit():
    assert command("pre-commit") == ["pre-commit", "run", "--hook-stage", "pre-push"]


def test_command_prek():
    assert command("prek") == ["prek", "run", "--hook-stage", "pre-push"]


def test_command_hk():
    assert command("hk") == ["hk", "run", "pre-push"]
