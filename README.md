# jj-pre-push

A *very basic* integration between `jj` and `pre-commit`.

Once configured, `jj-pre-push` will run your repo's pre-commit hooks before pushing to
git remotes, and abort the push if any hooks fail.
