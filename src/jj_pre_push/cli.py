import subprocess
from jj_pre_push import jj
import typer

app = typer.Typer()


@app.command()
def check_and_push(
    remote: str | None = None, bookmark: str | None = None, all: bool = False
):
    if remote is None:
        remote = jj.default_remote()
    bookmarks = jj.pushable_bookmarks(remote, bookmark=bookmark, all=all)
    if not (bookmark or all):
        keep = jj.default_bookmarks_to_push(remote)
        bookmarks = [b for b in bookmarks if b.name in keep]
    for b in bookmarks:
        with jj.checkout(b.local_commit_id):
            if (
                subprocess.run(
                    [
                        "pre-commit",
                        "run",
                        "--from-ref",
                        b.remote_commit_id,
                        "--to-ref",
                        b.local_commit_id,
                    ]
                ).returncode
                != 0
            ):
                print(
                    f"pre-commit checks failed for bookmark {b.name} ({b.remote_commit_id}..{b.local_commit_id})"
                )
                raise typer.Exit(1)


def main():
    app()
