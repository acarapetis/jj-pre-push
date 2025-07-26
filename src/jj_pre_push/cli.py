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
    bookmark: str | None = None,
    all: bool = False,
):
    if remote is None:
        remote = jj.default_remote()
    bookmarks = jj.pushable_bookmarks(remote, bookmark=bookmark, all=all)
    if not (bookmark or all):
        keep = jj.default_bookmarks_to_push(remote)
        bookmarks = [b for b in bookmarks if b.name in keep]

    if not bookmarks:
        logger.info("No bookmarks would be pushed, nothing to check.")
    for b in bookmarks:
        logger.info(f"Checking {b}")
        with jj.checkout(b.local_commit_id):
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
                raise typer.Exit(1)


# @app.command()
# def check_and_push(
#     remote: str | None = None,
#     bookmark: str | None = None,
#     all: bool = False,
# ):
#     check(remote, bookmark, all)
#     try:
#         jj.git_push(remote, bookmark, all)
#     except subprocess.CalledProcessError as e:
#         raise typer.Exit(e.returncode)
#
#
if __name__ == "__main__":
    app()
