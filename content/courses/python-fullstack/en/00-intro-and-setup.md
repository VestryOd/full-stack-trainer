# Installation and the first CLI skeleton

## Theory

This chapter ends with a working command-line interface (CLI) skeleton. It starts with the two things that surprise a JS developer first: how Python is installed, and how it isolates dependencies.

Python is interpreted and dynamically typed. Every value has a concrete type at runtime. You just don't declare that type in a signature unless you add explicit type hints. The syntax difference you keep hitting in the first week: blocks are defined by indentation, not `{}`. Indentation isn't a style choice here — it's syntax. Get it wrong and you get an `IndentationError`, not a linter warning.

**Installing Python.** macOS/Linux almost always ship with some `python3` already. Don't rely on that system Python: it is often outdated, and the operating system itself depends on it. In practice, install a current Python separately, either via [pyenv](https://github.com/pyenv/pyenv) (think `nvm`, if that's familiar) or the official installer from python.org. This course needs **Python 3.11+**. Check the version:

```bash
python3 --version
# Python 3.12.3
```

**venv — virtual environments.** This is the single most important difference from the Node ecosystem, and it's worth internalizing right away. In Node, every project is isolated by default: `npm install` puts packages into a local `node_modules`. Two projects that need different versions of the same library never collide.

Python has **no isolation by default** — `pip install requests` with no extra setup installs `requests` into the site-packages of *the interpreter itself*, globally. Two projects needing different Django versions on the same machine will step on each other.

`venv` fixes this by creating a copy/symlink of the interpreter plus a dedicated site-packages directory for that one project:

```bash
python3 -m venv .venv          # create the environment in .venv
source .venv/bin/activate      # activate it (Linux/macOS)
# .venv\Scripts\activate       # activate it (Windows)
python --version               # "python" now resolves to the venv's 3.11+
pip install requests           # installed only into .venv, not globally
deactivate                     # leave the environment
```

After `activate`, the `python` and `pip` commands in your shell point at the binaries inside `.venv/bin/`, not at the system ones. One venv does the job of `nvm` and `node_modules` at once. It pins the interpreter version (whichever `python3` you created it with) and the set of installed packages.

**pip and pyproject.toml.** `pip` is the npm/yarn of Python, but historically it had no built-in lockfile. People managed that by hand with `pip freeze > requirements.txt`. Real lockfiles — poetry, uv — come up in the modules-and-packaging chapter. The modern standard for project metadata is `pyproject.toml`, the direct counterpart of `package.json`:

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

The `if __name__ == "__main__":` idiom means: run this code only if the file was executed directly, not imported as a module. Here `__name__` is a special module-level variable. It equals `"__main__"` only when the file is the process entry point. When the file is imported from somewhere else, it equals the module's own name — `"main"`, `"taskman.cli"` and so on.

**argparse.** A built-in module (no `pip install` needed) for parsing CLI arguments — the direct counterpart of `commander`/`yargs`, just shipped in the standard library. The key concept for a CLI with subcommands — `add`, `list`, `done` and so on — is `subparsers`. You get one top-level parser plus a dedicated sub-parser per command, each with its own arguments.

### Parallels with JS/TS/Node:

- **venv ≈ `nvm` + `node_modules` rolled into one mechanism.** Node isolates projects by default (a local `node_modules`); Python has no isolation until you explicitly create and activate a venv.
- **pyproject.toml ≈ package.json**, except that linter and type-checker config lives inside it under `[tool.x]`, not in separate files like `.eslintrc` or `tsconfig.json`. Many tools still support standalone config files as well.
- **argparse ≈ commander/yargs**, but nothing to install — it's part of the standard library, the way `readline` used to be built into Node.
- **pip without venv ≈ `npm install -g`** — a global install that breaks the moment two projects want different versions. In Python, unfortunately, that's the *default* behavior, not an opt-in flag.

## What we're adding to the project

We're building the `taskman` CLI task-manager skeleton from scratch. It is two files: a `pyproject.toml` with project metadata, and a single `main.py`. That `main.py` holds an `add <text>` command, which stores a task in an **in-memory list** and prints a confirmation.

Persistence (JSON, then SQLite) shows up in chapter 08. The goal right now is only to live through the full cycle with your own hands: venv → pyproject.toml → argparse → run it.

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

