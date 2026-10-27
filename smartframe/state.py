"""The tool's own memory, in data/state.json.

It records every picture this tool has put on the TV (its content id plus the date stamp the tool
gave it), so that tidying up and undo only ever remove those. Photos the owner put on the TV
themselves are never in this list, so they are never touched.
"""
import json
import os
import time


class State:
    def __init__(self, path):
        self.path = path
        self.data = {"uploaded": [], "current": None, "last_run": 0, "last_date": "", "photo_index": -1, "last_photo": ""}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except (OSError, json.JSONDecodeError):
                pass   # a damaged state file is treated as empty; nothing on the TV is deleted

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    @property
    def uploaded(self):
        return self.data["uploaded"]

    def add_upload(self, content_id, image_date):
        self.data["uploaded"].append({"id": content_id, "image_date": image_date, "at": time.time()})
        self.data["current"] = content_id

    def forget(self, content_id):
        self.data["uploaded"] = [u for u in self.data["uploaded"] if u["id"] != content_id]
        if self.data.get("current") == content_id:
            self.data["current"] = None

    def mark_run(self, date_text):
        self.data["last_run"] = time.time()
        self.data["last_date"] = date_text
