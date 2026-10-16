"""Serve the built pages for the edit-and-watch loop.

``python -m http.server`` would almost do, but it lets the browser cache, and a
cached page defeats the whole point: the reload fires and the browser serves the
stale copy back to itself. This sends ``Cache-Control: no-store`` on everything,
which is the one thing worth a file of our own.

    python serve.py ./out            # http://127.0.0.1:8765

Then rebuild whenever the numbers change:

    python build_pages.py bundle.json ./out --csv assumptions.csv --live

The ``--live`` page polls this server once a second and reloads when the file
actually changes. A page built without ``--live`` has no poller, which is what
you send someone.

One thing to expect: browsers throttle timers in a tab you are not looking at,
so a backgrounded page can take a while to notice. It catches up the moment you
switch back to it, which is when you wanted to see it anyway.

Stop it with ctrl-C. Nothing is written outside the directory you point it at,
and it listens on the loopback address only.
"""

import argparse
import functools
import http.server
import os
import socketserver
import sys

DEFAULT_PORT = 8791      # off the common ones; 8000 and 8765 are usually taken


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Static files, with caching turned off so a reload actually reloads."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        # One line per rebuild is useful; a line per poll is not.
        if self.command != "HEAD":
            sys.stderr.write("%s %s\n" % (self.command, self.path))


def _bind(host, port, handler, tries=12):
    """The first free port at or above ``port``.

    A dev server that dies because something else already holds the port is an
    interruption for no reason -- and killing whatever holds it is worse.
    """
    socketserver.TCPServer.allow_reuse_address = True
    last = None
    for candidate in range(port, port + tries):
        try:
            return socketserver.TCPServer((host, candidate), handler), candidate
        except OSError as exc:
            last = exc
    raise SystemExit(
        f"no free port between {port} and {port + tries - 1}: {last}")


def serve(directory, port=DEFAULT_PORT, host="127.0.0.1"):
    if not os.path.isdir(directory):
        raise SystemExit(f"{directory} is not a directory")

    handler = functools.partial(NoCacheHandler, directory=os.path.abspath(directory))
    httpd, port = _bind(host, port, handler)

    with httpd:
        pages = sorted(n for n in os.listdir(directory) if n.endswith(".html"))
        print(f"serving {os.path.abspath(directory)} at http://{host}:{port}")
        for name in pages:
            print(f"  http://{host}:{port}/{name}")
        if not pages:
            print("  (no pages built yet -- run build_pages.py)")
        print("ctrl-C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("directory", nargs="?", default=".")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    serve(args.directory, args.port)
