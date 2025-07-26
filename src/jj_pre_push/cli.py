import subprocess
from typing import Annotated
from jj_pre_push import jj
import typer
import logging

logger = logging.getLogger(__name__)


app = typer.Typer()


@app.callback()
def callback(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False):
    logging.basicConfig(
        format="%(message)s", level=logging.DEBUG if verbose else logging.WARNING
    )


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def check(
    remote: str | None = None,
    bookmark: Annotated[str | None, typer.Option("-b", "--bookmark")] = None,
    all: bool = False,
    deleted: bool = False,
    allow_new: Annotated[bool, typer.Option("-N", "--allow-new")] = False,
    revisions: Annotated[list[str], typer.Option("-r", "--revisions")] = [],
    change: Annotated[list[str], typer.Option("-c", "--change")] = [],
):
    if remote is None:
        remote = jj.default_remote()
    bookmarks = jj.pushable_bookmarks(remote, bookmark=bookmark, all=all)
    if not (bookmark or all):
        keep = jj.default_bookmarks_to_push(remote)
        bookmarks = [b for b in bookmarks if b.name in keep]

    if not bookmarks:
        logger.info("No bookmarks would be pushed, nothing to check.")
    else:
        success = True
        with jj.stash_change():
            for b in bookmarks:
                logger.info(f"Checking {b}")
                jj.new(b.local_commit_id)
                result = subprocess.run(
                    [
                        "pre-commit",
                        "run",
                        "--from-ref",
                        b.remote_commit_id,
                        "--to-ref",
                        b.local_commit_id,
                    ]
                )
                if result.returncode != 0:
                    logger.error(f"pre-commit checks failed for bookmark {b}")
                    success = False

        if success:
            logger.info("All checks passed.")
        else:
            logger.error("One or more checks failed, please fix before pushing.")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
