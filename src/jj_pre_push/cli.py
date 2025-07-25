import subprocess
from jj_pre_push import jj
import typer

app = typer.Typer()


@app.command()
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
    for b in bookmarks:
        print(f"Checking {b}")
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
                print(f"pre-commit checks failed for bookmark {b}")
                raise typer.Exit(1)


@app.command()
def check_and_push(
    remote: str | None = None,
    bookmark: str | None = None,
    all: bool = False,
):
    check(remote, bookmark, all)
    try:
        jj.git_push(remote, bookmark, all)
    except subprocess.CalledProcessError as e:
        raise typer.Exit(e.returncode)


def main():
    app()
