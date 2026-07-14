# Installation and the first CLI skeleton

## Theory

Python is interpreted and dynamically typed — every value has a concrete type at runtime, you just don't declare it in a signature unless you add explicit type hints. The syntax difference that will bug you for the first week: blocks are defined by indentation, not `{}`. Indentation isn't a style choice here — it's syntax. Get it wrong and you get an `IndentationError`, not a linter warning.

**Installing Python.** macOS/Linux almost always ship with some `python3` already, but don't rely on the system Python — it's often outdated and the OS itself depends on it. In practice: install a current Python separately, either via [pyenv](https://github.com/pyenv/pyenv) (think `nvm`, if that's familiar) or the official installer from python.org. This course needs **Python 3.11+**. Check the version:

```bash
python3 --version
# Python 3.12.3
```

**venv — virtual environments.** This is the single most important difference from the Node ecosystem, and it's worth internalizing right away. In Node, every project is isolated by default: `npm install` puts packages in a local `node_modules`, so two projects requiring different versions of the same library never collide. Python has **no isolation by default** — `pip install requests` with no extra setup installs `requests` into the site-packages of *the interpreter itself*, globally. Two projects needing different Django versions on the same machine will step on each other.

`venv` fixes this by creating a copy/symlink of the interpreter plus a dedicated site-packages directory for that one project:

```bash
python3 -m venv .venv          # create the environment in .venv
source .venv/bin/activate      # activate it (Linux/macOS)
# .venv\Scripts\activate       # activate it (Windows)
python --version               # "python" now resolves to the venv's 3.11+
pip install requests           # installed ONLY into .venv, not globally
deactivate                     # leave the environment
```

After `activate`, `python` and `pip` in your shell point at the binaries inside `.venv/bin/`, not the system ones. venv is doing the job of `nvm` and `node_modules` combined — it pins both the interpreter version (whichever `python3` you created it with) and the set of installed packages.

**pip and pyproject.toml.** `pip` is npm/yarn, but historically without a built-in single lockfile (people used to hand-manage this with `pip freeze > requirements.txt`; real lockfiles — poetry, uv — come up in the modules-and-packaging chapter). The modern standard for project metadata is `pyproject.toml`, the direct counterpart of `package.json`:

| package.json | pyproject.toml | Purpose |
|---|---|---|
| `"name"` | `[project] name` | package name |
| `"version"` | `[project] version` | version |
| `"dependencies"` | `[project] dependencies` | deps (different format — a list of version-spec strings, not an object) |
| `"scripts"` | no direct stdlib equivalent; `[project.scripts]` is about CLI entry points, not arbitrary commands | npm scripts are usually replaced by `Makefile`/`invoke`/`nox` |
| ESLint-style config blocks embedded in package.json | `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` | third-party tool config lives right in the same file |

**Project layout and running code.** There's no single "create-react-app" convention, but two layouts are common: flat (`main.py` sitting next to `pyproject.toml`) and src-layout (`src/package_name/...`). For a small CLI, start flat — we'll move to src-layout once it's actually justified, in the modules-and-packages chapter.

Running a script:

```bash
python main.py add "Buy milk"
```

The `if __name__ == "__main__":` idiom is Python's way of saying "run this code only if the file was executed directly, not imported as a module." `__name__` is a special module-level variable: it equals `"__main__"` only when the file is the process's entry point, and equals the module's own name (`"main"`, `"taskman.cli"`, etc.) when the file is imported from somewhere else.

**argparse.** A built-in module (no `pip install` needed) for parsing CLI arguments — the direct counterpart of `commander`/`yargs`, just shipped in the standard library. The key concept for a CLI with subcommands (`add`, `list`, `done`, ...) is `subparsers`: one top-level parser plus a dedicated sub-parser per command, each with its own arguments.

### Parallels with JS/TS/Node:

- **venv ≈ `nvm` + `node_modules` rolled into one mechanism.** Node isolates projects by default (a local `node_modules`); Python has no isolation until you explicitly create and activate a venv.
- **pyproject.toml ≈ package.json**, except linter/type-checker config lives right inside it under `[tool.x]`, rather than in separate `.eslintrc`/`tsconfig.json`-style files (though many tools still support standalone config files too).
- **argparse ≈ commander/yargs**, but nothing to install — it's part of the standard library, the way `readline` used to be built into Node.
- **pip without venv ≈ `npm install -g`** — a global install that breaks the moment two projects want different versions. In Python, unfortunately, that's the *default* behavior, not an opt-in flag.

## What we're adding to the project

We're bootstrapping the `taskman` CLI task-manager skeleton from scratch: a `pyproject.toml` with project metadata, and a single `main.py` with an `add <text>` command that stores a task in an **in-memory list** and prints a confirmation. Persistence (JSON, then SQLite) shows up in chapter 08 — the goal right now is just to live through the full "venv → pyproject.toml → argparse → run it" cycle with your own hands.

## Practical exercise

1. Install Python 3.11+, confirm with `python3 --version`.
2. Create a project folder `taskman/`, create a venv inside it (`python3 -m venv .venv`), activate it.
3. Create `pyproject.toml` with a `[project]` section: `name = "taskman"`, `version = "0.1.0"`, `requires-python = ">=3.11"`.
4. Create `main.py` with an `argparse`-based CLI supporting one subcommand:
   - `add <text>` — appends a task `{"id": ..., "text": ..., "done": False}` to a module-level in-memory list and prints `Added: [id] text`.
5. Confirm `python main.py add "Buy milk"` prints `Added: [1] Buy milk`.

Things to think through (you don't have to solve all of these now, but form an opinion):

- What happens if you run `python main.py add "Buy milk"` twice in a row? Why does the second run also print `[1] ...` instead of `[2] ...`? Is that a bug?
- What does `python main.py` print with no arguments at all? What about `python main.py add` with no text? Look closely at the error message — that's argparse behavior you didn't write yourself.
- Should an empty string / whitespace-only string be a valid task text? Your call — but be able to justify it.

## Worked solution

`pyproject.toml`:

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []
```

`main.py`:

```python
import argparse

# No persistence yet — just a list living in process memory.
# It resets on every restart; that's expected for this chapter
# and gets fixed in the persistence chapter later on.
tasks: list[dict] = []


def add_task(text: str) -> dict:
    task = {"id": len(tasks) + 1, "text": text, "done": False}
    tasks.append(task)
    return task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskman", description="Simple task manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("text", help="Task description")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        task = add_task(args.text)
        print(f"Added: [{task['id']}] {task['text']}")


if __name__ == "__main__":
    main()
```

Key decisions:

- `subparsers = parser.add_subparsers(dest="command", required=True)` — `dest="command"` puts the chosen subcommand's name into `args.command`; `required=True` makes argparse error out and exit if no subcommand is given (without it, missing a subcommand wasn't treated as an error in some Python versions).
- `list[dict]` — since Python 3.9, built-in generic types (`list[int]`, `dict[str, int]`) don't require `from typing import List, Dict`; it's closer to writing `string[]` in TS than to pulling a generic in from a separate module.
- `if __name__ == "__main__": main()` — guarantees that `python main.py` runs `main()`, but if `main.py` later becomes a module something else imports (tests, in chapter 09), the import won't trigger the CLI logic as a side effect.

## Check yourself

1. Why does `python3 -m venv .venv` create a whole structure (an interpreter copy/symlink plus its own site-packages), instead of just a list of installed packages — and how is that fundamentally different from how npm isolates dependencies through `node_modules`?
2. What happens if you run `pip install` without an activated venv, on a project where the system Python is already used by something else? Why does this lead to hard-to-track-down bugs in practice?
3. Why do you need `if __name__ == "__main__":` at all, if you could just call `main()` as the last line of the file unconditionally? What changes if `main.py` gets imported from another file?
4. How is the `[project]` section in `pyproject.toml` fundamentally different from `package.json` when it comes to managing dependency versions — what does `pyproject.toml` NOT solve out of the box (without extra tooling)?
5. Why does `add_subparsers` require `required=True` as an explicit parameter, instead of treating a subcommand as required by default?

<details>
<summary>Answers</summary>

1. Isolation in Python is about more than packages — it's also about which interpreter you're using at all. venv pins exactly which `python`/`pip` binaries you get, because a machine can have several Python versions installed side by side, and without an explicit environment, `pip install` lands in the site-packages of whichever interpreter happens to be first on `PATH`. Node already bakes package-version isolation into `node_modules` per project, while runtime-version management is a separate concern (`nvm`); venv in Python bundles both concerns into one mechanism.
2. The package gets installed into the global site-packages of the system (or first-on-`PATH`) Python. If two different projects on the machine need different versions of the same library, the later install silently overwrites the earlier one — and the other project starts failing with no apparent cause in its own code, purely because someone ran `pip install` without a venv in a different terminal.
3. Without `if __name__ == "__main__":`, calling `main()` unconditionally would fire on **every** import of the file — including when tests in chapter 09 want to import `add_task` or `build_parser` from `main.py` without running the CLI. `__name__` equals `"__main__"` only when the file is the process entry point; on import it equals the module's own name, so the code inside the `if` never runs.
4. `pyproject.toml` describes metadata and the version ranges you're willing to accept, but on its own it doesn't produce a reproducible lockfile with exact pinned versions of the whole dependency tree (unlike `package-lock.json`/`yarn.lock`, which get generated automatically). Getting a real lockfile in Python means bringing in a separate tool on top (poetry, uv, pip-tools) — covered in the modules-and-packaging chapter.
5. Historically argparse allowed subparsers to be optional, so you could build a CLI where having no subcommand is a valid case (e.g., falling through to show help). That behavior was kept as an explicit opt-in rather than the new default, to avoid breaking existing code across Python version upgrades — a typical example of how conservative the standard library is about changing default behavior between minor releases.

</details>

## Common mistake

A JS/TS developer used to dependencies always being local and isolated (`node_modules` gets created automatically on `npm install`, wherever you happen to be) will almost certainly forget to activate the venv before running `pip install` at least once. The difference is that in Node, a missing isolation step usually fails loudly and immediately (no `node_modules` — nothing works, "module not found" is obvious). In Python the package **installs successfully anyway** — just not where you thought. The script might even import it fine (if it happens to also exist in the system Python), creating a false sense that everything works, right up until you're on a different machine or in CI where that "accidental" global package doesn't exist.

The second common trip-up is confusing `python` and `python3` as binary names: on some systems (older Linux distros, or a fresh macOS with no Python explicitly installed), `python` may not exist at all, or may point at Python 2. Inside an activated venv this doesn't matter — `python` always points at the interpreter the venv was created with — but before activation, `python script.py` can unexpectedly blow up on a syntax error from f-strings or type hints that Python 2 simply doesn't understand.
