"""Decode and normalize selected snapshots before storage or any provider use."""
import hashlib
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import APIError


def sanitize(raw, mime_type, settings):
    if len(raw) > settings.max_image_bytes:
        raise APIError(413, "TOO_LARGE", "Image exceeds the 10 MiB limit.")
    if mime_type not in ("image/jpeg", "image/png"):
        raise APIError(415, "UNSUPPORTED_MEDIA", "Only JPEG and PNG snapshots are accepted.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as candidate:
                expected = "JPEG" if mime_type == "image/jpeg" else "PNG"
                if candidate.format != expected or candidate.width * candidate.height > settings.max_pixels:
                    raise ValueError("Format or pixel limit")
                candidate.verify()
            with Image.open(BytesIO(raw)) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((settings.image_side, settings.image_side))
                output = BytesIO()
                # Reconstruct pixel data so EXIF, comments, ICC and ancillary chunks do not survive.
                clean = Image.frombytes("RGB", image.size, image.tobytes())
                clean.save(output, format="JPEG", quality=85)
        data = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise APIError(422, "INVALID_IMAGE", "Snapshot is invalid or exceeds decoded image limits.") from None
    return {"bytes": data, "mime_type": "image/jpeg", "sha256": hashlib.sha256(data).hexdigest()}
