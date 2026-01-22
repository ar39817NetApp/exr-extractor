"""gRPC client for EXR extraction service.

Reads EXR files locally and sends bytes to the server for processing.
Supports both unary and bidirectional streaming modes.
"""

import grpc
import sys
import os

import proto.extractor_pb2 as extractor_pb2
import proto.extractor_pb2_grpc as extractor_pb2_grpc

DEFAULT_CHUNK_SIZE = 256 * 1024  # 256KB chunks


def generate_exr_chunks(input_file, chunk_size=DEFAULT_CHUNK_SIZE):
    """Generator that yields EXR chunks for streaming.

    Args:
        input_file: Path to the input EXR file
        chunk_size: Size of each chunk in bytes

    Yields:
        EXRChunk messages (header first, then data chunks)
    """
    file_size = os.path.getsize(input_file)
    filename = os.path.basename(input_file)

    # Send header first
    yield extractor_pb2.EXRChunk(
        header=extractor_pb2.EXRHeader(
            filename=filename,
            total_size=file_size,
            chunk_size=chunk_size
        )
    )

    # Send data chunks
    with open(input_file, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield extractor_pb2.EXRChunk(data=chunk)


def process_exr_streaming(input_file, output_file, host='localhost', port=50051):
    """Process EXR using bidirectional streaming (for large files).

    Args:
        input_file: Path to the input EXR file
        output_file: Path to save the output PNG file
        host: Server host
        port: Server port

    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        return False

    file_size = os.path.getsize(input_file)
    print(f"[Streaming] Reading EXR file: {input_file}")
    print(f"[Streaming] File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")

    options = [
        ('grpc.max_send_message_length', -1),
        ('grpc.max_receive_message_length', -1),
    ]
    channel = grpc.insecure_channel(f'{host}:{port}', options=options)
    stub = extractor_pb2_grpc.ExtractionServiceStub(channel)

    print(f"[Streaming] Connecting to {host}:{port}...")

    try:
        png_buffer = bytearray()
        width = 0
        height = 0

        # Start bidirectional streaming
        response_iterator = stub.ProcessEXRStream(generate_exr_chunks(input_file))

        for response in response_iterator:
            content_type = response.WhichOneof('content')

            if content_type == 'status':
                status = response.status
                progress_pct = status.progress * 100
                print(f"[{status.type}] {status.message} ({progress_pct:.0f}%)")

                if status.type == extractor_pb2.STATUS_ERROR:
                    print(f"Error: {status.message}")
                    return False

            elif content_type == 'header':
                width = response.header.width
                height = response.header.height
                total_size = response.header.total_size
                print(f"[Streaming] PNG header: {width}x{height}, {total_size} bytes")

            elif content_type == 'data':
                png_buffer.extend(response.data)

        if not png_buffer:
            print("Error: No PNG data received")
            return False

        # Save the PNG file
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'wb') as f:
            f.write(png_buffer)

        print(f"[Streaming] PNG saved to: {output_file} ({len(png_buffer)} bytes)")
        return True

    except grpc.RpcError as e:
        print(f"\ngRPC Error: {e.code()}")
        print(f"Details: {e.details()}")
        return False
    finally:
        channel.close()


def process_exr(input_file, output_file, host='localhost', port=50051):
    """Read EXR file, send bytes to gRPC server, and save PNG response.
    
    Args:
        input_file: Path to the input EXR file (local file)
        output_file: Path to save the output PNG file (local file)
        host: Server host
        port: Server port
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        return False
    
    print(f"Reading EXR file: {input_file}")
    with open(input_file, 'rb') as f:
        exr_data = f.read()
    
    print(f"File size: {len(exr_data)} bytes ({len(exr_data) / (1024*1024):.2f} MB)")
    
    # Configure channel with unlimited message sizes
    options = [
        ('grpc.max_send_message_length', -1),
        ('grpc.max_receive_message_length', -1),
    ]
    channel = grpc.insecure_channel(f'{host}:{port}', options=options)
    stub = extractor_pb2_grpc.ExtractionServiceStub(channel)
    
    request = extractor_pb2.ProcessEXRBytesRequest(exr_data=exr_data)
    
    print(f"Sending bytes to {host}:{port}...")
    
    try:
        response = stub.ProcessEXRBytes(request)
        
        print(f"\nResponse received!")
        print(f"Dimensions: {response.width}x{response.height}")
        print(f"PNG data size: {len(response.png_data)} bytes ({len(response.png_data) / 1024:.2f} KB)")
        print(f"Message: {response.message}")
        
        # Save the PNG file
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'wb') as f:
            f.write(response.png_data)
        
        print(f"PNG saved to: {output_file}")
        return True
        
    except grpc.RpcError as e:
        print(f"\ngRPC Error: {e.code()}")
        print(f"Details: {e.details()}")
        return False
    finally:
        channel.close()


def health_check(host='localhost', port=50051):
    """Check server health.

    Args:
        host: Server host
        port: Server port

    Returns:
        bool: True if healthy
    """
    print(f"Checking health of {host}:{port}...")

    channel = grpc.insecure_channel(f'{host}:{port}')
    stub = extractor_pb2_grpc.ExtractionServiceStub(channel)

    try:
        response = stub.HealthCheck(extractor_pb2.HealthCheckRequest())
        print(f"Healthy: {response.healthy}")
        print(f"Service: {response.service_name}")
        print(f"Version: {response.version}")
        return response.healthy
    except grpc.RpcError as e:
        print(f"Health check failed: {e.code()}")
        print(f"Details: {e.details()}")
        return False
    finally:
        channel.close()


def print_usage():
    """Print usage information."""
    print("Usage: python client.py <input> <output> [options]")
    print("       python client.py --health [--host=HOST] [--port=PORT]")
    print("\nOptions:")
    print("  --host=HOST          Server host (default: localhost)")
    print("  --port=PORT          Server port (default: 50051)")
    print("  --stream             Use bidirectional streaming (recommended for large files)")
    print("  --health             Check server health")
    print("\nDescription:")
    print("  Reads an EXR file locally and sends its bytes to the gRPC server.")
    print("  The server processes the EXR and returns PNG data, which is saved locally.")
    print("\nExamples:")
    print("  # Health check")
    print("  python client.py --health")
    print()
    print("  # Basic usage (unary)")
    print("  python client.py data/input/file.exr data/output/result.png")
    print()
    print("  # Streaming mode (recommended for files > 10MB)")
    print("  python client.py data/input/large.exr data/output/result.png --stream")
    print()
    print("  # Remote server with streaming")
    print("  python client.py data/input/file.exr data/output/result.png --host=192.168.1.100 --stream")


def main():
    """Main entry point for the client."""
    # Parse common arguments first
    host = 'localhost'
    port = 50051
    use_streaming = False
    do_health = '--health' in sys.argv

    for arg in sys.argv[1:]:
        if arg.startswith('--host='):
            host = arg.split('=')[1]
        elif arg.startswith('--port='):
            port = int(arg.split('=')[1])
        elif arg == '--stream':
            use_streaming = True

    # Health check mode
    if do_health:
        success = health_check(host=host, port=port)
        sys.exit(0 if success else 1)

    # Help mode
    if '--help' in sys.argv or '-h' in sys.argv:
        print_usage()
        sys.exit(0)

    # Processing mode requires input and output
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Process the EXR file
    if use_streaming:
        success = process_exr_streaming(input_file, output_file, host=host, port=port)
    else:
        success = process_exr(input_file, output_file, host=host, port=port)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
