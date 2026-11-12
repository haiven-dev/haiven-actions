#!/usr/bin/env python3
"""Open or refresh the one pull request that promotes a source branch.

The description lists, by conventional-commit type, every commit the source
branch carries that the target branch lacks. It is regenerated between two HTML
comment markers on each run, so text a reviewer writes outside them is kept. An
open pull request from the source into the target that was opened by hand is
adopted: the generated block is appended to its description and its title is
left alone.

Nothing is versioned, tagged or released here.

Environment:
  PROMOTION_SOURCE  branch whose commits are promoted (the pull request head)
  PROMOTION_TARGET  branch they are promoted into (the pull request base)
  PROMOTION_TITLE   title for a newly opened pull request (optional)
  PROMOTION_NOTE    paragraph placed after the commit list (optional)
  GITHUB_TOKEN      token with pull-requests: write on GITHUB_REPOSITORY

The source and target may instead be passed as the two positional arguments.
Git runs in the current directory, which must be a clone of the repository with
an ``origin`` remote.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BEGIN = "<!-- promotion-pr:begin -->"
END = "<!-- promotion-pr:end -->"
# GitHub rejects descriptions over 65536 characters; leave room for the rest.
MAX_LIST = 50000
GIT = shutil.which("git")

BREAKING = re.compile(r"^- [a-z]+(\([^)]*\))?!: ")
FEATURE = re.compile(r"^- feat(\([^)]*\))?: ")
FIX = re.compile(r"^- fix(\([^)]*\))?: ")


class Failure(RuntimeError):
    """A safe, operator-readable refusal or API failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def captured(text: str) -> str:
    """Return text as POSIX command substitution would: no trailing newlines."""
    return text.rstrip("\n")


