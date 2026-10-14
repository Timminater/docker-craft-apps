#!/usr/bin/env python3
"""Discover official Craft apps, validate releases, then update the fork atomically."""
import base64
import configparser
import json
import os
from pathlib import Path
import re
from html.parser import HTMLParser
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CATALOG = "https://getartcraft.com/apps"
MANIFEST = Path("root/defaults/craft-releases.json")
APP_RE = re.compile(r"[a-z][a-z0-9]*craft")
TAG_RE = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?")


def fetch(url):
    headers = {"User-Agent": "Craft-Apps-Fork-Updater"}
    if urlparse(url).hostname == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return response.read().decode("utf-8")


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.hrefs = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href" and value)


def discover(text):
    apps = set()
    for href in Links(text).hrefs:
        url = urlparse(href)
        if url.netloc and url.netloc != "getartcraft.com":
            continue
        match = re.fullmatch(r"/apps/([a-z][a-z0-9]*craft)/?", url.path)
        if match:
            apps.add(match[1])
    if not apps or "photocraft" not in apps:
        raise ValueError("Official app catalog could not be recognized; refusing an empty update")
    return apps


def check_release(app, release):
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease") or not TAG_RE.fullmatch(tag):
        raise ValueError(f"{app}: unsupported stable release tag {tag!r}")
    assets = {asset["name"]: asset for asset in release["assets"]}
    for arch in ("x86_64", "aarch64"):
        name = f"{app}-{tag[1:]}-linux-{arch}.deb"
        asset = assets.get(name, {})
        expected = f"https://github.com/storytold/{app}/releases/download/{tag}/{name}"
        if asset.get("browser_download_url") != expected or asset.get("size", 0) <= 0:
            raise ValueError(f"{app}: latest release is missing the expected {arch} Debian package")
    return tag


def check_desktop(app, text):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.read_string(text)
    entry = parser["Desktop Entry"]
    if (entry.get("Type") != "Application"
            or entry.get("Exec", "").split() not in ([app], [app, "%F"], [app, "%U"], [app, "%f"], [app, "%u"])
            or entry.get("Icon") != f"ai.storyteller.{app}"):
        raise ValueError(f"{app}: launcher format changed; manual packaging review required")
    label = entry["Name"]
    if not re.fullmatch(r"[A-Za-z0-9 -]{1,60}", label):
        raise ValueError(f"{app}: unsupported app name")
    return label


def render(root, releases, labels):
    """Calculate all changes before writing anything, keeping unrelated defaults."""
    apps = sorted(releases)
    if not apps or "photocraft" not in apps or not all(APP_RE.fullmatch(app) for app in apps):
        raise ValueError("Invalid app inventory")
    changes = {}
    for name in ("Dockerfile", "Dockerfile.aarch64"):
        text = (root / name).read_text()
        text, count = re.subn(r"for APP in [a-z0-9 ]+; do", "for APP in " + " ".join(app for app in apps if app != "photocraft") + "; do", text)
        if count != 1:
            raise ValueError(f"{name}: installation loop changed")
        changes[Path(name)] = text
    for name in ("autostart", "autostart_wayland"):
        path = Path("root/defaults") / name
        text, count = re.subn(r"for APP in [a-z0-9 ]+; do", "for APP in " + " ".join(apps) + "; do", (root / path).read_text())
        if count != 1:
            raise ValueError(f"{name}: shortcut loop changed")
        changes[path] = text
    for name in ("menu.xml", "menu_wayland.xml"):
        path = Path("root/defaults") / name
        text = (root / path).read_text()
        text = re.sub(r'^<item[^\n]*<command>/usr/bin/[a-z0-9]*craft</command>[^\n]*</item>\n', '', text, flags=re.MULTILINE)
        if text.count("</menu>") != 1:
            raise ValueError(f"{name}: menu format changed")
        entries = "".join(f'<item label="{labels[app]}" icon="/usr/share/icons/hicolor/48x48/apps/ai.storyteller.{app}.png"><action name="Execute"><command>/usr/bin/{app}</command></action></item>\n' for app in apps)
        changes[path] = text.replace("</menu>", entries + "</menu>")
    changes[MANIFEST] = json.dumps(releases, indent=2, sort_keys=True) + "\n"
    return changes


def update(root=ROOT, get=fetch):
    discovered = discover(get(CATALOG))
    previous = json.loads((root / MANIFEST).read_text()) if (root / MANIFEST).exists() else {}
    # A temporary catalog omission must never silently remove an installed app.
    apps = discovered | set(previous)
    releases, labels = {}, {}
    for app in sorted(apps):
        if not APP_RE.fullmatch(app):
            raise ValueError(f"Invalid app identifier: {app}")
        page = get(f"{CATALOG}/{app}")
        repos = {urlparse(href).path.rstrip("/").lower() for href in Links(page).hrefs if urlparse(href).hostname == "github.com"}
        if f"/storytold/{app}" not in repos:
            raise ValueError(f"{app}: official repository could not be confirmed")
        api = f"https://api.github.com/repos/storytold/{app}"
        tag = check_release(app, json.loads(get(api + "/releases/latest")))
        desktop = json.loads(get(api + f"/contents/packaging/linux/ai.storyteller.{app}.desktop?ref=" + quote(tag, safe="")))
        labels[app] = check_desktop(app, base64.b64decode(desktop["content"]).decode("utf-8"))
        releases[app] = tag
    changes = render(root, releases, labels)
    modified = []
    for path, content in changes.items():
        target = root / path
        if not target.exists() or target.read_text() != content:
            target.write_text(content, newline="\n")
            modified.append(str(path))
    for app, tag in sorted(releases.items()):
        print(f"{app}: {tag}" + (" (new app)" if app not in previous else ""))
    print(f"Updated {len(modified)} files; verified {len(releases)} apps on both architectures")
    return releases


if __name__ == "__main__":
    update()
