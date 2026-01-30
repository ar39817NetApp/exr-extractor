"""gRPC server implementation for EXR extraction service."""

import grpc
from concurrent import futures
import logging
import os
from pathlib import Path
import time
import uuid

import proto.extractor_pb2 as extractor_pb2
import proto.extractor_pb2_grpc as extractor_pb2_grpc
from server.exr_processor import process_exr_bytes_to_png_bytes


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base directory for file operations
DATA_DIR = os.getenv('DATA_DIR', '/data')


def validate_path(path, base_dir=DATA_DIR):
    """Validate that path is relative and within allowed directory.
    
    Args:
        path: User-provided path (should be relative)
        base_dir: Base directory to constrain operations
        
    Returns:
        Absolute path if valid
        
    Raises:
        ValueError: If path is invalid or contains path traversal
    """
    if not path:
        raise ValueError("Path cannot be empty")
    
    # Prevent path traversal attacks
    if '..' in path or path.startswith('/'):
        raise ValueError(f"Invalid path: {path}. Path must be relative and not contain '..'")
    
    # Construct full path
    full_path = os.path.normpath(os.path.join(base_dir, path))
    
    # Ensure it's still within base_dir after normalization
    if not full_path.startswith(os.path.abspath(base_dir)):
        raise ValueError(f"Path {path} is outside allowed directory")
    
    return full_path


DEFAULT_CHUNK_SIZE = 256 * 1024  # 256KB chunks for streaming


