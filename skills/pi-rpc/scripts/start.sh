#!/bin/bash
set -e

# Change to the scripts directory to run Make targets correctly
cd "$(dirname "$0")"

# Build the server binary if it doesn't exist
if [ ! -f "bin/pi-server" ]; then
    make build-server
fi

# Start the server in the background, suppressing stdout and stderr unless debug is requested
if [ "$PI_DEBUG" = "1" ]; then
    ./bin/pi-server &
else
    ./bin/pi-server > /dev/null 2>&1 &
fi

# Wait for server to come up
PI_SERVER="${PI_SERVER_URL:-http://localhost:4097}"

# Health check using the List endpoint
for i in {1..10}; do
    if curl -sf -H 'Content-Type: application/json' -d '{}' "$PI_SERVER/pirpc.v1.SessionService/List" > /dev/null; then
        echo "pi-rpc server started successfully on $PI_SERVER"
        exit 0
    fi
    sleep 0.5
done

echo "Error: pi-rpc server failed to start or is not reachable at $PI_SERVER" >&2
exit 1
