"""Upload, select and tidy-up logic against a pretend Frame. Run: python -m unittest discover tests"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from smartframe import cli
from smartframe.state import State
from tests.fake_frame import FakeFrame

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER = [{"content_id": "MY_F0001", "image_date": "2024:01:01 10:00:00"},
         {"content_id": "MY_F0002", "image_date": "2024:02:01 10:00:00"}]


class FrameTests(unittest.TestCase):
    def setUp(self):
        os.environ["SMARTFRAME_CHROME"] = "/nonexistent/chrome"   # the quick Pillow picture is enough here
        self.dir = tempfile.mkdtemp(prefix="smartframe-test-")

    def tearDown(self):
        if getattr(self, "fake", None):
            self.fake.stop()
        shutil.rmtree(self.dir, ignore_errors=True)
        os.environ.pop("SMARTFRAME_CHROME", None)

    def start(self, **kw):
        self.fake = FakeFrame(photos=kw.pop("photos", OWNER), **kw).start()
        return self.fake

    def config(self, **extra):
        cfg = {"frame": {"ip": "127.0.0.1", "port": self.fake.port}, "timezone": "Australia/Melbourne",
               "photos": {"folder": os.path.join(REPO, "samples", "photos")},
               "blocks": [{"type": "date"}, {"type": "reminders"}, {"type": "quote", "text": "A test line."}],
               "style": "gallery"}
        cfg.update(extra)
        path = os.path.join(self.dir, "config.json")
        with open(path, "w") as f:
            json.dump(cfg, f)
        return path

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(args))
        return code, out.getvalue()

    def state(self):
        return State(os.path.join(self.dir, "data", "state.json"))

    def test_run_uploads_selects_and_removes_only_its_own(self):
        fake = self.start()
        cfg = self.config()
        for _ in range(3):
            code, out = self.cli("--config", cfg, "run")
            self.assertEqual(code, 0, out)
        self.assertEqual(fake.uploads, ["MY_F0003", "MY_F0004", "MY_F0005"])
        self.assertEqual(fake.ids(), ["MY_F0001", "MY_F0002", "MY_F0005"])   # owner's photos untouched
        self.assertEqual(fake.current, "MY_F0005")
        self.assertEqual(fake.deletes, ["MY_F0003", "MY_F0004"])
        self.assertEqual([u["id"] for u in self.state().uploaded], ["MY_F0005"])

    def test_keep_previous(self):
        fake = self.start()
        cfg = self.config(keep_previous=1)
        for _ in range(3):
            self.assertEqual(self.cli("--config", cfg, "run")[0], 0)
        self.assertEqual(fake.ids(), ["MY_F0001", "MY_F0002", "MY_F0004", "MY_F0005"])

    def test_undo_leaves_the_owners_photos(self):
        fake = self.start()
        cfg = self.config(keep_previous=5)
        for _ in range(2):
            self.cli("--config", cfg, "run")
        code, out = self.cli("--config", cfg, "undo", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(fake.ids(), ["MY_F0001", "MY_F0002"])
        self.assertEqual(self.state().uploaded, [])

    def test_upload_that_never_says_image_added_is_found_not_resent(self):
        fake = self.start(silent_upload=True)
        cfg = self.config()
        code, out = self.cli("--config", cfg, "run")
        self.assertEqual(code, 0, out)
        self.assertEqual(fake.uploads, ["MY_F0003"])   # one upload, no second copy
        self.assertEqual(fake.current, "MY_F0003")
        self.assertEqual([u["id"] for u in self.state().uploaded], ["MY_F0003"])

    def test_refused_token_says_to_pair_again(self):
        self.start(refuse=True)
        cfg = self.config()
        code, out = self.cli("--config", cfg, "run")
        self.assertEqual(code, 1)
        self.assertIn("smartframe pair", out)

    def test_an_id_the_tv_reused_after_a_reset_is_left_alone(self):
        # The record says this tool uploaded MY_F0001, but the TV now lists MY_F0001 with another
        # date stamp (it was reset and the owner uploaded their own photo): it must stay.
        fake = self.start()
        cfg = self.config()
        st = self.state()
        st.add_upload("MY_F0001", "2026:05:05 05:00:00")
        st.save()
        code, out = self.cli("--config", cfg, "undo", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(fake.ids(), ["MY_F0001", "MY_F0002"])
        self.assertEqual(fake.deletes, [])
        self.assertIn("Left 1 alone", out)

    def test_check_is_read_only(self):
        fake = self.start()
        cfg = self.config()
        code, out = self.cli("--config", cfg, "check")
        self.assertEqual(code, 0, out)
        self.assertIn("Art Mode:        supported", out)
        self.assertIn("2.03", out)
        self.assertEqual((fake.uploads, fake.selects, fake.deletes), ([], [], []))

    def test_when_due_waits_for_the_tv(self):
        self.start()
        cfg = self.config()
        self.fake.stop()   # the TV is off
        self.fake = None
        code, out = self.cli("--config", cfg, "run", "--when-due")
        self.assertEqual((code, out), (0, ""))   # quiet; the next run tries again


if __name__ == "__main__":
    unittest.main()
