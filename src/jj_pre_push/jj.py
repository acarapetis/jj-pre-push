"""Utility functions for controlling the jj cli."""

from contextlib import contextmanager
import json
from pathlib import Path
import random
import string
import subprocess
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


def jj(args: list[str], snapshot: bool = True, suppress_stderr: bool = False):
    if not snapshot:
        args += ["--ignore-working-copy"]
    return (
        subprocess.check_output(
            ["jj", "--color", "never", *args],
            stderr=subprocess.DEVNULL if suppress_stderr else None,
        )
        .decode()
        .strip()
    )


class CommitRef(NamedTuple):
    name: str
    remote: str
    commit_id: str

    @property
    def local(self):
        return not self.remote


class Bookmark(NamedTuple):
    name: str
    target: list[str]
    remote: str | None = None
    tracking_target: list[str] | None = None


class TrackedBookmark(NamedTuple):
    name: str
    local_commit_id: str
    remote_commit_id: str

    def __str__(self):
        return f"{self.name} ({self.remote_commit_id[:7]}..{self.local_commit_id[:7]})"


def default_remote() -> str:
    """Get the name of the default git remote in the current jj repository; i.e. the
    remote that `jj git push` would push to."""
    # jj docs for --remote:
    #     This defaults to the `git.push` setting. If that is not configured, and if
    #     there are multiple remotes, the remote named "origin" will be used.
    try:
        return jj(["config", "get", "git.push"], suppress_stderr=True, snapshot=False)
    except subprocess.CalledProcessError:
        return "origin"


def pushable_bookmarks(
    remote: str, bookmark: str | None = None, all: bool = False
) -> list[TrackedBookmark]:
    """
    -b, --bookmark <BOOKMARK>
            Push only this bookmark, or bookmarks matching a pattern (can be repeated)

            By default, the specified name matches exactly. Use `glob:` prefix to select bookmarks by [wildcard pattern].

            [wildcard pattern]: https://jj-vcs.github.io/jj/latest/revsets#string-patterns

        --tracked
            Push all tracked bookmarks

            This usually means that the bookmark was already pushed to or fetched from the [relevant remote].

            [relevant remote]: https://jj-vcs.github.io/jj/latest/bookmarks#remotes-and-tracked-bookmarks
    """
    cmd = ["bookmark", "list", "--remote", remote, "-T", r'json(self) ++ "\n"']
    if all:
        cmd.append("--tracked")
    if bookmark:
        cmd.append(bookmark)

    local_bms = {}
    remote_bms = {}
    for line in jj(cmd, snapshot=False).splitlines():
        b = Bookmark(**json.loads(line))  # type: ignore
        (remote_bms if b.remote else local_bms)[b.name] = b

    results = []
    for b in remote_bms.values():
        if len(b.tracking_target) > 1:
            logger.debug(f"Bookmark {b.name}@{remote} is conflicted, ignoring")
            continue

        results.append(
            TrackedBookmark(
                name=b.name,
                local_commit_id=b.tracking_target[0],
                remote_commit_id=b.target[0],
            )
        )

    if all:
        # Find local bookmarks new to this remote
        for b in local_bms.values():
            if b.name not in remote_bms:
                results.append(
                    TrackedBookmark(
                        name=b.name,
                        local_commit_id=b.target[0],
                        remote_commit_id=b.target[0],
                    )
                )

    return [b for b in results if b.local_commit_id != b.remote_commit_id]


def default_bookmarks_to_push(remote: str) -> set[str]:
    """Get the names of all bookmarks that would be considered for pushing by `jj git push`."""
    # jj docs for git push:
    #     By default, pushes tracking bookmarks pointing to
    #     `remote_bookmarks(remote=<remote>)..@`
    revsets = f"bookmarks() & (remote_bookmarks(remote={json.dumps(remote)})..@)"
    return {
        json.loads(line)
        for line in jj(
            [
                "log",
                "--no-graph",
                "-r",
                revsets,
                "-T",
                'remote_bookmarks.map(|b| json(b.name())).join("\n") ++ "\n"',
            ],
            snapshot=False,
        ).splitlines()
    }


def workspace_root() -> Path:
    return Path(jj(["workspace", "root"], snapshot=False).strip())


def current_change_id() -> str:
    return jj(["log", "--no-graph", "-r", "@", "-T", "change_id"], snapshot=False)


def new(ref: str | None = None):
    cmd = ["new"]
    if ref:
        cmd.append(ref)
    jj(cmd)


@contextmanager
def stash_change():
    """Remember the working copy commit and return to it at the end of the context."""
    # Create a temporary bookmark so the current change isn't destroyed if it's empty
    tempbm = "jj-pre-push-keep-" + "".join(random.choices(string.ascii_letters, k=10))
    jj(["bookmark", "create", tempbm, "-r", "@"], suppress_stderr=True)
    try:
        yield
    finally:
        jj(["edit", tempbm], suppress_stderr=True)
        jj(["bookmark", "forget", tempbm], suppress_stderr=True)


def git_push(
    remote: str | None = None,
    bookmark: str | None = None,
    all: bool = False,
):
    cmd = ["git", "push"]
    if remote:
        cmd.extend(["--remote", remote])
    if bookmark:
        cmd.extend(["--bookmark", bookmark])
    if all:
        cmd.extend(["--all"])
    jj(cmd)