def git(*args: str, cwd: Path | None = None) -> str:
    require(GIT is not None, "git executable not found on PATH")
    completed = subprocess.run(
        [GIT, *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise Failure(
            f"git {' '.join(args)} failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout


def validate_branch(value: str, label: str) -> str:
    require(bool(value), f"{label} is required")
    require(GIT is not None, "git executable not found on PATH")
    completed = subprocess.run(
        [GIT, "check-ref-format", f"refs/heads/{value}"],
        check=False,
        capture_output=True,
    )
    require(completed.returncode == 0, f"{label} is not a valid branch name: {value}")
    return value


class GitHub:
    def __init__(
        self, token: str, repo: str, api_url: str = "https://api.github.com"
    ) -> None:
        require(bool(token), "GITHUB_TOKEN is required")
        require("/" in repo, "GITHUB_REPOSITORY is required")
        self.token = token
        self.repo = repo
        self.api_url = api_url.rstrip("/")

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.api_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise Failure(
                f"GitHub API {method} {path} failed ({error.code}): {detail}"
            ) from error

    def open_pull_request(self, head: str, base: str) -> int | None:
        owner = self.repo.split("/", 1)[0]
        query = urlencode(
            {"state": "open", "head": f"{owner}:{head}", "base": base, "per_page": 1}
        )
        pulls = self.request("GET", f"/repos/{self.repo}/pulls?{query}")
        require(isinstance(pulls, list), "pull request listing is invalid")
        if not pulls:
            return None
        return int(pulls[0]["number"])

    def body(self, number: int) -> str:
        pull = self.request("GET", f"/repos/{self.repo}/pulls/{number}")
        require(isinstance(pull, dict), f"pull request #{number} response is invalid")
        return pull.get("body") or ""

    def create(self, head: str, base: str, title: str, body: str) -> str:
        pull = self.request(
            "POST",
            f"/repos/{self.repo}/pulls",
            {"head": head, "base": base, "title": title, "body": body},
        )
        require(isinstance(pull, dict), "pull request creation response is invalid")
        return str(pull.get("html_url", ""))

    def edit_body(self, number: int, body: str) -> str:
        pull = self.request(
            "PATCH", f"/repos/{self.repo}/pulls/{number}", {"body": body}
        )
        require(isinstance(pull, dict), "pull request update response is invalid")
        return str(pull.get("html_url", ""))


def grouped(subjects: str) -> str:
    """Group ``- subject (sha)`` lines in the order a reviewer reads them.

    Anything that is not a conventional feat or fix, including a subject that
    is not conventional at all, falls under "Other changes".
    """
    breaking = feat = fix = other = ""
    for line in subjects.split("\n"):
        if BREAKING.search(line):
            breaking += line + "\n"
        elif FEATURE.search(line):
            feat += line + "\n"
        elif FIX.search(line):
            fix += line + "\n"
        else:
            other += line + "\n"
    output = ""
    for heading, lines in (
        ("Breaking changes", breaking),
        ("Features", feat),
        ("Bug fixes", fix),
        ("Other changes", other),
    ):
        if lines:
            output += f"### {heading}\n\n{lines}\n"
    return captured(output)


def promotion_block(head: str, base: str, subjects: str, note: str) -> str:
    count = sum(1 for line in subjects.split("\n") if line.startswith("- "))
    listing = grouped(subjects)
    if len(listing) > MAX_LIST:
        listing = (
            listing[:MAX_LIST]
            + "\n\n_(truncated: see the Commits tab for the full list)_\n"
        )
    block = f"{BEGIN}\n"
    block += f"## Promotes `{head}` into `{base}`\n\n"
    block += f"{count} commit(s) on `{head}` are not on `{base}` yet.\n\n"
    block += f"{listing}\n\n"
    if note:
        block += f"{note}\n\n"
    block += "_The Promotion PR workflow regenerates this block on every push to"
    block += f" `{head}` or `{base}`. Edit only outside it._\n"
    block += f"{END}\n"
    return captured(block)


def replace_block(current: str, block: str) -> str:
    """Swap the marked block in ``current``, or append it when absent."""
    lines = current.split("\n")
    begins = [index for index, line in enumerate(lines) if line == BEGIN]
    ends = [index for index, line in enumerate(lines) if line == END]
    if not begins and not ends:
        lines.extend(["", block])
    else:
        require(
            len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0],
            "pull request body has malformed promotion markers",
        )
        lines[begins[0] : ends[0] + 1] = [block]
    return captured("\n".join(lines) + "\n")


def promote(
    api: Any, head: str, base: str, title: str, note: str, cwd: Path | None = None
) -> str:
    """Open or refresh the promotion pull request; return the log message."""
    git(
        "fetch",
        "--quiet",
        "--no-tags",
        "origin",
        f"+refs/heads/{base}:refs/remotes/origin/{base}",
        f"+refs/heads/{head}:refs/remotes/origin/{head}",
        cwd=cwd,
    )
    revisions = f"origin/{base}..origin/{head}"

    number = api.open_pull_request(head, base)

    if int(
        git("rev-list", "--count", "--no-merges", revisions, cwd=cwd).strip()
    ) == 0:
        return (
            f"{head} has no non-merge commits missing from {base}; "
            "nothing to promote."
        )

    subjects = captured(
        git("log", "--no-merges", "--reverse", "--format=- %s (%h)", revisions, cwd=cwd)
    )
    block = promotion_block(head, base, subjects, note)

    if number is None:
        return api.create(head, base, title, block + "\n")

    current = captured(api.body(number).replace("\r", ""))
    updated = replace_block(current, block)
    if updated == current:
        return f"Pull request #{number} is already current."
    url = api.edit_body(number, updated + "\n")
    return captured(f"{url}\nRefreshed pull request #{number}.".lstrip("\n"))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        require(len(args) in {0, 2}, "usage: promotion-pr.py [<source> <target>]")
        head = args[0] if args else os.environ.get("PROMOTION_SOURCE", "")
        base = args[1] if args else os.environ.get("PROMOTION_TARGET", "")
        head = validate_branch(head.strip(), "source branch")
        base = validate_branch(base.strip(), "target branch")
        require(head != base, "source and target branches must differ")
        title = (
            os.environ.get("PROMOTION_TITLE") or f"chore: promote {head} into {base}"
        )
        note = os.environ.get("PROMOTION_NOTE", "")
        api = GitHub(
            os.environ.get("GITHUB_TOKEN", ""),
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        )
        print(promote(api, head, base, title, note))
    except Failure as error:
        print(f"promotion pull request failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
