# AGENTS.md

Instructions for AI coding agents that work on `mflux-web-seed`. Human contributors can use this file too. For project background, read `README.md`.

## Project summary

- `mflux-web-seed` is a FastAPI web UI for [MFlux](https://github.com/mflux-community/mflux). MFlux generates images on Apple Silicon with MLX.
- This distribution ships one package: `mflux.web.seed`. The `mflux` core distribution does the inference work.
- The console command is `mflux-web`. It calls `mflux.web.seed.cli:main`.
- MFlux and MLX run only on arm64 or aarch64 hosts. The `justfile` stops on other hosts.

## Namespace contract (do not break)

This package follows the namespace model from [mflux PR #776](https://github.com/mflux-community/mflux/pull/776).

- Put all package code in `src/mflux/web/seed/`.
- Do not add `src/mflux/__init__.py`. The core distribution owns that file.
- Do not add `src/mflux/web/__init__.py`. `mflux.web` must stay an implicit namespace package.
- Do not change `module-name` or `namespace` in `[tool.uv.build-backend]` in `pyproject.toml`.
- `tests/test_namespace_extensions.py` checks this contract. These tests must pass.

## Setup

Install `uv` and `just` first. Then run:

```bash
just venv-install   # Python 3.13 venv, dependencies, pre-commit hooks
```

Use `uv run` for all Python commands. Do not use `pip install`.

## Commands

| Task | Command | Changes files? |
| --- | --- | --- |
| List all recipes | `just` | No |
| Lint (ruff) | `just dev-lint` | No |
| Format (ruff) | `just dev-format` | Yes |
| Type check (ty) | `just dev-typecheck` | No |
| All pre-commit hooks | `just dev-check` | Yes (auto-fix) |
| Tests | `just test` | No |
| Start the web server | `just run` | No |
| Show server options | `just run --help` | No |
| Build wheel and sdist | `just build` | Yes (`dist/`) |

Before you say that a change is complete, run `just dev-lint`, `just dev-typecheck` and `just test`.

## Code layout

```text
src/mflux/web/seed/
  cli.py          # argparse, YAML settings merge, uvicorn start
  settings.py     # WebSettings dataclass
  app.py          # WebApp: FastAPI routes (pages and /api/*)
  auth.py         # WebAuth (API key, sessions), LoginThrottle
  network.py      # NetworkPolicy: bind address and allowed Host headers
  paths.py        # PathGuard: keeps file access inside allowed directories
  schema.py       # FormSchema: builds UI forms from the mflux CLI parsers
  invocation.py   # Invocation: turns a form payload into validated CLI args
  adapters.py     # one CommandAdapter per mflux generate command
  runner.py       # JobRunner: one worker thread, model cache, progress events
  static/         # plain JavaScript and CSS (no build step)
  templates/      # Jinja2 HTML templates
tests/web/        # UI tests
tests/test_namespace_extensions.py  # namespace contract tests
mflux-web.example.yaml  # example settings file (all keys commented out)
```

## Architecture notes

- Each adapter in `adapters.py` mirrors one mflux CLI `main()`. `load()` builds the model once. `generate()` makes one image for one seed. When mflux core changes a CLI, update the matching adapter.
- To add a model, subclass `CommandAdapter` and add the instance to `ADAPTERS`. Add tests in `tests/web/`.
- `JobRunner` touches model memory only on its worker thread. Do not load, use or free models from request handlers.
- Settings precedence: command-line flags, then the YAML file, then built-in defaults. The server uses the first YAML file it finds: the `--yaml` path, then `MFLUX_WEB_YAML`, then `./mflux-web.yaml`, then `~/.config/mflux/mflux-web.yaml`. A missing `--yaml` or `MFLUX_WEB_YAML` file is an error.
- The server rejects unknown YAML keys. When you add a setting, add it to `YAML_OPTIONS` in `cli.py` and to `mflux-web.example.yaml`.
- API key precedence: command line, then `MFLUX_WEB_API_KEY`, then YAML. At each level, a key and a key file together are an error.

## Security rules

The UI can listen on a network, so these rules are strict.

- The server owns all file paths. Send every user path through `PathGuard`.
- `FormSchema.BLOCKED_FLAGS` lists CLI flags that a form must never set. Do not remove a flag from this list without a clear reason in the PR.
- A bind address that is not loopback needs an API key. Keep this check.
- Do not log API keys, session secrets or full request bodies.
- `tests/web/test_security.py` covers these rules. Add a test for each new route or upload path.

## Code style

- Ruff settings are in `pyproject.toml`: line length 120, double quotes, sorted imports.
- Match the style of the code near your change. The code uses few comments. A comment tells why, not what.
- Tests must not download models or generate images. Use fakes for the mflux model classes.
- Put type hints on new code. `pyproject.toml` ignores four ty rules because of old errors in `runner.py`. Do not add new errors of these types. If you fix all errors of one rule, remove its ignore line.
- The `typos` pre-commit hook checks spelling. Add real project words to `_typos.toml`.

## Dependencies and version pins

- `ruff` and `ty` have exact pins in `pyproject.toml`. The same versions are in `.pre-commit-config.yaml` and in the install commands in `README_JUST.md`. When you change a version, change it in all three files.
- After you change `pyproject.toml`, run `uv lock` and commit `uv.lock`. The `uv-sync-locked` pre-commit hook fails if the lock file is out of date.
- `[tool.uv.sources]` pins mflux core to git `main`, because no release contains PR #776 yet. Do not remove this pin until such a release is available.

## Pull requests

- Keep each PR on one topic.
- `just dev-check` and `just test` must pass before you open a PR.
- Update `README.md` when a command, option or setting changes. Update `mflux-web.example.yaml` when a setting changes.
- Do not commit personal paths, API keys, models, generated images, `.venv/` or `dist/`.

## Agent-specific files

- `CLAUDE.md` imports this file for Claude Code. Put shared instructions here, not in `CLAUDE.md`.
- Commit `.claude/settings.json`, `.claude/agents/`, `.claude/commands/` and `.claude/skills/` when they help all contributors.
- Do not commit personal files: `.claude/settings.local.json` and `CLAUDE.local.md`. `.gitignore` excludes them.
