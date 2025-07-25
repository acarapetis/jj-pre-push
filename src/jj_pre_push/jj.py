from contextlib import contextmanager
import json
import random
import string
import subprocess
import logging
from typing import Any, Iterable, NamedTuple

logger = logging.getLogger(__name__)


def jj_json(
    args: list[str],
    return_fields: Iterable[str],
    snapshot: bool = False,
) -> list[list[str | dict[str, Any]]]:
    template = (
        r'"[" ++ '
        + r' ++ "," ++ '.join(f"json({part})" for part in return_fields)
        + r' ++ "]\n"'
    )
    output = jj([*args, "-T", template], snapshot=snapshot)
    return [json.loads(line) for line in output.splitlines()]


def jj(args: list[str], snapshot: bool = False, suppress_stderr: bool = False):
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
    cmd = ["bookmark", "list", "--remote", remote]
    if all:
        cmd.append("--tracked")
    if bookmark:
        cmd.append(bookmark)

    local_bms = {}
    remote_bms = {}
    for [data] in jj_json(cmd, return_fields=["self"]):
        bm = Bookmark(**data)  # type: ignore
        (remote_bms if bm.remote else local_bms)[bm.name] = bm

    results = []
    for bm in remote_bms.values():
        if len(bm.tracking_target) > 1:
            logger.debug(f"Bookmark {bm.name}@{remote} is conflicted, ignoring")
            continue

        results.append(
            TrackedBookmark(
                name=bm.name,
                local_commit_id=bm.tracking_target[0],
                remote_commit_id=bm.target[0],
            )
        )

    if all:
        # Find local bookmarks new to this remote
        for bm in local_bms.values():
            if bm.name not in remote_bms:
                results.append(
                    TrackedBookmark(
                        name=bm.name,
                        local_commit_id=bm.target[0],
                        remote_commit_id=bm.target[0],
                    )
                )

    return results


def default_remote() -> str:
    """Get the name of the default git remote in the current jj repository; i.e. the
    remote that `jj git push` would push to."""
    # jj docs for --remote:
    #     This defaults to the `git.push` setting. If that is not configured, and if
    #     there are multiple remotes, the remote named "origin" will be used.
    try:
        return jj(["config", "get", "git.push"], suppress_stderr=True)
    except subprocess.CalledProcessError:
        return "origin"


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
            ]
        ).splitlines()
    }


def workspace_root() -> str:
    return jj(["workspace", "root"])


def current_change_id() -> str:
    return jj(["log", "--no-graph", "-r", "@", "-T", "change_id"])


@contextmanager
def checkout(ref: str):
    # Create a temporary bookmark so the current change isn't destroyed if it's empty
    tempbm = "jj-pre-push-keep-" + "".join(random.choices(string.ascii_letters, k=10))
    jj(["bookmark", "create", tempbm, "-r", "@"], snapshot=True, suppress_stderr=True)
    jj(["new", ref], snapshot=True, suppress_stderr=True)
    yield
    jj(["edit", tempbm], snapshot=True, suppress_stderr=True)
    jj(["bookmark", "forget", tempbm], suppress_stderr=True)
