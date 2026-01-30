"""Entry point for the EXR Extraction gRPC service."""

import signal
import sys
import time
from server.server import serve


def main():
    """Start the gRPC server and handle graceful shutdown."""
    port = 50051
    server = serve(port=port)
    
    def shutdown_handler(signum, frame):
        print('\nShutting down server...')
        server.stop(grace=5)
        print('Server stopped.')
        sys.exit(0)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        # Keep the server running
        server.wait_for_termination()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        server.stop(grace=5)
        print('Server stopped.')


if __name__ == '__main__':
    main()
