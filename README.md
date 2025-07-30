# jj-pre-push

[![PyPI](https://img.shields.io/pypi/v/jj-pre-push)](https://pypi.org/project/jj-pre-push/)

A _very limited_ integration between [jj](https://jj-vcs.github.io) and
[pre-commit](https://pre-commit.com/) allowing you to run your pre-push hooks in a
colocated jj/git repository.

I don't expect this to last forever, it's just a stopgap until some jj-native mechanism
arrives that can take over.

Prior art:

- <https://www.aazuspan.dev/blog/automating-pre-push-checks-with-jujutsu/>
- Various comments on <https://github.com/jj-vcs/jj/issues/405>

## Usage

Use `jj-pre-push push` (or an alias - personally I use `jj push`) as a replacement for
`jj git push`. It takes all the same arguments, and does the following:

1. Determines which bookmarks the corresponding `jj git push` will update on the remote,
   and how they would change.
2. For each of these bookmarks in turn:
   - Checks out the bookmark to the working copy
   - Runs the pre-push hooks defined in your .pre-commit-config.yaml on the same set of
     files pre-commit would when pushing the same change. (For existing branches that's
     the files touched in the range `old`...`new`; for new branches it's the files
     touched in all ancestors of `new` that aren't present on the remote.)
   - Reports any failures; and if any files were modified reports the change ID(s) in which
     these modifications can be found.
3. If all hooks succeeded on all branches, executes `jj git push` with the arguments
   provided; otherwise nothing is pushed.
4. Returns the working copy to its original change.

If there is no .pre-commit-config.yaml in your workspace root, `jj-pre-push push`
immediately delegates to `jj git push`.

By default `jj-pre-push` produces no console output of its own unless hooks fail. If
you'd like to see more details about what's happening, you can use `jj-pre-push
--log-level=INFO push`.

## Installation

If you have [uv](https://docs.astral.sh/uv/) installed and you're planning to use an
alias anyway, you can avoid explicitly installing at all with `uvx`, e.g. with this jj
configuration for `jj push`:

```toml
[aliases]
push = ["util", "exec", "--", "uvx", "jj-pre-push", "push"]
```

Otherwise, install the PyPI package `jj-pre-push` in whichever way you prefer; e.g. `uv tool
install jj-pre-push` or `pip install jj-pre-push`, and use `jj-pre-push push` as
described earlier.

## Usage with jjui

If you're a [jjui](https://github.com/idursun/jjui) fan (I think maybe you should be!),
here's an example `jjui/config.toml` snippet showing how you can define custom commands
to invoke jj-pre-push: one to perform the default `jj push`, and one to push the
bookmarks attached to the change you have currently selected in the UI.

```toml
[custom_commands]
"jj push" = { key = ["p"], args = ["push"] }
"jj push selected bookmark(s)" = { key = ["P"], args = ["push", "-r", "$change_id"] }
```

Note that these depend upon the `jj push` alias defined in the previous section.
