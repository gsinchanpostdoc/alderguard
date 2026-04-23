#!/usr/bin/env python3
"""serve.py — Local development server for alder-ipm-sim-web.

No dependencies beyond the Python standard library.
Starts http.server on port 8080 (or the port given as the first argument)
and opens the default browser.

Usage:
    python serve.py          # port 8080
    python serve.py 3000     # custom port
"""

import http.server
import os
import sys
import webbrowser
from functools import partial

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    # Serve from the directory where this script lives
    serve_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(serve_dir)

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=serve_dir)
    server = http.server.HTTPServer(("", port), handler)

    url = f"http://localhost:{port}"
    print(f"Serving alder-ipm-sim-web at {url}")
    print("Press Ctrl+C to stop.\n")

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()

if __name__ == "__main__":
    main()
