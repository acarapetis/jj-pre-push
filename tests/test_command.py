from jj_pre_push.cli import checker_command


def test_command_pre_commit():
    assert checker_command("pre-commit") == ["pre-commit", "run", "--hook-stage", "pre-push"]


def test_command_prek():
    assert checker_command("prek") == ["prek", "run", "--hook-stage", "pre-push"]


def test_command_hk():
    assert checker_command("hk") == ["hk", "run", "pre-push"]
