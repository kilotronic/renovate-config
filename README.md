# renovate-config

Shared [Renovate](https://docs.renovatebot.com/) presets, so every repo gets its pin updates
from one set of rules instead of hand-made pin-bump pull requests.

## Use

In a repo's `renovate.json`:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "github>kilotronic/renovate-config",
    "github>kilotronic/renovate-config:automerge"
  ]
}
```

Leave out the `:automerge` line in a repo whose default branch does not require CI.

## What the presets do

`default.json`:

- Pins GitHub Actions and reusable workflows to a commit, with the version as a comment
  (`uses: actions/checkout@<sha> # v7.0.1`), and keeps both current.
- Turns on the pre-commit manager (off by default in Renovate), so pre-commit `rev:` pins move
  too, including commit pins with a `# frozen: v1.2.3` comment.
- Moves the kilotronic check tools (`kilotronic/checks`, and the separate `lint`,
  `git-identity`, `secret-scan`, `data-leak-check`, `vendored-license-check` and `red-on-logic`
  repos it merges) in one pull request across every place they are pinned, and only to dotted
  releases (`v1.3.2`, never the moving `v1` tag).
- Turns off the copier manager: the answers files name a private template and pin a commit,
  so it only logs lookup failures. It goes back on here once the templates are public and tagged.
- Groups GitHub Actions, Python and npm minor/patch updates into one pull request each.
- Runs before 9am Pacific on Mondays, and waits three days after a release before offering it.
  Security fixes come at any time, with no wait, labelled `security`.
- Holds Python minor and major versions (`.python-version`, Docker base images,
  `setup-python`): those move by hand when needed. Patches still flow.

`automerge.json`: minor, patch, pin and digest updates merge themselves (squash) once every
check is green, required or not (Renovate merges them itself, not through GitHub's auto-merge,
which waits for required checks only); majors wait for a person.

A repo adds its own rules after the `extends` line. Renovate applies later rules last, so keep
any grouping rule for the check tools in this preset, not in the repo.

## Develop

`.github/workflows/ci.yml` runs Renovate's validator (`renovate-config-validator --strict`) over
every preset and `tests/` with pytest. Locally:

```sh
npx --yes --package renovate@44.224.2 -- renovate-config-validator --strict --no-global default.json automerge.json renovate.json
uvx pytest -q tests
```

## License

MIT
