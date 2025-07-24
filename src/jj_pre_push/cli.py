import logging
import subprocess
from typing import Annotated

import typer

from . import jj
from .bookmark_updates import get_remote_bookmark_updates

logger = logging.getLogger(__name__)
app = typer.Typer()


@app.callback()
def callback(
    log_level: Annotated[str, typer.Option(envvar="JJ_PRE_PUSH_LOG_LEVEL")] = "WARNING",
):
    logging.basicConfig(format="jj-pre-push: %(message)s", level=log_level)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def check(ctx: typer.Context):
    push_args = ctx.args
    if not (jj.workspace_root() / ".pre-commit-config.yaml").exists():
        logger.info("No pre-commit config in this repo, nothing to check.")
        return

    try:
        updates = get_remote_bookmark_updates(push_args)
    except jj.JJError as e:
        logger.error(e.message)
        raise typer.Exit(e.returncode)

    if not updates:
        logger.info("No bookmarks would be pushed, nothing to check.")
        return

    updates = {u for u in updates if u.update_type != "delete"}

    if not updates:
        logger.info("Only deletions would be pushed, nothing to check.")
        return

    success = True
    with jj.autostash():
        for u in updates:
            assert u.new_commit is not None

            logger.info(f"{u}: checking with pre-commit...")
            jj.new(u.new_commit)

            # Even though pre-commit is python, we call it as a subprocess so that
            # we use whatever version the user has installed on their PATH - seems
            # like the least surprising thing to do.

            if u.update_type == "move_forward" and u.old_commit is not None:
                # Just check the files changed since the last push
                opts = ["--from-ref", u.old_commit, "--to-ref", u.new_commit]
            else:
                # For new branches or force-pushes, just check everything.
                # TODO: Could potentially extract the list of differing files from
                # jj/git and pass this to pre-commit's --files? Haven't thought it
                # through all the way yet.
                opts = ["--all-files"]

            result = subprocess.run(
                ["pre-commit", "run", "--hook-stage", "pre-push", *opts]
            )
            if result.returncode != 0:
                success = False
                change = jj.current_change()
                if change.empty:
                    logger.error(f"{u}: pre-commit failed but changed no files.")
                else:
                    logger.error(
                        f"{u}: pre-commit changed some files, see {change.change_id}"
                    )

    if success:
        logger.info("All checks passed.")
    else:
        logger.error("One or more checks failed, please fix before pushing.")
        raise typer.Exit(1)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def push(ctx: typer.Context, help: bool = False, dry_run: bool = False):
    push_args = ctx.args

    if help:
        subprocess.run(["jj", "git", "push", "--help", *push_args])
        return

    check(ctx)

    if dry_run:
        push_args.append("--dry-run")
    subprocess.run(["jj", "git", "push", *push_args], check=True)


if __name__ == "__main__":
    app()
