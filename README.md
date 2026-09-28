# mflux-web-seed
## About
This is a small basic Web UI seed for building web apps that access MFlux. 

[MFlux](https://github.com/mflux-community/mflux) is a free, open-source tool that lets you generate AI images on your own Mac, without paying for a cloud service. 

This seed provides a small web browser interface for MFlux; a friendly page with forms and buttons instead of having to type commands into a terminal. Under the hood, all the actual image-generation work is still done by the main MFlux software - this project is just a starting point for you to build your own web app that fronts MFlux.


## Origin Story
The mflux web UI, extracted from the [x746b/mflux](https://github.com/x746b/mflux)
fork into a standalone PyPI distribution — the packaging model introduced by
[mflux PR #776](https://github.com/mflux-community/mflux/pull/776). 


The UI lives in one unique child of the shared `mflux.web` namespace:
`mflux.web.seed`. The `mflux` core distribution provides the inference
plumbing.

## Overview

- **What this is:** the full fork web UI (FastAPI app, job runner, adapters,
  auth, static/templates assets and tests) as an independently
  releasable package.
- **The contract (PR #776):** this distribution ships ONLY
  `src/mflux/web/seed/`. It never ships `src/mflux/__init__.py` (core owns
  it) or `src/mflux/web/__init__.py` (`mflux.web` must stay an implicit
  namespace package). Installing it never collides with core or other UIs.
- **Entry point:** `mflux-web` console command (`mflux.web.seed.cli:main`).

## Quick start

```bash
just venv-install   # venv (Python 3.13) + deps + pre-commit hooks
just test           # web UI tests + namespace contract tests
just dev-lint       # ruff (read-only)
just dev-format     # ruff format (mutates files)
just dev-typecheck  # ty
just dev-check      # pre-commit run --all-files (auto-fixes)
just venv-uninstall # remove .venv
```

Run the UI:

```bash
just run                      # serves the web UI (see --help for host/port/auth/TLS)
just run --help               # full option list
```

To keep your settings in a file, copy the example settings file. Then remove the `#` from the settings that you want to change:

```bash
cp mflux-web.example.yaml mflux-web.yaml                           # this folder only
mkdir -p ~/.config/mflux && cp mflux-web.example.yaml ~/.config/mflux/mflux-web.yaml  # all folders
```

The server uses the first file that it finds: the `--yaml` path, then `MFLUX_WEB_YAML`, then `./mflux-web.yaml`, then `~/.config/mflux/mflux-web.yaml`. The startup message shows the file that the server uses. Command-line options override the values in the file.

Build a publishable wheel/sdist:

```bash
just build                     # dist/mflux_web_seed-0.1.0*.whl|.tar.gz
```

## How the namespace works

- Core mflux's initializer extends its `__path__` (`pkgutil.extend_path`), so
  directories contributed by separately installed UI distributions merge
  into one import namespace — including editable checkouts.
- `mflux.web` is an implicit namespace package: no distribution ships
  `mflux/web/__init__.py`; Python combines the contributed `mflux/web/*/`
  directories. The fork's old `mflux/web/__init__.py` (empty) was dropped
  during extraction for exactly this reason.
- Ordinary wheels sharing one site-packages already coexist; `extend_path`
  fixes split-directory and editable layouts.
- The regression tests in `tests/test_namespace_extensions.py` (adapted from
  the PR #776 suite) verify: the contract files are never shipped, the child
  imports without core, and two UI distributions merge across separate
  directories.

## Core pin

The UI depends on `mflux>=0.20.0`, currently pinned to git main via
`[tool.uv.sources]` because the PR #776 path extension is not yet in a
release. Once core ships a release containing #776, swap to
`mflux>=<that version>` and delete the override.

## Extraction notes (fork → seed)

- Internal imports rewritten: `mflux.web.X` → `mflux.web.seed.X` (10 modules,
  8 test files; import order re-sorted by ruff).
- Fork's `mflux/web/__init__.py` was empty — dropped, per contract.
- `tests/web/test_memory.py::test_qwen21_geometry_cache_is_bounded` skips
  when core lacks the fork's bounded geometry-cache enhancement
  (`GEOMETRY_CACHE_SIZE`): the UI works with both upstream and fork core.
- ty baseline: four rules carried over ignored from the fork
  (`unresolved-attribute`, `invalid-assignment`, `invalid-argument-type`,
  `not-subscriptable` — 26 pre-existing diagnostics in `runner.py`'s
  `Job | str` sentinel pattern). Fix piecemeal, not during extraction.

## Layout

```text
src/mflux/web/seed/    # the child: app.py adapters.py runner.py auth.py cli.py
                       #            invocation.py network.py paths.py schema.py
                       #            settings.py static/ templates/
tests/web/             # UI tests from the fork (imports rewritten)
tests/test_namespace_extensions.py  # PR #776 contract regression tests
justfile               # adapted from mflux core (clean → uninstall)
.pre-commit-config.yaml # ruff + typos + ty + uv-sync-locked
pyproject.toml          # uv_build, module-name = mflux.web.seed
```

## Tooling pins

Pinned to match mflux core (single source of truth in `pyproject.toml`,
kept in sync with `.pre-commit-config.yaml`):

| Tool      | Version | Note                                  |
| --------- | ------- | ------------------------------------- |
| ruff      | 0.16.3  | lint + format, same rules as core     |
| ty        | 0.0.72  | type checker, same as core            |
| pytest    | >=9.1   | test runner                           |
| Python    | 3.13    | recommended maintainer Python (just)  |


---
<sub>Web UI originally authored by [@AnthonyWu](https://github.com/anthonywu) & [ianscrivener](https://github.com/ianscrivener)</sub>