- `subparsers = parser.add_subparsers(dest="command", required=True)` — `dest="command"` puts the chosen subcommand's name into `args.command`. The `required=True` part makes argparse print an error and exit when no subcommand is given. Without it, a missing subcommand was not treated as an error in some Python versions.
- `list[dict]` — since Python 3.9, the built-in generics `list[int]` and `dict[str, int]` do not require `from typing import List, Dict`. It is closer to writing `string[]` in TS than to importing a generic from a separate module.
- `if __name__ == "__main__": main()` — guarantees that `python main.py` runs `main()`. Later `main.py` may become a module that something else imports, for example the tests in chapter 09. Then the import will not trigger the CLI logic as a side effect.

## Check yourself

1. `python3 -m venv .venv` creates a whole structure: an interpreter copy or symlink plus its own site-packages. Why not just a list of installed packages? And how is that different from the way npm isolates dependencies through `node_modules`?
2. What happens if you run `pip install` without an activated venv, on a project where the system Python is already used by something else? Why does this lead to hard-to-track-down bugs in practice?
3. Why do you need `if __name__ == "__main__":` at all, if you could just call `main()` as the last line of the file unconditionally? What changes if `main.py` gets imported from another file?
4. How is the `[project]` section of `pyproject.toml` different from `package.json` in managing dependency versions? What does `pyproject.toml` **not** solve on its own, without extra tooling?
5. Why does `add_subparsers` require `required=True` as an explicit parameter, instead of treating a subcommand as required by default?

<details>
<summary>Answers</summary>

1. Isolation in Python is about more than packages. It is also about which interpreter you are using at all. A venv pins exactly which `python` and `pip` binaries you get. A machine can hold several Python versions side by side. Without an explicit environment, `pip install` lands in the site-packages of whichever interpreter comes first on `PATH`. Node already bakes package-version isolation into `node_modules` per project, and runtime-version management is a separate concern there (`nvm`). A venv in Python bundles both concerns into one mechanism.
2. The package gets installed into the global site-packages of the system (or first-on-`PATH`) Python. If two different projects on the machine need different versions of the same library, the later install silently overwrites the earlier one. The other project then starts failing with no apparent cause in its own code. The real cause is that someone ran `pip install` without a venv in a different terminal.
3. Without `if __name__ == "__main__":`, an unconditional call to `main()` would fire on **every** import of the file. That includes chapter 09, where tests import `add_task` or `build_parser` from `main.py` without wanting to run the CLI. The variable `__name__` equals `"__main__"` only when the file is the process entry point. On import it equals the module's own name, so the code inside the `if` never runs.
4. `pyproject.toml` describes metadata and the version ranges you are willing to accept. On its own it does not produce a reproducible lockfile with exact pinned versions of the whole dependency tree. Compare that with `package-lock.json` and `yarn.lock`, which are generated automatically and pin the whole tree. Getting a real lockfile in Python means bringing in a separate tool on top (poetry, uv, pip-tools) — covered in the modules-and-packaging chapter.
5. Historically argparse allowed subparsers to be optional. That let you build a CLI where having no subcommand is a valid case, for example to show help instead. The behavior was kept as an explicit opt-in, not made the new default, so that existing code would not break on Python upgrades. It is a typical example of how conservative the standard library is about changing defaults between minor releases.

</details>

## Common mistake

A JS/TS developer is used to dependencies being local and isolated: `node_modules` gets created automatically on `npm install`, wherever you happen to be. Such a developer will almost certainly forget to activate the venv before `pip install` at least once.

In Node, a missing isolation step usually fails loudly and immediately: with no `node_modules`, nothing works, and "module not found" is obvious. In Python the package **installs successfully anyway** — just not where you thought.

The script might even import it fine, if that package also happens to exist in the system Python. This creates a false sense that everything works. It holds until you move to another machine, or to a continuous integration (CI) run where that "accidental" global package does not exist.

The second common problem is confusing `python` and `python3` as binary names. On some systems `python` may not exist at all, or may point at Python 2. That happens on older Linux distributions, and on a fresh macOS with no Python explicitly installed.

Inside an activated venv this doesn't matter: `python` always points at the interpreter the venv was created with. Before activation it can matter a lot. Running `python script.py` may fail with a syntax error on f-strings or type hints, which Python 2 simply does not understand.