class ExtractionServiceServicer(extractor_pb2_grpc.ExtractionServiceServicer):
    """Implementation of the ExtractionService gRPC service."""

    def ProcessEXRStream(self, request_iterator, context):
        """Bidirectional streaming RPC for processing large EXR files.

        Receives EXR data in chunks, processes it, and streams PNG back in chunks.

        Args:
            request_iterator: Iterator of EXRChunk messages
            context: gRPC context

        Yields:
            PNGChunk messages with header, data chunks, and status updates
        """
        request_id = str(uuid.uuid4())
        exr_buffer = bytearray()
        expected_size = 0
        filename = "unknown"

        try:
            # Phase 1: Receive EXR chunks
            logger.info(f"[{request_id}] Starting streaming receive")

            for chunk in request_iterator:
                content_type = chunk.WhichOneof('content')

                if content_type == 'header':
                    filename = chunk.header.filename
                    expected_size = chunk.header.total_size
                    logger.info(f"[{request_id}] Receiving {filename}: {expected_size} bytes")

                    # Send receiving status
                    yield extractor_pb2.PNGChunk(
                        status=extractor_pb2.ProcessingStatus(
                            type=extractor_pb2.STATUS_RECEIVING,
                            message=f"Receiving {filename}",
                            progress=0.0
                        )
                    )

                elif content_type == 'data':
                    exr_buffer.extend(chunk.data)
                    if expected_size > 0:
                        progress = len(exr_buffer) / expected_size
                        # Send progress every ~10%
                        if len(exr_buffer) % (expected_size // 10 + 1) < len(chunk.data):
                            yield extractor_pb2.PNGChunk(
                                status=extractor_pb2.ProcessingStatus(
                                    type=extractor_pb2.STATUS_RECEIVING,
                                    message=f"Received {len(exr_buffer)}/{expected_size} bytes",
                                    progress=min(progress, 0.99)
                                )
                            )

            received_size = len(exr_buffer)
            logger.info(f"[{request_id}] Received {received_size} bytes total")

            if received_size == 0:
                yield extractor_pb2.PNGChunk(
                    status=extractor_pb2.ProcessingStatus(
                        type=extractor_pb2.STATUS_ERROR,
                        message="No data received",
                        progress=0.0
                    )
                )
                return

            # Phase 2: Process EXR
            yield extractor_pb2.PNGChunk(
                status=extractor_pb2.ProcessingStatus(
                    type=extractor_pb2.STATUS_PROCESSING,
                    message="Processing EXR to PNG",
                    progress=0.0
                )
            )

            start_time = time.time()
            png_bytes, width, height = process_exr_bytes_to_png_bytes(
                bytes(exr_buffer),
                exposure_ev=0.0,
                key=0.18,
                to_srgb=True
            )
            elapsed = time.time() - start_time
            logger.info(f"[{request_id}] Processing took {elapsed:.3f}s, output: {width}x{height}")

            # Phase 3: Send PNG header
            yield extractor_pb2.PNGChunk(
                header=extractor_pb2.PNGHeader(
                    width=width,
                    height=height,
                    total_size=len(png_bytes)
                )
            )

            # Phase 4: Stream PNG data in chunks
            yield extractor_pb2.PNGChunk(
                status=extractor_pb2.ProcessingStatus(
                    type=extractor_pb2.STATUS_SENDING,
                    message="Sending PNG data",
                    progress=0.0
                )
            )

            total_png_size = len(png_bytes)
            offset = 0
            while offset < total_png_size:
                chunk_data = png_bytes[offset:offset + DEFAULT_CHUNK_SIZE]
                yield extractor_pb2.PNGChunk(data=chunk_data)
                offset += len(chunk_data)

            # Phase 5: Complete
            yield extractor_pb2.PNGChunk(
                status=extractor_pb2.ProcessingStatus(
                    type=extractor_pb2.STATUS_COMPLETE,
                    message=f"Completed: {width}x{height} PNG ({total_png_size} bytes)",
                    progress=1.0
                )
            )
            logger.info(f"[{request_id}] Streaming complete")

        except ValueError as e:
            logger.error(f"[{request_id}] Validation error: {e}")
            yield extractor_pb2.PNGChunk(
                status=extractor_pb2.ProcessingStatus(
                    type=extractor_pb2.STATUS_ERROR,
                    message=f"Invalid EXR: {str(e)}",
                    progress=0.0
                )
            )

        except Exception as e:
            logger.error(f"[{request_id}] Error: {e}", exc_info=True)
            yield extractor_pb2.PNGChunk(
                status=extractor_pb2.ProcessingStatus(
                    type=extractor_pb2.STATUS_ERROR,
                    message=f"Processing error: {str(e)}",
                    progress=0.0
                )
            )

    def HealthCheck(self, request, context):
        """Health check endpoint.

        Args:
            request: HealthCheckRequest (empty)
            context: gRPC context

        Returns:
            HealthCheckResponse with service status
        """
        return extractor_pb2.HealthCheckResponse(
            healthy=True,
            service_name="exr-extractor",
            version="1.0.0"
        )

    def ProcessEXRBytes(self, request, context):
        """Process EXR bytes and return PNG bytes.
        
        Args:
            request: ProcessEXRBytesRequest containing exr_data
            context: gRPC context for setting status codes
            
        Returns:
            ProcessEXRBytesResponse with png_data, dimensions, and message
        """
        request_id = str(uuid.uuid4())
        try:
            # Validate input
            if not request.exr_data:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('exr_data is required')
                logger.error(f"[{request_id}] exr_data is required")
                return extractor_pb2.ProcessEXRBytesResponse()
            
            # Use default processing parameters
            exposure_ev = 0.0
            key = 0.18
            to_srgb = True
            
            logger.info(f"[{request_id}] Processing EXR bytes: size={len(request.exr_data)} bytes")
            start_time = time.time()
            # Process the EXR bytes
            png_bytes, width, height = process_exr_bytes_to_png_bytes(
                request.exr_data,
                exposure_ev=exposure_ev,
                key=key,
                to_srgb=to_srgb
            )
            elapsed = time.time() - start_time
            logger.info(f"[{request_id}] EXR to PNG conversion took {elapsed:.3f} seconds")
            logger.info(f"[{request_id}] Successfully processed: {width}x{height}, PNG size={len(png_bytes)} bytes")
            
            # Return the response
            return extractor_pb2.ProcessEXRBytesResponse(
                png_data=png_bytes,
                width=width,
                height=height,
                message=f"Successfully processed {width}x{height} image"
            )
            
        except ValueError as e:
            logger.error(f"[{request_id}] Invalid argument: {e}")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f'Invalid EXR data: {str(e)}')
            return extractor_pb2.ProcessEXRBytesResponse()
            
        except Exception as e:
            logger.error(f"[{request_id}] Error processing EXR bytes: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f'Internal error processing EXR: {str(e)}')
            return extractor_pb2.ProcessEXRBytesResponse()


def serve(port=50051, max_workers=10):
    """Start the gRPC server.
    
    Args:
        port: Port to listen on (default: 50051)
        max_workers: Maximum number of worker threads (default: 10)
    """
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.max_send_message_length', -1),  # No limit
            ('grpc.max_receive_message_length', -1),  # No limit
        ]
    )
    
    extractor_pb2_grpc.add_ExtractionServiceServicer_to_server(
        ExtractionServiceServicer(), server
    )
    
    server.add_insecure_port(f'[::]:{port}')
    
    logger.info(f"Starting gRPC server on port {port}...")
    server.start()
    logger.info(f"Server started successfully on port {port}")
    
    return server
