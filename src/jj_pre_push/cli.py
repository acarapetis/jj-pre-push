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
        logger.info("No bookmarks will be pushed, nothing to check.")
        return

    updates = {u for u in updates if u.update_type != "delete"}

    if not updates:
        logger.info("Only deletions will be pushed, nothing to check.")
        return

    success = True
    with jj.autostash():
        for u in updates:
            assert u.new_commit is not None

            logger.info(f"{u}: checking with pre-commit...")

            if u.old_commit is not None:
                # Just check old...new.
                # pre-commit's pre-push hook does this, so we do the same.
                from_refs = [u.old_commit]
            else:
                # For new branches, pre-commit finds the first ancestor of the new
                # bookmark's target that isn't already on the remote, then diffs from
                # its parent. Really we should consider the possibility of a local merge
                # derived from multiple remote heads; so:
                on_remote = f"(::remote_bookmarks(remote={u.remote}))"
                our_remote_heads = f"heads(::{u.new_commit} & {on_remote})"
                from_refs = [c.commit_id for c in jj.get_changes(our_remote_heads)]

            # Usually there will just be one from_ref (and in fact pre-commit seems
            # to just assume this is always the case); but it's possible the local
            # branch is a merge of two local branches started from distinct remote
            # branches. In this rare case we run once per root. Would be more efficient
            # to union the lists of changed files I guess?
            for from_ref in from_refs:
                jj.new(u.new_commit)
                logger.info(f"Running pre-commit on {from_ref}...{u.new_commit}")
                # Even though pre-commit is python, we call it as a subprocess so that
                # we use whatever version the user has installed on their PATH - seems
                # like the least surprising thing to do.
                ref_opts = ["--from-ref", from_ref, "--to-ref", u.new_commit]
                result = subprocess.run(
                    ["pre-commit", "run", "--hook-stage", "pre-push", *ref_opts]
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
