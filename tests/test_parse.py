from jj_pre_push.bookmark_updates import BookmarkUpdate, parse_git_push_dry_run


def test_parse_git_push_dry_run():
    output = """\
Changes to push to origin:
  Move forward bookmark main from d964e724c76e to a81d749233ff
  Add bookmark painstaking to 591f7e9aae85
  Move sideways bookmark sideways from 9c712e75a982 to 23f89ce4b31b
  Move backward bookmark backward from d964e724c76e to 561998a40ada
  Delete bookmark deleted from 9c712e75a982
Dry-run requested, not pushing.
"""
    assert parse_git_push_dry_run(output) == {
        BookmarkUpdate(
            "origin", "main", "move_forward", "d964e724c76e", "a81d749233ff"
        ),
        BookmarkUpdate("origin", "painstaking", "add", None, "591f7e9aae85"),
        BookmarkUpdate(
            "origin", "sideways", "move_sideways", "9c712e75a982", "23f89ce4b31b"
        ),
        BookmarkUpdate(
            "origin", "backward", "move_backward", "d964e724c76e", "561998a40ada"
        ),
        BookmarkUpdate("origin", "deleted", "delete", "9c712e75a982"),
    }
