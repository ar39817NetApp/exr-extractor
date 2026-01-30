import OpenEXR
import Imath
import numpy as np
import cv2
import os
import tempfile


def _validate_exr_file(filepath):
    """Validate EXR file before processing to prevent segmentation faults.

    Args:
        filepath: Path to EXR file

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Check if file exists and is readable
        if not os.path.exists(filepath):
            return False, "File does not exist"

        if not os.path.isfile(filepath):
            return False, "Path is not a file"

        file_size = os.path.getsize(filepath)
        if file_size < 100:  # EXR files should be at least this size
            return False, f"File too small ({file_size} bytes) to be a valid EXR"

        # Check EXR magic number (first 4 bytes should be 0x76, 0x2f, 0x31, 0x01)
        with open(filepath, 'rb') as f:
            magic = f.read(4)
            if len(magic) < 4:
                return False, "Cannot read file header"

            expected_magic = bytes([0x76, 0x2f, 0x31, 0x01])
            if magic != expected_magic:
                return False, f"Invalid EXR magic number. Expected {expected_magic.hex()}, got {magic.hex()}"

            # Read version field (next 4 bytes)
            version_bytes = f.read(4)
            if len(version_bytes) < 4:
                return False, "Incomplete EXR header"

            # Basic header structure validation
            # Read more of the header to check for corruption
            f.seek(0)
            header_chunk = f.read(min(1024, file_size))

            # Check for null bytes in early header (indicates corruption)
            null_count = header_chunk[8:100].count(b'\x00')
            if null_count > 80:  # Too many nulls suggests corruption
                return False, "EXR header appears corrupted (too many null bytes)"

        # Try to open with OpenEXR to check if it's readable
        # Wrap in subprocess to isolate potential segfaults from corrupted files
        import subprocess
        import sys

        validation_code = f'''
import sys
import OpenEXR
try:
    f = OpenEXR.InputFile({repr(filepath)})
    header = f.header()
    if "dataWindow" not in header:
        sys.exit(1)
    dw = header["dataWindow"]
    width = dw.max.x - dw.min.x + 1
    height = dw.max.y - dw.min.y + 1
    if width <= 0 or height <= 0 or width > 65535 or height > 65535:
        sys.exit(1)
    if "channels" not in header or not header["channels"]:
        sys.exit(1)
    sys.exit(0)
except Exception:
    sys.exit(1)
'''

        try:
            # Pass current environment to subprocess (includes venv paths)
            env = os.environ.copy()
            result = subprocess.run(
                [sys.executable, '-c', validation_code],
                timeout=10,
                capture_output=True,
                text=True,
                env=env
            )

            if result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else "unknown error"
                return False, f"OpenEXR validation failed - file may be corrupted or unsupported ({stderr})"

        except subprocess.TimeoutExpired:
            return False, "OpenEXR validation timed out - file may be corrupted"
        except Exception as e:
            return False, f"Validation subprocess error: {str(e)}"

        return True, "Valid EXR file"

    except Exception as e:
        return False, f"Validation error: {str(e)}"


def _read_exr_rgb(exrpath):
    """Read an EXR file and extract RGB channels as float32 numpy array."""
    # Validate file first
    is_valid, error_msg = _validate_exr_file(exrpath)
    if not is_valid:
        raise ValueError(f"Invalid EXR file: {error_msg}")

    try:
        f = OpenEXR.InputFile(exrpath)
    except Exception as e:
        raise ValueError(f"Failed to open EXR file: {str(e)}")

    try:
        header = f.header()
    except Exception as e:
        raise ValueError(f"Failed to read EXR header: {str(e)}")

    dw = header['dataWindow']
    width = dw.max.x - dw.min.x + 1
    height = dw.max.y - dw.min.y + 1

    pt = Imath.PixelType(Imath.PixelType.FLOAT)

    def read_channel(name):
        try:
            raw = f.channel(name, pt)
        except Exception as e:
            # Log channel reading error but don't crash
            return None

        try:
            arr = np.frombuffer(raw, dtype=np.float32)
            return arr.reshape((height, width))
        except Exception as e:
            # Reshape or buffer conversion failed
            return None

    # Try common channel name variants
    r = read_channel('R')
    if r is None:
        r = read_channel('r')
    g = read_channel('G')
    if g is None:
        g = read_channel('g')
    b = read_channel('B')
    if b is None:
        b = read_channel('b')

    # If channels missing, try single-channel luminance or duplicate
    # Check each channel individually to avoid ambiguous array truth value
    r_missing = r is None
    g_missing = g is None
    b_missing = b is None

    if r_missing or g_missing or b_missing:
        # try luminance channel
        y = read_channel('Y')
        if y is None:
            y = read_channel('y')

        if y is not None:
            if r_missing:
                r = y
            if g_missing:
                g = y
            if b_missing:
                b = y
        else:
            # fill missing with zeros to avoid crashes
            if r_missing:
                r = np.zeros((height, width), dtype=np.float32)
            if g_missing:
                g = np.zeros((height, width), dtype=np.float32)
            if b_missing:
                b = np.zeros((height, width), dtype=np.float32)

    hdr = np.stack([r, g, b], axis=2)

    # Replace NaN and inf with 0
    hdr = np.nan_to_num(hdr, nan=0.0, posinf=0.0, neginf=0.0)
    return hdr


def _read_exr_rgb_from_bytes(exr_bytes):
    """Read an EXR file from bytes and extract RGB channels as float32 numpy array."""
    # Validate bytes first
    if not exr_bytes:
        raise ValueError("Empty EXR data")

    if len(exr_bytes) < 100:
        raise ValueError(f"EXR data too small ({len(exr_bytes)} bytes)")

    # Check magic number before writing to file
    expected_magic = bytes([0x76, 0x2f, 0x31, 0x01])
    if exr_bytes[:4] != expected_magic:
        raise ValueError(f"Invalid EXR magic number. This does not appear to be an EXR file.")

    # Write bytes to a temporary object that OpenEXR can read
    tmp_path = None
    try:
        # OpenEXR requires a file path, so we need to write to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.exr') as tmp:
            tmp.write(exr_bytes)
            tmp_path = tmp.name

        hdr = _read_exr_rgb(tmp_path)
        return hdr
    except ValueError as e:
        # Re-raise validation errors
        raise
    except Exception as e:
        raise ValueError(f"Error processing EXR data: {str(e)}")
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass  # Ignore cleanup errors


def _reinhard_tonemap(hdr, key=0.18, eps=1e-6):
    """Apply Reinhard tone mapping operator."""
    # Compute luminance
    Lw = 0.2126 * hdr[..., 0] + 0.7152 * hdr[..., 1] + 0.0722 * hdr[..., 2]
    Lw = np.clip(Lw, 0.0, 1e6)  # Clip extreme values
    # Avoid -inf from log(0)
    log_Lw = np.log(eps + Lw)
    log_Lw = np.nan_to_num(log_Lw, nan=0.0, posinf=0.0, neginf=0.0)
    log_mean = np.exp(np.mean(log_Lw))
    # Scale luminance
    Lm = (key / (log_mean + eps)) * Lw
    # Tone map luminance
    Ld = Lm / (1.0 + Lm)
    # Avoid division by zero
    scale = Ld / (Lw + eps)
    tonemapped = hdr * scale[..., None]
    tonemapped = np.clip(tonemapped, 0.0, 1.0)
    return tonemapped


def _linear_to_srgb(img):
    """Convert linear RGB to sRGB color space."""
    # img assumed in [0,1]
    a = 0.055
    srgb = np.where(img <= 0.0031308, img * 12.92, (1 + a) * np.power(img, 1.0 / 2.4) - a)
    srgb = np.clip(srgb, 0.0, 1.0)
    return srgb


def process_exr_to_rgb(exr_bytes, exposure_ev=0.0, key=0.18, to_srgb=True):
    """Process EXR bytes and return 8-bit RGB numpy array and dimensions.

    Args:
        exr_bytes: Raw EXR file bytes
        exposure_ev: Exposure value in stops (can be positive/negative)
        key: Reinhard key value (0.18 typical)
        to_srgb: If True, convert linear RGB to sRGB transfer function

    Returns:
        tuple: (rgb8_array, width, height) where rgb8_array is (H,W,3) uint8
    """
    hdr = _read_exr_rgb_from_bytes(exr_bytes)

    # Apply exposure (EV scale)
    scale = float(2.0 ** exposure_ev)
    hdr = hdr * scale
    # Clean any inf/nan after scaling
    hdr = np.nan_to_num(hdr, nan=0.0, posinf=1e6, neginf=0.0)
    hdr = np.clip(hdr, 0.0, 1e6)

    # Tone map using Reinhard
    ldr = _reinhard_tonemap(hdr, key=key)

    # Convert to sRGB if requested
    if to_srgb:
        ldr = _linear_to_srgb(ldr)

    rgb8 = (ldr * 255.0).round().astype(np.uint8)
    height, width = rgb8.shape[:2]

    return rgb8, width, height


def encode_to_png(rgb_array):
    """Encode RGB numpy array to PNG bytes.

    Args:
        rgb_array: (H,W,3) uint8 numpy array in RGB format

    Returns:
        bytes: PNG-encoded image data
    """
    # OpenCV expects BGR when writing
    bgr = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

    # Encode to PNG in memory
    success, buffer = cv2.imencode('.png', bgr)
    if not success:
        raise RuntimeError("Failed to encode image to PNG")

    return buffer.tobytes()


def process_exr_bytes_to_png_bytes(exr_bytes, exposure_ev=0.0, key=0.18, to_srgb=True):
    """Complete pipeline: EXR bytes to PNG bytes.

    Args:
        exr_bytes: Raw EXR file bytes
        exposure_ev: Exposure value in stops
        key: Reinhard key value
        to_srgb: Apply sRGB conversion

    Returns:
        tuple: (png_bytes, width, height)
    """
    rgb8, width, height = process_exr_to_rgb(exr_bytes, exposure_ev, key, to_srgb)
    png_bytes = encode_to_png(rgb8)
    return png_bytes, width, height