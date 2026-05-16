import logging
import subprocess
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Literal, cast

import typer

from . import jj
from .bookmark_updates import get_remote_bookmark_updates

logger = logging.getLogger(__name__)
app = typer.Typer()

Mode = Literal["default", "remote-ancestors"]


@dataclass
class Settings:
    checker: str
    mode: Mode


def version_callback(value: bool):
    if value:
        try:
            v = version("jj-pre-push")
        except PackageNotFoundError:
            v = "unknown"
        print(f"jj-pre-push version {v}")
        raise typer.Exit(0)


@app.callback()
def callback(
    ctx: typer.Context,
    log_level: Annotated[str, typer.Option(envvar="JJ_PRE_PUSH_LOG_LEVEL")] = "WARNING",
    checker: Annotated[
        str,
        typer.Option(
            envvar="JJ_PRE_PUSH_CHECKER", help="Executable to call to run checks (e.g. prek)"
        ),
    ] = "pre-commit",
    mode: Annotated[
        Mode,
        typer.Option(
            envvar="JJ_PRE_PUSH_MODE",
            help="EXPERIMENTAL: Determines which files to check. "
            "default: use pre-commit's default logic for pre-push hooks. "
            "remote-ancestors: files changed since the most recent ancestors already present on the remote.",
        ),
    ] = "default",
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
):
    logging.basicConfig(format="jj-pre-push: %(message)s", level=log_level)
    ctx.obj = Settings(
        checker=checker,
        mode=mode,
    )


def checker_command(checker: str):
    match checker:
        case "hk":
            return ["hk", "run", "pre-push"]
        case _:
            return [checker, "run", "--hook-stage", "pre-push"]


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def check(ctx: typer.Context):
    settings = cast(Settings, ctx.obj)
    push_args = ctx.args
    try:
        root = jj.workspace_root()
    except jj.JJError as e:
        if e.message:
            logger.error(e.message)
        raise typer.Exit(e.returncode)

    if not (root / ".pre-commit-config.yaml").exists():
        logger.info("No pre-commit config in this repo, nothing to check.")
        return

    try:
        updates = get_remote_bookmark_updates(push_args)
    except jj.JJError as e:
        if e.message:
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

    # Optimization: if the current working commit is empty and is based on the
    # bookmark being pushed, we can run the checker directly in that working
    # commit instead of creating a new one. This leaves any edits made by the
    # checker in the working commit, ready for the user.
    orig_wc = jj.current_change()
    orig_parents = jj.get_changes("parents(@)")
    orig_parent_ids = [c.commit_id for c in orig_parents]

    with jj.autostash():
        for u in updates:
            assert u.new_commit is not None

            logger.info(f"{u}: checking with {settings.checker}...")
            if settings.mode == "default" and u.old_commit is not None:
                # Just check old...new.
                # pre-commit's pre-push hook does this, so we default to the same.
                from_refs = [u.old_commit]
            else:
                # For new branches, pre-commit finds the first ancestor of the new
                # bookmark's target that isn't already on the remote, then diffs from
                # its parent. Really we should consider the possibility of a local merge
                # derived from multiple remote heads; so:
                on_remote = f"(::remote_bookmarks(remote=exact:{u.remote}))"
                our_remote_heads = f"heads(::{u.new_commit} & {on_remote})"
                from_refs = [c.commit_id for c in jj.get_changes(our_remote_heads)]

            # Usually there will just be one from_ref (and in fact pre-commit seems
            # to just assume this is always the case); but it's possible the local
            # branch is a merge of two local branches started from distinct remote
            # branches. In this rare case we run once per root. Would be more efficient
            # to union the lists of changed files I guess?
            use_orig_wc = (
                orig_wc.empty and u.new_commit in orig_parent_ids and len(from_refs) == 1
            )
            for from_ref in from_refs:
                if use_orig_wc:
                    logger.info(
                        f"Using empty working commit {orig_wc.change_id} on top of {u.new_commit}"
                    )
                    jj.edit(orig_wc.change_id)
                else:
                    jj.new(u.new_commit)

                logger.info(f"Running {settings.checker} on {from_ref}...{u.new_commit}")
                # Even though pre-commit is python, we call it as a subprocess so that
                # we use whatever version the user has installed on their PATH - seems
                # like the least surprising thing to do.
                ref_opts = ["--from-ref", from_ref, "--to-ref", u.new_commit]
                result = subprocess.run([*checker_command(settings.checker), *ref_opts])
                if result.returncode != 0:
                    success = False
                    change = jj.current_change()
                    if change.empty:
                        logger.error(f"{u}: {settings.checker} failed but changed no files.")
                    else:
                        logger.error(
                            f"{u}: {settings.checker} changed some files, see {change.change_id}"
                        )

    if success:
        logger.info("All checks passed.")
    else:
        logger.error("One or more checks failed, please fix before pushing.")
        raise typer.Exit(1)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
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
