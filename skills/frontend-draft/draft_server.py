#!/usr/bin/env python
"""Draft Studio — a shared, editable preview of a static site.

Serves a draft directory with two things layered on top of the raw files:

  * live reload  — the page polls for file changes and reloads itself, so
    when Claude edits a file you see it immediately.
  * design mode  — a toolbar toggle makes the rendered page directly
    editable (click in, delete a paragraph, retype text); Save writes the
    edited DOM back to the file on disk.

The draft dir is meant to be its own git repo, so "what the user changed"
is just `git diff` — that diff is the instruction Claude acts on.

Usage: draft_server.py [--dir DIR] [--port N]
Only the Python standard library is used.
"""
import argparse
import json
import os
import posixpath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

ROOT = os.getcwd()
WATCH_EXT = (".html", ".css", ".js")

CHROME = """
<style data-draft-chrome>
  #__ds_bar{position:fixed;top:10px;right:10px;z-index:2147483647;
    font:13px/1.4 ui-monospace,Consolas,monospace;background:#1b1f24;color:#e6e9ec;
    border:1px solid #333c45;border-radius:8px;padding:7px 9px;display:flex;gap:8px;
    align-items:center;box-shadow:0 4px 14px rgba(0,0,0,.35);opacity:.92}
  #__ds_bar button{font:inherit;background:#2b3540;color:#e6e9ec;border:1px solid #3d4a57;
    border-radius:5px;padding:4px 9px;cursor:pointer}
  #__ds_bar button:hover{background:#374553}
  #__ds_bar button.on{background:#3d6b52;border-color:#4f8a6a;color:#fff}
  #__ds_bar .dot{width:8px;height:8px;border-radius:50%;background:#5c6773}
  #__ds_bar .dot.dirty{background:#d6a34a}
  #__ds_bar .dot.saved{background:#4f8a6a}
  #__ds_banner{position:fixed;top:56px;right:10px;z-index:2147483647;
    font:13px ui-monospace,monospace;background:#3a2f16;color:#f0d9a8;
    border:1px solid #8a6420;border-radius:8px;padding:8px 11px;display:none;gap:8px;align-items:center}
  body.__ds_edit [contenteditable="true"]{outline:2px dashed rgba(61,107,82,.6);outline-offset:2px}
</style>
<div id="__ds_bar" data-draft-chrome contenteditable="false">
  <span class="dot" id="__ds_dot" title="save state"></span>
  <button id="__ds_edit_btn" title="Toggle direct editing of the page">Design mode</button>
  <button id="__ds_save_btn" title="Write your edits back to the file">Save</button>
  <span id="__ds_path" style="opacity:.6"></span>
</div>
<div id="__ds_banner" data-draft-chrome contenteditable="false">
  <span>Claude changed this file on disk.</span>
  <button id="__ds_reload_btn">Reload</button>
  <button id="__ds_dismiss_btn">Keep my edits</button>
</div>
<script data-draft-chrome>
(function(){
  var PATH = window.__DS_PATH, MTIME = window.__DS_MTIME || 0;
  var edit=false, dirty=false;
  var bar=document.getElementById("__ds_bar"),
      editBtn=document.getElementById("__ds_edit_btn"),
      saveBtn=document.getElementById("__ds_save_btn"),
      dot=document.getElementById("__ds_dot"),
      banner=document.getElementById("__ds_banner");
  document.getElementById("__ds_path").textContent=PATH;

  function setDirty(d){dirty=d;dot.className="dot"+(d?" dirty":"");}
  function setSaved(){dot.className="dot saved";setTimeout(function(){if(!dirty)dot.className="dot";},1200);}

  function protect(){ // keep our chrome non-editable while body is editable
    document.querySelectorAll("[data-draft-chrome]").forEach(function(e){e.contentEditable="false";});
  }
  editBtn.onclick=function(){
    edit=!edit;
    document.body.contentEditable=edit?"true":"false";
    document.body.classList.toggle("__ds_edit",edit);
    editBtn.classList.toggle("on",edit);
    if(edit)protect();
  };
  document.addEventListener("input",function(e){
    if(edit && !e.target.closest("[data-draft-chrome]")) setDirty(true);
  });

  function serialize(){
    var clone=document.documentElement.cloneNode(true);
    clone.querySelectorAll("[data-draft-chrome]").forEach(function(e){e.remove();});
    clone.querySelectorAll("[contenteditable]").forEach(function(e){e.removeAttribute("contenteditable");});
    clone.classList.remove("__ds_edit");
    if(clone.querySelector("body")) clone.querySelector("body").classList.remove("__ds_edit");
    return "<!doctype html>\\n"+clone.outerHTML+"\\n";
  }
  saveBtn.onclick=function(){
    fetch("/__save",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({path:PATH,html:serialize()})})
     .then(function(r){return r.json();})
     .then(function(j){if(j.ok){MTIME=j.mtime;setDirty(false);setSaved();}
       else alert("save failed: "+(j.error||"?"));})
     .catch(function(e){alert("save failed: "+e);});
  };
  document.getElementById("__ds_reload_btn").onclick=function(){location.reload();};
  document.getElementById("__ds_dismiss_btn").onclick=function(){banner.style.display="none";};

  setInterval(function(){
    fetch("/__poll").then(function(r){return r.json();}).then(function(j){
      if(j.mtime>MTIME){
        if(edit && dirty){ banner.style.display="flex"; }
        else location.reload();
      }
    }).catch(function(){});
  },1000);
})();
</script>
"""


