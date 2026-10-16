"""Open a built artifact in whatever the machine uses for it.

A page the user has to go and find is a page they read later, or not at all.
This hands it to them.

It degrades rather than fails. A lab container has no desktop and no Excel, so
there is nothing to hand anything to; in that case it prints the path and says
so, which is all anyone can do. Nothing here is worth interrupting a run over.
"""

import os
import platform
import shutil
import subprocess
import sys


def _opener():
    system = platform.system()
    if system == "Darwin":
        return ["open"]
    if system == "Windows":
        return None                      # os.startfile, handled below
    for candidate in ("xdg-open", "gio", "gnome-open"):
        path = shutil.which(candidate)
        if path:
            return [path, "open"] if candidate == "gio" else [path]
    return []


def open_path(target, quiet=False):
    """Open a file or URL. Returns True if something was launched.

    Never raises: the artifact exists either way, and failing to show it is not
    a reason to fail the run.
    """
    if platform.system() == "Windows":
        try:
            os.startfile(target)         # noqa: S606 -- the platform's own opener
            return True
        except OSError as exc:
            if not quiet:
                print(f"could not open {target}: {exc}", file=sys.stderr)
            return False

    command = _opener()
    if not command:
        if not quiet:
            print(f"nothing here can open files; it is at {target}",
                  file=sys.stderr)
        return False

    try:
        subprocess.run(command + [target], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=20)
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        if not quiet:
            print(f"could not open {target}: {exc}", file=sys.stderr)
        return False


def open_page(path, host="127.0.0.1", port=None):
    """Open a built page, over the server when one is serving it.

    The live-reload poller only works over HTTP -- a ``file://`` page has no
    server to ask -- so prefer the URL whenever something is listening.
    """
    if port and _listening(host, port):
        return open_path(f"http://{host}:{port}/{os.path.basename(path)}")
    return open_path("file://" + os.path.abspath(path))


def _listening(host, port):
    import socket

    with socket.socket() as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, int(port))) == 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="a file path or a URL")
    ap.add_argument("--port", type=int, help="serve.py's port, if it is running")
    args = ap.parse_args()

    if args.target.startswith(("http://", "https://")):
        open_path(args.target)
    else:
        open_page(args.target, port=args.port)
