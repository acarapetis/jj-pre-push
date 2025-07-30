"""Utility functions for controlling the jj cli."""

import logging
import random
import string
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class JJError(Exception):
    message: str
    returncode: int


def jj(
    args: list[str],
    snapshot: bool = True,
    suppress_stderr: bool = False,
    capture_stderr: bool = False,
) -> str:
    """Run a `jj` CLI command and capture its output."""
    cmd = ["jj", *args]
    if not snapshot:
        cmd.extend(["--ignore-working-copy"])
    logger.debug(cmd)

    if capture_stderr:
        stderr = subprocess.STDOUT
    elif suppress_stderr:
        stderr = subprocess.PIPE  # still want to capture it for error reporting
    else:
        stderr = None  # let it go through to the terminal

    try:
        ret = subprocess.run(cmd, stderr=stderr, stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        raise JJError((e.stdout or b"").decode(), e.returncode) from e
    else:
        return ret.stdout.decode().strip()


def workspace_root() -> Path:
    return Path(jj(["workspace", "root"], snapshot=False).strip())


@dataclass(slots=True, frozen=True)
class ChangeSummary:
    change_id: str
    commit_id: str
    empty: bool


def current_change() -> ChangeSummary:
    return get_changes("@")[0]


def get_changes(revset: str) -> list[ChangeSummary]:
    template = r'empty ++ "," ++ change_id.shortest(8) ++ "," ++ commit_id.shortest(12) ++ "\n"'
    output = jj(["log", "--no-graph", "-r", revset, "-T", template])
    return [
        ChangeSummary(change_id=change_id, commit_id=commit_id, empty=empty == "true")
        for line in output.splitlines()
        for empty, change_id, commit_id in [line.split(",")]
    ]


def new(ref: str | None = None):
    cmd = ["new", "--quiet"]
    if ref:
        cmd.append(ref)
    jj(cmd)


@contextmanager
def autostash():
    """Remember the working copy commit and return to it at the end of the context."""
    # Create a temporary bookmark so the current change isn't automatically abandoned
    tempbm = "jj-pre-push-keep-" + "".join(random.choices(string.ascii_letters, k=10))
    jj(["bookmark", "create", tempbm, "-r", "@", "--quiet"])
    try:
        yield
    finally:
        jj(["edit", tempbm, "--quiet"])
        jj(["bookmark", "forget", tempbm, "--quiet"])
