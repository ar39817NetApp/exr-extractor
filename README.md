# EXR Extraction Service

A gRPC service for converting EXR (OpenEXR) image files to PNG format with tone mapping. The service receives EXR, applies Reinhard tone mapping with sRGB conversion, and returns the converted image as PNG.

## Features

- **gRPC API** - High-performance binary protocol
- **Tone mapping** - Reinhard photographic tone mapping for HDR to SDR conversion
- **Auto-scaling** - Exposure control and sRGB color space conversion
- **Docker Ready**: Containerized for easy deployment

## Prerequisites

- Docker Desktop (macOS/Windows) or Docker Engine (Linux)
- Python 3.9+ (for running the client locally)

## Project Structure

```
exr-extractor/
├── data/
│   ├── input/             # Place your .exr files here
│   └── output/            # Processed .png files will be saved here
├── proto/
│   ├── extractor.proto    # gRPC service definition
│   ├── extractor_pb2.py   # Generated gRPC code
│   └── extractor_pb2_grpc.py
├── server/
│   ├── __init__.py        # Makes server a package
│   ├── main.py            # Server entry point
│   ├── server.py          # gRPC service implementation
│   └── exr_processor.py   # EXR processing logic
├── client/
│   └── client.py          # Test client
├── Dockerfile             # Docker image definition
├── requirements.txt       # Python dependencies
├── Makefile               # Project automation commands
└── README.md              # Project documentation
```

## Quick Start with Makefile

The project includes a Makefile for easy setup and execution:

```bash
# Show available commands
make help

# Build Docker container
make build

# Run Docker container (detached mode on port 50054)
make run

# View container logs
make logs

# Test with a EXR file
make test data/input/file.exr data/output/result.png

# Stop and remove container
make clean
```

### Development Commands

```bash
# Create virtual environment
make venv

# Install dependencies
make install

# Generate gRPC code from proto definition
make proto
```

## Manual Setup

If you prefer not to use Make:

1. **Create virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Generate gRPC code**:
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/extractor.proto
```

## Running the Server

### Using Docker (Recommended):

```bash
# Build the image
make build

# Run the container
make run

# The server will be available on localhost:50051
```

Or manually:
```bash
docker build -t exr-extractor:latest .
docker run -d --rm -p 50051:50051 --name exr-extractor exr-extractor:latest
```

The server runs on port 50051 inside the container, mapped to port 50051 on the host.

## Testing with the Client

### Process a EXR file:

```bash
# Using Make
make test data/input/input.exr data/output/output.png

# Or manually
python -m client.client data/input/input.exr data/output/output.png
```

## API Details

The service provides a bytes-based RPC method for processing EXR files:

### ProcessEXRBytes

Client sends EXR file bytes, server returns PNG bytes.

```protobuf
rpc ProcessEXRBytes (ProcessEXRBytesRequest) returns (ProcessEXRBytesResponse);

message ProcessEXRBytesRequest {
  bytes exr_data = 1;
}

message ProcessEXRBytesResponse {
  bytes png_data = 1;
  int32 width = 2;
  int32 height = 3;
  string message = 4;
}
```

### Processing Parameters (hardcoded defaults)

- **Exposure EV**: 0.0 (no adjustment)
- **Reinhard Key**: 0.18 (standard middle gray)
- **sRGB Conversion**: Enabled

## License

Proprietary - NetApp Internal Use Only
