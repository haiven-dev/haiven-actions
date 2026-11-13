"""Tests for the promotion pull-request maintainer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("promotion-pr.py")
spec = importlib.util.spec_from_file_location("promotion_pr", SCRIPT)
promotion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promotion)


NOTHING_TO_PROMOTE = (
    "sdk-dev has no non-merge commits missing from main, and its merge commits"
    " change no files; nothing to promote."
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()


class FakeAPI:
    """Records pull-request calls the way GitHub would answer them."""

    def __init__(self, number=None, body=""):
        self.number = number
        self.stored_body = body
        self.lookups = []
        self.created = []
        self.edited = []

    def open_pull_request(self, head, base):
        self.lookups.append((head, base))
        return self.number

    def body(self, number):
        assert number == self.number, number
        return self.stored_body

    def create(self, head, base, title, body):
        self.created.append((head, base, title, body))
        return "https://github.com/haiven-dev/example/pull/7"

    def edit_body(self, number, body):
        self.edited.append((number, body))
        self.stored_body = body
        return f"https://github.com/haiven-dev/example/pull/{number}"


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="promotion action ü ")
        root = Path(self.temp.name)
        self.origin = root / "origin repo.git"
        self.clone = root / "clone ü"
        git(root, "init", "-q", "--bare", str(self.origin))
        git(root, "clone", "-q", str(self.origin), str(self.clone))
        git(self.clone, "config", "user.name", "Test")
        git(self.clone, "config", "user.email", "test@example.com")
        git(self.clone, "checkout", "-q", "-b", "main")
        self.commit("base.txt", "chore: initial commit")
        git(self.clone, "push", "-q", "origin", "main")
        git(self.clone, "checkout", "-q", "-b", "sdk-dev")

    def tearDown(self):
        self.temp.cleanup()

    def commit(self, name: str, subject: str) -> str:
        path = self.clone / name
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(previous + subject + "\n", encoding="utf-8")
        git(self.clone, "add", name)
        git(self.clone, "commit", "-qm", subject)
        return git(self.clone, "rev-parse", "--short", "HEAD")

    def push(self) -> None:
        git(self.clone, "push", "-q", "origin", "sdk-dev")

    def promote(self, api, title="chore: promote sdk-dev into main", note=""):
        return promotion.promote(api, "sdk-dev", "main", title, note, cwd=self.clone)

    def mixed_history(self) -> dict[str, str]:
        shas = {
            "fix": self.commit("a.txt", "fix(api): reject empty names"),
            "other": self.commit("b.txt", "docs: explain the integration branch"),
            "feat": self.commit("c.txt", "feat: add the lobby contract"),
            "breaking": self.commit("d.txt", "feat(ws)!: rename server to community"),
            "loose": self.commit("e.txt", "Tidy up the README"),
        }
        git(self.clone, "checkout", "-q", "-b", "side")
        shas["side"] = self.commit("f.txt", "fix: retry the handshake")
        git(self.clone, "checkout", "-q", "sdk-dev")
        git(self.clone, "merge", "-q", "--no-ff", "-m", "Merge side", "side")
        self.push()
        return shas

    def expected_block(self, shas: dict[str, str], note: str = "") -> str:
        note_text = f"{note}\n\n" if note else ""
        return (
            "<!-- promotion-pr:begin -->\n"
            "## Promotes `sdk-dev` into `main`\n\n"
            "6 commit(s) on `sdk-dev` are not on `main` yet.\n\n"
            "### Breaking changes\n\n"
            f"- feat(ws)!: rename server to community ({shas['breaking']})\n\n"
            "### Features\n\n"
            f"- feat: add the lobby contract ({shas['feat']})\n\n"
            "### Bug fixes\n\n"
            f"- fix(api): reject empty names ({shas['fix']})\n"
            f"- fix: retry the handshake ({shas['side']})\n\n"
            "### Other changes\n\n"
            f"- docs: explain the integration branch ({shas['other']})\n"
            f"- Tidy up the README ({shas['loose']})\n\n"
            f"{note_text}"
            "_The Promotion PR workflow regenerates this block on every push to"
            " `sdk-dev` or `main`. Edit only outside it._\n"
            "<!-- promotion-pr:end -->"
        )

    def test_opens_a_pull_request_grouping_commits_by_conventional_type(self):
        shas = self.mixed_history()
        api = FakeAPI()

        message = self.promote(api, note="Merge with a **merge commit**.")

        self.assertEqual(message, "https://github.com/haiven-dev/example/pull/7")
        self.assertEqual(api.lookups, [("sdk-dev", "main")])
        self.assertEqual(
            api.created,
            [
                (
                    "sdk-dev",
                    "main",
                    "chore: promote sdk-dev into main",
                    self.expected_block(shas, "Merge with a **merge commit**.") + "\n",
                )
            ],
        )
        self.assertEqual(api.edited, [])

    def test_nothing_to_promote_writes_nothing(self):
        self.push()
        api = FakeAPI(number=3, body="kept")

        message = self.promote(api)

        self.assertEqual(
            message,
            NOTHING_TO_PROMOTE,
        )
        self.assertEqual((api.created, api.edited), ([], []))

    def back_merge(self, *, edit: str = "") -> None:
        """Land a commit on main, then merge main back into sdk-dev.

        With ``edit``, the merge commit also changes a file, the way a conflict
        resolution would.
        """
        git(self.clone, "checkout", "-q", "main")
        self.commit("release.txt", "chore: release")
        git(self.clone, "push", "-q", "origin", "main")
        git(self.clone, "checkout", "-q", "sdk-dev")
        if not edit:
            git(self.clone, "merge", "-q", "--no-ff", "-m", "Merge main", "main")
        else:
            git(self.clone, "merge", "-q", "--no-ff", "--no-commit", "main")
            (self.clone / "release.txt").write_text(edit, encoding="utf-8")
            git(self.clone, "add", "release.txt")
            git(self.clone, "commit", "-qm", "Merge main")
        self.push()

    def test_merge_commit_only_difference_writes_nothing(self):
        self.back_merge()
        self.assertEqual(git(self.clone, "rev-list", "--count", "main..sdk-dev"), "1")
        api = FakeAPI(number=3, body="kept")

        message = self.promote(api)

        self.assertEqual(
            message,
            NOTHING_TO_PROMOTE,
        )
        self.assertEqual((api.created, api.edited), ([], []))

    def test_a_no_op_back_merge_opens_nothing(self):
        self.back_merge()
        api = FakeAPI()

        message = self.promote(api)

        self.assertEqual(message, NOTHING_TO_PROMOTE)
        self.assertEqual((api.created, api.edited), ([], []))

    def test_target_commits_after_a_back_merge_are_not_a_difference(self):
        self.back_merge()
        git(self.clone, "checkout", "-q", "main")
        self.commit("later.txt", "fix: patch the release again")
        git(self.clone, "push", "-q", "origin", "main")
        git(self.clone, "checkout", "-q", "sdk-dev")
        api = FakeAPI()

        message = self.promote(api)

        self.assertEqual(message, NOTHING_TO_PROMOTE)
        self.assertEqual((api.created, api.edited), ([], []))

    def test_a_merge_commit_that_changes_files_is_promoted(self):
        self.back_merge(edit="resolved by hand\n")
        api = FakeAPI()

        self.promote(api)

        self.assertEqual(len(api.created), 1)
        body = api.created[0][3]
        self.assertIn("0 commit(s) on `sdk-dev` are not on `main` yet.", body)
        self.assertIn(
            "Only merge commits on `sdk-dev` are missing from `main`, and they"
            " change files. See the Files changed tab.",
            body,
        )
        self.assertNotIn("###", body)

    def test_a_merge_commit_that_changes_files_refreshes_an_open_pull_request(
        self,
    ):
        self.back_merge(edit="resolved by hand\n")
        api = FakeAPI(number=3, body="Opened by hand.")

        message = self.promote(api)

        self.assertEqual(
            message,
            "https://github.com/haiven-dev/example/pull/3\n"
            "Refreshed pull request #3.",
        )
        self.assertEqual(api.created, [])
        self.assertEqual(len(api.edited), 1)
        self.assertIn("they change files", api.edited[0][1])

    def test_a_commit_after_a_back_merge_is_promoted(self):
        self.back_merge()
        added = self.commit("g.txt", "feat: add the lobby contract")
        self.push()
        api = FakeAPI()

        self.promote(api)

        self.assertEqual(len(api.created), 1)
        body = api.created[0][3]
        self.assertIn("1 commit(s) on `sdk-dev` are not on `main` yet.", body)
        self.assertIn(
            f"### Features\n\n- feat: add the lobby contract ({added})\n", body
        )
        self.assertNotIn("Merge main", body)

    def test_adopts_a_hand_opened_pull_request_and_keeps_its_text(self):
        shas = self.mixed_history()
        api = FakeAPI(number=12, body="Opened by hand.\r\n\r\nPlease review.\r\n")

        message = self.promote(api)

        self.assertEqual(
            message,
            "https://github.com/haiven-dev/example/pull/12\n"
            "Refreshed pull request #12.",
        )
        self.assertEqual(api.created, [])
        self.assertEqual(
            api.edited,
            [
                (
                    12,
                    "Opened by hand.\n\nPlease review.\n\n"
                    + self.expected_block(shas)
                    + "\n",
                )
            ],
        )

    def test_regenerates_only_the_marked_block(self):
        shas = self.mixed_history()
        stale = (
            "Reviewer intro.\n"
            "<!-- promotion-pr:begin -->\nold list\n<!-- promotion-pr:end -->\n"
            "Reviewer footer."
        )
        api = FakeAPI(number=5, body=stale)

        self.promote(api)

        self.assertEqual(
            api.edited,
            [
                (
                    5,
                    "Reviewer intro.\n"
                    + self.expected_block(shas)
                    + "\nReviewer footer.\n",
                )
            ],
        )

    def test_refuses_malformed_markers_without_editing_the_pull_request(self):
        self.mixed_history()
        malformed_bodies = (
            f"Intro.\n{promotion.BEGIN}\nstale block\nReviewer footer.",
            f"Intro.\n{promotion.END}\nReviewer footer.",
            (
                f"{promotion.BEGIN}\nfirst\n{promotion.END}\n"
                f"{promotion.BEGIN}\nsecond\n{promotion.END}"
            ),
            f"{promotion.END}\n{promotion.BEGIN}",
        )
        for body in malformed_bodies:
            with self.subTest(body=body):
                api = FakeAPI(number=5, body=body)

                with self.assertRaisesRegex(
                    promotion.Failure, "malformed promotion markers"
                ):
                    self.promote(api)

                self.assertEqual(api.edited, [])

    def test_a_current_description_is_left_alone(self):
        self.mixed_history()
        api = FakeAPI(number=5, body="Intro.")
        self.promote(api)
        self.assertEqual(len(api.edited), 1)

        message = self.promote(api)

        self.assertEqual(message, "Pull request #5 is already current.")
        self.assertEqual(len(api.edited), 1)

    def test_new_commits_refresh_the_block(self):
        self.mixed_history()
        api = FakeAPI(number=5, body="")
        self.promote(api)
        added = self.commit("g.txt", "fix: close idle sockets")
        self.push()

        self.promote(api)

        self.assertEqual(len(api.edited), 2)
        self.assertIn(f"- fix: close idle sockets ({added})\n", api.edited[1][1])
        self.assertIn("7 commit(s) on `sdk-dev`", api.edited[1][1])

    def test_an_overlong_list_is_truncated(self):
        subjects = "\n".join(
            f"- fix: change {index:05d} (abc1234)" for index in range(2000)
        )

        block = promotion.promotion_block("sdk-dev", "main", subjects, "")

        listing = block.split("yet.\n\n", 1)[1]
        self.assertIn(
            "\n\n_(truncated: see the Commits tab for the full list)_\n\n\n_The",
            listing,
        )
        self.assertEqual(len(listing.split("\n\n_(truncated")[0]), promotion.MAX_LIST)
        self.assertIn("2000 commit(s)", block)

    def test_main_reads_branches_and_title_from_the_environment(self):
        environment = {
            "PROMOTION_SOURCE": "sdk-dev",
            "PROMOTION_TARGET": "dev",
            "PROMOTION_TITLE": "",
            "PROMOTION_NOTE": "Note.",
            "GITHUB_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "haiven-dev/example",
        }
        with (
            mock.patch.dict(promotion.os.environ, environment, clear=True),
            mock.patch.object(promotion, "promote", return_value="done") as run,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(promotion.main([]), 0)

        api, head, base, title, note = run.call_args.args
        self.assertEqual((head, base), ("sdk-dev", "dev"))
        self.assertEqual(title, "chore: promote sdk-dev into dev")
        self.assertEqual(note, "Note.")
        self.assertEqual(api.repo, "haiven-dev/example")

    def test_main_refuses_invalid_branches(self):
        environment = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "haiven-dev/example"}
        for source, target in (("", "main"), ("sdk-dev", "bad..ref"), ("main", "main")):
            with (
                self.subTest(source=source, target=target),
                mock.patch.dict(promotion.os.environ, environment, clear=True),
                mock.patch.object(promotion, "promote") as run,
                mock.patch("builtins.print"),
            ):
                self.assertEqual(promotion.main([source, target]), 1)
                run.assert_not_called()


class GitHubClientTests(unittest.TestCase):
    def test_lookup_is_limited_to_same_repository_heads(self):
        api = promotion.GitHub("t", "haiven-dev/example")
        with mock.patch.object(api, "request", return_value=[{"number": 9}]) as request:
            self.assertEqual(api.open_pull_request("sdk-dev", "main"), 9)
        method, path = request.call_args.args
        self.assertEqual(method, "GET")
        self.assertEqual(
            path,
            "/repos/haiven-dev/example/pulls?state=open&head=haiven-dev%3Asdk-dev"
            "&base=main&per_page=1",
        )

    def test_missing_pull_request_and_null_body(self):
        api = promotion.GitHub("t", "haiven-dev/example")
        with mock.patch.object(api, "request", return_value=[]):
            self.assertIsNone(api.open_pull_request("sdk-dev", "main"))
        with mock.patch.object(api, "request", return_value={"body": None}):
            self.assertEqual(api.body(4), "")


if __name__ == "__main__":
    unittest.main()
