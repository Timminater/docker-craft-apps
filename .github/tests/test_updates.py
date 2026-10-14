import base64
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/update-craft-apps.py"
spec = importlib.util.spec_from_file_location("updater", SCRIPT)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def release(app, tag="v1.2.3"):
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
        {"name": f"{app}-{tag[1:]}-linux-{arch}.deb", "size": 123,
         "browser_download_url": f"https://github.com/storytold/{app}/releases/download/{tag}/{app}-{tag[1:]}-linux-{arch}.deb"}
        for arch in ("x86_64", "aarch64")
    ]}


def desktop(app):
    return f"[Desktop Entry]\nType=Application\nName={app.title()}\nExec={app} %F\nIcon=ai.storyteller.{app}\n"


class UpdateTests(unittest.TestCase):
    def test_catalog_is_deduplicated_and_external_links_ignored(self):
        text = '<a href="/apps/photocraft">Photo</a><a href="/apps/photocraft">Again</a><a href="https://getartcraft.com/apps/newcraft">New</a><a href="https://evil.invalid/apps/othercraft">Ignore</a>'
        self.assertEqual(updater.discover(text), {"photocraft", "newcraft"})

    def test_changed_catalog_fails_closed(self):
        with self.assertRaises(ValueError):
            updater.discover('<a href="/unrelated">Empty</a>')

    def test_missing_architecture_or_wrong_download_url_rejected(self):
        data = release("photocraft")
        self.assertEqual(updater.check_release("photocraft", data), "v1.2.3")
        data["assets"].pop()
        with self.assertRaises(ValueError):
            updater.check_release("photocraft", data)
        data = release("photocraft")
        data["assets"][0]["browser_download_url"] = "https://evil.invalid/package.deb"
        with self.assertRaises(ValueError):
            updater.check_release("photocraft", data)

    def test_unstable_release_rejected(self):
        for field in ("draft", "prerelease"):
            data = release("photocraft")
            data[field] = True
            with self.assertRaises(ValueError):
                updater.check_release("photocraft", data)

    def test_unexpected_launcher_rejected(self):
        self.assertEqual(updater.check_desktop("newcraft", desktop("newcraft")), "Newcraft")
        with self.assertRaises(ValueError):
            updater.check_desktop("newcraft", desktop("newcraft").replace("Exec=newcraft %F", "Exec=sh -c something"))

    def fixture(self, directory):
        root = Path(directory)
        for name in ("Dockerfile", "Dockerfile.aarch64", "root/defaults/autostart", "root/defaults/autostart_wayland", "root/defaults/menu.xml", "root/defaults/menu_wayland.xml"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(updater.ROOT / name, target)
        (root / updater.MANIFEST).write_text(json.dumps({"photocraft": "v1.0.0"}))
        return root

    def get(self, url):
        if url == updater.CATALOG:
            return '<a href="/apps/photocraft">Photo</a><a href="/apps/newcraft">New</a>'
        if url.startswith(updater.CATALOG + "/"):
            app = url.rsplit("/", 1)[1]
            return f'<a href="https://github.com/storytold/{app}">Source</a>'
        app = url.split("/")[5]
        if url.endswith("/releases/latest"):
            return json.dumps(release(app))
        return json.dumps({"content": base64.b64encode(desktop(app).encode()).decode()})

    def test_new_app_updates_both_architectures_and_desktops_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            updater.update(root, self.get)
            for name in ("Dockerfile", "Dockerfile.aarch64", "root/defaults/autostart", "root/defaults/autostart_wayland"):
                self.assertIn("newcraft", (root / name).read_text())
            for name in ("menu.xml", "menu_wayland.xml"):
                self.assertEqual((root / "root/defaults" / name).read_text().count("/usr/bin/newcraft</command>"), 1)
            before = {file: file.read_bytes() for file in root.rglob("*") if file.is_file()}
            updater.update(root, self.get)
            self.assertEqual(before, {file: file.read_bytes() for file in root.rglob("*") if file.is_file()})

    def test_failed_new_app_does_not_partially_write_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            before = {file: file.read_bytes() for file in root.rglob("*") if file.is_file()}
            def get(url):
                if "newcraft/releases/latest" in url:
                    data = release("newcraft")
                    data["assets"].pop()
                    return json.dumps(data)
                return self.get(url)
            with self.assertRaises(ValueError):
                updater.update(root, get)
            self.assertEqual(before, {file: file.read_bytes() for file in root.rglob("*") if file.is_file()})

    def test_existing_app_is_not_removed_by_catalog_omission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / updater.MANIFEST).write_text(json.dumps({"photocraft": "v1.0.0", "oldcraft": "v1.0.0"}))
            result = updater.update(root, self.get)
            self.assertIn("oldcraft", result)


if __name__ == "__main__":
    unittest.main()