MIME = {
    ".html": "text/html", ".htm": "text/html", ".css": "text/css",
    ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".ico": "image/x-icon", ".mp4": "video/mp4", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".woff": "font/woff",
    ".woff2": "font/woff2", ".ttf": "font/ttf", ".otf": "font/otf",
    ".map": "application/json", ".txt": "text/plain", ".xml": "application/xml",
    ".pdf": "application/pdf", ".wasm": "application/wasm", ".csv": "text/csv",
}


def safe_path(root, rel):
    rel = unquote(rel).lstrip("/")
    full = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([full, os.path.realpath(root)]) != os.path.realpath(root):
        return None
    return full


def listing(full, urlpath):
    """Directory index for a folder with no index.html (multi-page sites)."""
    rows = []
    if urlpath.rstrip("/"):
        rows.append('<li><a href="../">../</a></li>')
    for name in sorted(os.listdir(full)):
        if name.startswith(".git"):
            continue
        p = os.path.join(full, name)
        slash = "/" if os.path.isdir(p) else ""
        rows.append(f'<li><a href="{name}{slash}">{name}{slash}</a></li>')
    return ("<!doctype html><meta charset=utf-8>"
            "<style>body{font:15px ui-monospace,monospace;max-width:40rem;"
            "margin:3rem auto;padding:0 1rem}h1{font-size:1rem;color:#666}"
            "li{margin:.3rem 0}a{color:#3d6b52}</style>"
            f"<h1>draft: /{urlpath}</h1><ul>{''.join(rows)}</ul>")


def max_mtime(root):
    m = 0
    for dp, _, fs in os.walk(root):
        if ".git" in dp:
            continue
        for f in fs:
            if f.endswith(WATCH_EXT):
                try:
                    m = max(m, int(os.path.getmtime(os.path.join(dp, f))))
                except OSError:
                    pass
    return m


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/__poll":
            return self._send(200, json.dumps({"mtime": max_mtime(ROOT)}))
        full = safe_path(ROOT, path.lstrip("/") or ".")
        if not full or not os.path.exists(full):
            return self._send(404, "not found", "text/plain")
        if os.path.isdir(full):
            idx = os.path.join(full, "index.html")
            if os.path.isfile(idx):
                full = idx
            else:
                return self._send(200, listing(full, path.strip("/")),
                                  "text/html; charset=utf-8")
        ext = posixpath.splitext(full)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        if ext in (".html", ".htm"):
            html = open(full, encoding="utf-8", errors="replace").read()
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            inject = (f'<script data-draft-chrome>window.__DS_PATH={json.dumps(rel)};'
                      f'window.__DS_MTIME={max_mtime(ROOT)};</script>' + CHROME)
            html = (html.replace("</body>", inject + "</body>", 1)
                    if "</body>" in html else html + inject)
            return self._send(200, html, "text/html; charset=utf-8")
        data = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlparse(self.path).path != "/__save":
            return self._send(404, json.dumps({"ok": False, "error": "no route"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n))
            full = safe_path(ROOT, payload["path"])
            if not full:
                return self._send(400, json.dumps({"ok": False, "error": "bad path"}))
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload["html"])
            return self._send(200, json.dumps({"ok": True, "mtime": max_mtime(ROOT)}))
        except Exception as e:
            return self._send(500, json.dumps({"ok": False, "error": str(e)}))


def serve(root, port):
    global ROOT
    ROOT = os.path.realpath(root)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"draft studio: http://localhost:{port}/  serving {ROOT}", flush=True)
    srv.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="draft")
    ap.add_argument("--port", type=int, default=8791)
    args = ap.parse_args()
    serve(args.dir, args.port)


if __name__ == "__main__":
    main()
