#!/bin/bash
echo "Starting MCP Server..."
python -m src.server 2> error.log
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Server crashed with exit code $EXIT_CODE!"
    echo "Error log:"
    cat error.log
    
    # Start a dummy HTTP server to serve the error log so we can see it from the outside!
    echo -e "HTTP/1.1 500 Internal Server Error\n\n$(cat error.log)" > response.http
    while true; do
        cat response.http | nc -l -p $PORT
    done
fi
