#!/usr/bin/env python
"""Draft Studio — a shared editable draft for ANY site.

Turns a target into a running, editable preview + a git-tracked draft whose
diff is the instruction Claude acts on. Works across the range of real sites:
static HTML (single or multi-page, at repo root or in a subdir), a brand-new
site from scratch, and framework apps (Next/Vite/etc.) via their own dev server.

    studio.py TARGET [--port N] [--fresh] [--name NAME] [--workspace DIR]

TARGET is one of:
    .                 a local directory (a site you already have)
    path/to/site      any local path
    owner/repo        a GitHub repo (cloned with gh, works for private)
    https://…​.git     a git URL
    scratch           start a new empty site

What it does:
  1. Resolve TARGET to a local source (cloning if remote).
  2. Detect the site: static | framework | scratch, and find where the
     servable files actually live (root, or public/docs/site/www/dist/... ).
  3. Build a disposable draft/ (its own git repo; baseline committed) so
     `git -C <draft> diff` is exactly what the user changed.
  4. Serve it:
       static/scratch -> the draft_server (live-reload + browser design-mode
                         with save-to-disk).
       framework      -> the project's own dev server through a loopback visual
                         editor proxy. Browser edits become durable source-change
                         requests; the agent applies them to components.
  5. Print a STUDIO READY block with the URL and the draft path.

Only the standard library + git/gh/npm on PATH are used.
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import draft_server  # noqa: E402
import framework_server  # noqa: E402

SUBDIRS = ["public", "docs", "site", "www", "dist", "build", "src",
           "frontend", "web", "app"]
IGNORE = shutil.ignore_patterns(".git", "node_modules", "__pycache__",
                                ".next", ".venv", "venv", "dist", "build", ".workspace", ".draft-studio",
                                "*.mp4", "*.parquet", "*.zip")


def run(cmd, cwd=None, check=True, capture=False):
    return subprocess.run(cmd, cwd=cwd, check=check,
                          text=True, capture_output=capture)


def free_port(start):
    p = start
    while p < start + 200:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
        p += 1
    return start


def resolve_source(target, ws):
    """Return (local_source_path, display_name)."""
    if target == "scratch":
        return None, "scratch"
    p = Path(target)
    if p.exists():
        return p.resolve(), p.resolve().name
    # remote: a git URL, an owner/repo slug, or a bare repo name (gh resolves
    # a bare name against the authenticated user)
    is_url = "://" in target or target.endswith(".git")
    is_repo = is_url or bool(re.fullmatch(r"[\w.-]+(/[\w.-]+)?", target))
    if not is_repo:
        sys.exit(f"target not found and not a repo: {target}")
    name = re.sub(r"\.git$", "", target.rstrip("/").split("/")[-1])
    dest = ws / "src" / name
    if dest.exists():
        print(f"[studio] reusing clone {dest}")
        return dest, name
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[studio] cloning {target} ...")
    if is_url:
        run(["git", "clone", "--depth", "1", target, str(dest)])
    else:
        run(["gh", "repo", "clone", target, str(dest), "--", "--depth", "1"])
    return dest, name


def has_html(d):
    try:
        return any(f.lower().endswith((".html", ".htm")) for f in os.listdir(d))
    except OSError:
        return False


def detect(source):
    """Return (mode, servable_root, meta). mode in static|framework|scratch."""
    if source is None:
        return "scratch", None, {}
    pkg = source / "package.json"
    if pkg.exists():
        try:
            j = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = j.get("scripts", {})
            cmd = ("dev" if "dev" in scripts else
                   "start" if "start" in scripts else None)
            deps = {**j.get("dependencies", {}), **j.get("devDependencies", {})}
            flavor = next((k for k in ("next", "vite", "astro", "@sveltejs/kit",
                                       "react-scripts", "@angular/core")
                           if k in deps), "node")
            if cmd:
                return "framework", source, {"script": cmd, "flavor": flavor}
        except Exception:
            pass
    # static: find the dir that actually holds the pages
    if has_html(source):
        return "static", source, {}
    for sub in SUBDIRS:
        d = source / sub
        if d.is_dir() and has_html(d):
            return "static", d, {}
    # any nested dir with html (shallow)
    for d in sorted(source.rglob("index.html"))[:1]:
        return "static", d.parent, {}
    return "scratch", None, {}


SCAFFOLD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>New site</title>
<style>
  :root{color-scheme:light dark}
  body{font:16px/1.6 system-ui,sans-serif;max-width:42rem;margin:4rem auto;padding:0 1.25rem}
  h1{font-size:2rem;margin:0 0 .5rem}
  p{color:#555}
</style>
</head>
<body>
  <h1>New site</h1>
  <p>Edit this page directly, or sketch a skeleton and let Claude fill it in.</p>
  <!-- add sections here; an empty <section> or a comment is an instruction -->
</body>
</html>
"""


