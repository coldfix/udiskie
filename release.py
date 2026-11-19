#!/usr/bin/env python3
"""Create a local release: python3 release.py [VERSION]."""

import argparse
import datetime
import os
import readline
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "version", nargs="?", help="new version (prompt if omitted)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    os.chdir(Path(__file__).resolve().parent)

    version_file = Path("udiskie/__init__.py")
    current_version = exec_file(version_file)["__version__"]
    print(f"Current version: {current_version}")

    new_version = args.version or prompt_version(current_version)

    tag = f"v{new_version}"
    git("check-ref-format", f"refs/tags/{tag}")

    if git("tag", "--list", tag):
        sys.exit(f"Tag already exists: {tag}")

    changelog = Path("CHANGES.rst")
    notes = edit_release_notes(current_version)
    update_changelog(changelog, new_version, notes)
    version_file.write_text(f'__version__ = "{new_version}"')

    run("make", "-BC", "lang")
    git("diff", "--check")
    run(
        "git",
        "commit",
        "--only",
        "-m",
        f"Release udiskie {tag}",
        "-m",
        notes,
        "--",
        str(version_file),
        str(changelog),
        "lang",
    )
    run("git", "tag", tag)


def prompt_version(current_version):
    prefix, patch = current_version.rsplit(".", 1)
    next_version = f"{prefix}.{int(patch) + 1}"
    readline.set_startup_hook(lambda: readline.insert_text(next_version))
    try:
        return input("New version: ").strip()
    finally:
        readline.set_startup_hook()


def edit_release_notes(current_version):
    """Draft release notes and let the user edit them in a temporary file."""
    changes = git("log", "--format=- %s", f"v{current_version}..HEAD")
    with tempfile.TemporaryDirectory(prefix="udiskie-release-") as directory:
        notes_file = Path(directory) / "release-notes.rst"
        notes_file.write_text(changes + "\n")
        open_editor(str(notes_file))
        return notes_file.read_text().strip()


def update_changelog(changelog, new_version, notes):
    """Prepend the dated release notes to the changelog."""
    heading, previous = changelog.read_text().split("\n\n", 1)
    underline = "~" * len(new_version)
    today = datetime.date.today().strftime("%d.%m.%Y")
    insertion = f"""
{new_version}
{underline}
Date: {today}

{notes}

"""
    changelog.write_text(f"{heading}\n{insertion}\n{previous}")
    print(insertion)


def exec_file(path):
    """Execute a python file and return the `globals` dictionary."""
    namespace = {}
    exec(path.read_text(), namespace, namespace)
    return namespace


def open_editor(filename):
    editor = shlex.split(git("var", "GIT_EDITOR"))
    run(*editor, filename)


def update_version_file(version_file, current_version, new_version):
    """Update the version in udiskie/__init__.py."""


def git(*args):
    return run("git", *args, stdout=subprocess.PIPE).stdout.strip()


def run(*command, **kwargs):
    bold_white = "\033[1;37m"
    reset = "\033[0m"
    print(f"{bold_white}{shlex.join(command)}{reset}", file=sys.stderr)
    return subprocess.run(command, check=True, text=True, **kwargs)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, EOFError, KeyboardInterrupt) as error:
        sys.exit(str(error) or "Release cancelled.")
