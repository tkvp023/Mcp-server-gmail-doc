#!/bin/bash
echo "Starting MCP Server..."
python -m src.server 2> error.log
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Server crashed with exit code $EXIT_CODE!"
    echo "Error log:"
    cat error.log
    
    # Start a dummy HTTP server to serve the error log so we can see it from the outside!
    echo "Serving error log on port $PORT..."
    cat << 'EOF' > serve_error.py
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class ErrorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(500)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        try:
            with open("error.log", "rb") as f:
                self.wfile.write(f.read())
        except Exception as e:
            self.wfile.write(str(e).encode())

port = int(os.getenv("PORT", "8000"))
server = HTTPServer(("0.0.0.0", port), ErrorHandler)
server.serve_forever()
EOF
    python serve_error.py
fi
