import logging
import re
from dataclasses import dataclass
from typing import Literal

from .jj import jj

logger = logging.getLogger(__name__)

BookmarkUpdateType = Literal[
    "move_forward", "move_backward", "move_sideways", "add", "delete"
]


@dataclass(slots=True, frozen=True)
class BookmarkUpdate:
    remote: str
    bookmark: str
    update_type: BookmarkUpdateType
    old_commit: str | None = None
    new_commit: str | None = None

    def __str__(self):
        old = f" from {self.old_commit[:8]}" if self.old_commit else ""
        new = f" to {self.new_commit[:8]}" if self.new_commit else ""
        return f"{self.update_type.replace('_', ' ').capitalize()} {self.bookmark}{old}{new}"


# This is extremely brittle but it seems much better than reimplementing all the
# bookmark selection logic of `jj git push` for every possible combination of
# arguments.
# TODO: Consider parsing more rigidly?
# If the wording changes in the future, it's better to fail than to parse incorrectly!
_remote_pattern = re.compile(r"^Changes to push to (.+?):")
_bookmark_update_patterns: dict[BookmarkUpdateType, re.Pattern] = {
    "move_forward": re.compile(
        r"Move forward bookmark (?P<bookmark>\S+) from (?P<old_commit>\w+) to (?P<new_commit>\w+)"
    ),
    "move_backward": re.compile(
        r"Move backward bookmark (?P<bookmark>\S+) from (?P<old_commit>\w+) to (?P<new_commit>\w+)"
    ),
    "move_sideways": re.compile(
        r"Move sideways bookmark (?P<bookmark>\S+) from (?P<old_commit>\w+) to (?P<new_commit>\w+)"
    ),
    "add": re.compile(r"Add bookmark (?P<bookmark>\S+) to (?P<new_commit>\w+)"),
    "delete": re.compile(r"Delete bookmark (?P<bookmark>\S+) from (?P<old_commit>\w+)"),
}


def parse_git_push_dry_run(output: str) -> set[BookmarkUpdate]:
    """Extract bookmark change details from `jj git push --dry-run`."""

    updates = set()
    remote = None
    for line in output.splitlines():
        if match := _remote_pattern.search(line):
            remote = match.group(1)
        for update_type, pattern in _bookmark_update_patterns.items():
            if match := pattern.search(line):
                if remote is None:
                    raise ValueError(
                        "Unexpected line ordering in jj git push --dry-run"
                    )
                updates.add(
                    BookmarkUpdate(
                        **match.groupdict(), remote=remote, update_type=update_type
                    )
                )
    return updates


def get_remote_bookmark_updates(jj_git_push_args: list[str]) -> set[BookmarkUpdate]:
    """Given a list of CLI arguments to `jj git push`, determine the set of bookmark
    updates that would be pushed to the git remote."""
    output = jj(
        ["git", "push", "--dry-run", *jj_git_push_args],
        snapshot=False,
        capture_stderr=True,
    )
    return parse_git_push_dry_run(output)
