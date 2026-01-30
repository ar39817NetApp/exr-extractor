# EXR Extraction Service

A gRPC service for converting EXR (OpenEXR) image files to PNG format with tone mapping. The service receives EXR, applies Reinhard tone mapping with sRGB conversion, and returns the converted image as PNG.

## Features

- **gRPC API** - High-performance binary protocol
- **Tone mapping** - Reinhard photographic tone mapping for HDR to SDR conversion
- **Auto-scaling** - Exposure control and sRGB color space conversion
- **Docker Ready** - Containerized for easy deployment

## Service Information

- **Port**: 50051
- **Container Name**: exr-extractor
- **Protocol**: gRPC

## Quick Start

```bash
# Start the service (builds image automatically)
make run

# View logs
make logs

# Test with an EXR file
make test INPUT=data/input/CrissyField.exr OUTPUT=data/output/CrissyField.png

# Stop the service
make stop

# Clean up (remove container and image)
make clean
```

## Available Commands

| Command | Description |
|---------|-------------|
| `make run` | Build and start service in Docker |
| `make logs` | View container logs in real-time |
| `make stop` | Stop and remove container |
| `make clean` | Stop container and remove Docker image |
| `make test INPUT=<file.exr> OUTPUT=<file.png>` | Test with EXR file |
| `make help` | Show available commands |

## Testing the Service

After starting the service with `make run`, you can test it with your EXR files:

### Basic Test (Recommended)
```bash
make test INPUT=data/input/CrissyField.exr OUTPUT=data/output/CrissyField.png
```

### More Examples
```bash
# Small test file (256x256)
make test INPUT=data/input/AllHalfValues.exr OUTPUT=data/output/AllHalfValues.png

# Standard HDR image (1218x810, 1.2MB)
make test INPUT=data/input/CrissyField.exr OUTPUT=data/output/CrissyField.png

# Large 4K HDR (79MB) - may take longer
make test INPUT=data/input/cedar_bridge_sunset_1_4k.exr OUTPUT=data/output/sunset.png

# Sample file (640x426)
make test INPUT=data/input/sample_640×426.exr OUTPUT=data/output/sample.png
```

### What Happens During Test

1. The service must be running (`make run`)
2. The EXR file is read from the `INPUT` path
3. Tone mapping is applied (Reinhard + sRGB conversion)
4. PNG file is saved to the `OUTPUT` path
5. Output directory is created automatically if it doesn't exist

### Expected Output

```
Processing: data/input/CrissyField.exr -> data/output/CrissyField.png
Reading EXR file: data/input/CrissyField.exr
File size: 1304619 bytes (1.24 MB)
Sending bytes to localhost:50051...

Response received!
Dimensions: 1218x810
PNG data size: 1668572 bytes (1629.46 KB)
Message: Successfully processed 1218x810 image
PNG saved to: data/output/CrissyField.png

✓ Test completed. Check output at: data/output/CrissyField.png
```

## API Details

The service provides a gRPC method for processing EXR files:

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

## Project Structure

```
exr-extractor/
├── data/
│   ├── input/             # Input .exr files
│   └── output/            # Output .png files (created automatically)
├── proto/
│   ├── extractor.proto    # gRPC service definition
│   ├── extractor_pb2.py
│   └── extractor_pb2_grpc.py
├── server/
│   ├── main.py            # Server entry point
│   ├── server.py          # gRPC service implementation
│   └── exr_processor.py   # EXR processing logic
├── client/
│   └── client.py          # Test client
├── Dockerfile
├── Makefile
└── README.md
```

## Processing Parameters

- **Exposure EV**: 0.0 (no adjustment)
- **Reinhard Key**: 0.18 (standard middle gray)
- **sRGB Conversion**: Enabled

## Troubleshooting

### Container not running
```bash
# Check if container is running
docker ps | grep exr-extractor

# If not running, start it
make run
```

### Test file not found
```bash
# Make sure your EXR file exists
ls -la data/input/

# Check the path is correct relative to the project root
make test INPUT=data/input/YourFile.exr OUTPUT=data/output/result.png
```

### Permission issues
```bash
# Make sure output directory exists and is writable
mkdir -p data/output
chmod 755 data/output
```

## License

Proprietary - NetApp Internal Use Only