def build_draft(mode, servable, source, draft, fresh):
    if fresh and draft.exists():
        if draft.name != 'draft' or draft.is_symlink() or (source and draft.resolve() == source.resolve()):
            raise ValueError('Refusing to replace a non-draft directory')
        shutil.rmtree(draft)
    if draft.exists():
        print(f"[studio] draft exists, kept: {draft} (use --fresh to rebuild)")
        return
    draft.mkdir(parents=True)
    if mode == "scratch":
        (draft / "index.html").write_text(SCAFFOLD, encoding="utf-8")
    elif mode == "framework":
        # need the whole project to run its dev server
        for item in os.listdir(source):
            if item in IGNORE(str(source), os.listdir(source)):
                continue
            s = source / item
            (shutil.copytree(s, draft / item, ignore=IGNORE)
             if s.is_dir() else shutil.copy2(s, draft / item))
    else:  # static: only the servable tree
        for item in os.listdir(servable):
            if item == ".git":
                continue
            s = servable / item
            (shutil.copytree(s, draft / item, ignore=IGNORE)
             if s.is_dir() else shutil.copy2(s, draft / item))
    if mode == 'framework':
        with (draft / '.gitignore').open('a', encoding='utf-8') as f:
            f.write('\n# Draft Studio build artifacts\nnode_modules/\n.next/\ndist/\n.env*\n.draft-studio/.lock\n.draft-studio/changes.tmp\n')
    run(["git", "init", "-q"], cwd=draft)
    run(["git", "add", "-A"], cwd=draft)
    run(["git", "-c", "user.email=draft@studio", "-c", "user.name=draft",
         "commit", "-q", "-m", f"baseline ({mode})"], cwd=draft, check=False)
    print(f"[studio] draft built at {draft} (git baseline committed)")


def ready(mode, url, draft, note=""):
    print("\n" + "=" * 58)
    print("STUDIO READY")
    print(f"  mode  : {mode}")
    print(f"  open  : {url}")
    print(f"  draft : {draft}")
    print(f"  diff  : git -C \"{draft}\" diff   (this is the instruction)")
    if note:
        print(f"  note  : {note}")
    print("=" * 58 + "\n", flush=True)


def serve_framework(draft, meta, port):
    npm = shutil.which("npm")
    if not npm:
        sys.exit("[studio] framework site needs Node/npm on PATH")
    if not (draft / "node_modules" / ".package-lock.json").exists():
        print("[studio] npm install (first run, may take a minute) ...")
        run([npm, "ci" if (draft / 'package-lock.json').exists() else "install"], cwd=draft)
    script = meta["script"]
    print(f"[studio] npm run {script}  ({meta['flavor']})")
    backend_port = free_port(port + 1)
    env = {**os.environ, "PORT": str(backend_port), "HOST": "127.0.0.1", "BROWSER": "none"}
    cmd = [npm, 'run', script]
    if meta['flavor'] == 'next':
        cmd += ['--', '--port', str(backend_port), '--hostname', '127.0.0.1']
    elif meta['flavor'] == 'vite':
        cmd += ['--', '--port', str(backend_port), '--host', '127.0.0.1', '--strictPort']
    proc = subprocess.Popen(cmd, cwd=draft, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', bufsize=1)
    discovered = [backend_port]
    def log_output():
        for line in proc.stdout:
            print('  [dev] ' + line.rstrip(), flush=True)
            match = re.search(r'https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d+)', line)
            if match:
                discovered[0] = int(match.group(1))
    threading.Thread(target=log_output, daemon=True).start()
    server = None
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f'Dev server exited with code {proc.returncode}')
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1', discovered[0])) == 0:
                    break
            time.sleep(.2)
        else:
            raise RuntimeError('Dev server did not start within 120 seconds')
        server = framework_server.create_server(draft, port, discovered[0])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        ready('framework', f'http://localhost:{server.server_port}/', draft,
              'Select element -> edit text/styles -> Save changes. Agent reads '
              '.draft-studio/changes.json and implements in component source. HMR remains active.')
        proc.wait()
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if proc.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
            else:
                proc.terminate()
            proc.wait(timeout=10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=0, help="0 = auto")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--name", default=None)
    ap.add_argument("--workspace", default=str(Path.home() / ".draft-studio"))
    args = ap.parse_args()

    ws = Path(args.workspace)
    source, name = resolve_source(args.target, ws)
    name = args.name or name
    if name in ('.', '..') or '/' in name or '\\' in name:
        sys.exit('Workspace name must be a single directory name')
    mode, servable, meta = detect(source)
    proj = ws / name
    draft = proj / "draft"
    print(f"[studio] target={args.target}  name={name}  mode={mode}"
          + (f"  servable={servable}" if servable else ""))
    build_draft(mode, servable, source, draft, args.fresh)

    if mode == "framework":
        port = free_port(args.port or (3000 if meta["flavor"] == "next" else 5173))
        serve_framework(draft, meta, port)
    else:
        port = free_port(args.port or 8791)
        ready(mode, f"http://localhost:{port}/", draft,
              "static: edit files OR browser Design mode + Save")
        draft_server.serve(str(draft), port)


if __name__ == "__main__":
    main()
