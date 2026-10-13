"""Fixed V1 method descriptions only; no physical observation authority."""
from dataclasses import dataclass
from ..observation_execution.models import ObserverExecutionDescription
from ..source_observation.models import SourceKind

MAX_INPUT_BYTES = 33554432
MAX_CODED_AXIS = 4096
MAX_DECODED_PIXELS = 4000000
ACCEPTED_PRESENTATIONS = 1
FORMAT = "PNG"
PNG_SIGNATURE_HEX = "89 50 4E 47 0D 0A 1A 0A"
CHUNK_GRAMMAR = ("PNG signature", "IHDR", "pHYs", "IDAT+", "IEND", "EOF")
ALLOWED_CHUNKS = ("IHDR", "pHYs", "IDAT", "IEND")
ENCODED_MODES = ((8, 0, "L"), (8, 2, "RGB"), (8, 4, "LA"), (8, 6, "RGBA"))
STRUCTURAL_OBLIGATIONS = (
    "exact PNG signature",
    "exactly one IHDR of length 13",
    "exactly one pHYs of length 9 before first IDAT",
    "one or more consecutive IDAT chunks with nonempty aggregate payload",
    "exactly one IEND of length 0 immediately followed by EOF",
    "validate every chunk CRC",
    "reject every non-allowlisted chunk",
    "exhaustive structural pass through EOF; n_frames == 1 alone is insufficient",
)
COMPLETE_OBLIGATIONS = (
    "bind exact M77 verified byte identity",
    "accepted structural preflight",
    "restricted decoder identification as PNG",
    "dimension and mode agreement with preflight before raster decode",
    "dimensions within limits before raster decode",
    "permissive truncated-image behavior disabled",
    "successful full raster decode",
    "dimension and mode agreement with preflight after raster decode",
    "L/RGB opaque only after full decode; inspect every LA/RGBA alpha sample",
    "all alpha samples 255 means OPAQUE; any below 255 means NOT_OPAQUE",
    "validate exact M76 fact mapping",
)


class StillImageObservationMethodError(ValueError):
    def __init__(self):
        super().__init__("still_image_observation_method_invalid")


@dataclass(frozen=True)
class StillImageObservationMethodSpec:
    contract_version: str = "1"
    observer: ObserverExecutionDescription = ObserverExecutionDescription(
        "pillow_png8_still", "12.3.0", "png8_single_still_identity_square",
        "1", "1", SourceKind.STILL_IMAGE,
    )


@dataclass(frozen=True)
class EncodedStillImageProfile:
    """Detached declared header facts, never parsed or physically verified here."""
    coded_width_px: int
    coded_height_px: int
    bit_depth: int
    color_type: int
    compression_method: int
    filter_method: int
    interlace_method: int
    phys_x_pixels_per_unit: int
    phys_y_pixels_per_unit: int
    phys_unit_specifier: int
