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
        print(f"Would push {b.name}: {b.remote_commit_id}..{b.local_commit_id}")
        with jj.checkout(b.local_commit_id):
            subprocess.check_call(
                [
                    "pre-commit",
                    "run",
                    "--from-ref",
                    b.remote_commit_id,
                    "--to-ref",
                    b.local_commit_id,
                ]
            )


def main():
    app()
