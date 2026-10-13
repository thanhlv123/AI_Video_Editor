# M79 Still Image Observation Method Contract

M79 is pure, deterministic, offline, transient, detached and non-authority.
It describes one fixed V1 method and validates declarations only. No physical
observer is implemented. Dependency requirement: NONE. No Pillow/PIL imports.
A future physical observer may use Pillow==12.3.0 only after separate qualification.

The frozen spec requires contract_version="1" and the existing M78
ObserverExecutionDescription with observer_id="pillow_png8_still",
observer_version="12.3.0", observation_method_id="png8_single_still_identity_square",
observation_method_version="1", fact_mapping_version="1", source_kind=STILL_IMAGE.
These labels authenticate nothing. Changing any label invalidates V1.
The second frozen record holds declared encoded header values, not parsed bytes.
No separate assessment is needed: validation returns the detached input or a fixed
sanitized error. It never establishes any AssessmentBoundary.

The only format is PNG8 single still with identity orientation and explicitly
square pixels. Future structural grammar is exactly:

`PNG signature -> IHDR -> pHYs -> IDAT+ -> IEND -> EOF`

The signature must be exactly `89 50 4E 47 0D 0A 1A 0A`.
Exactly one IHDR of length 13, exactly one pHYs of length 9 before the first
IDAT, one or more consecutive IDAT chunks with nonempty aggregate payload,
and exactly one IEND of length 0 immediately followed by EOF are required.
Every chunk CRC must validate. An exhaustive structural pass through EOF is
mandatory; n_frames == 1 alone is insufficient. M79 performs none of these actions.

All non-allowlisted chunks are rejected, including eXIf, tEXt, zTXt, iTXt,
iCCP, gAMA, cHRM, sRGB, PLTE, tRNS, acTL, fcTL, fdAT, DDAT and unknown/private
chunks. Animation and auxiliary presentations are outside the profile. There is
no general metadata policy map. Orientation-bearing metadata is absent by
construction; no EXIF/XMP interpretation, reflection handling, or malformed
metadata normalization is permitted. JPEG, indexed color, lower bit depths,
16-bit color and interlacing are excluded.

| Bit depth | Color type | Required decoded mode | Alpha presence |
| --- | --- | --- | --- |
| 8 | 0 | L | ABSENT |
| 8 | 2 | RGB | ABSENT |
| 8 | 4 | LA | PRESENT |
| 8 | 6 | RGBA | PRESENT |

Every other combination is rejected. Compression, filter and interlace methods
must all be 0. Mandatory pHYs has positive unsigned 32-bit X and Y pixels-per-unit,
X == Y, and unit specifier 0. Absent pHYs does not imply square pixels and is
outside this profile. Equal axes establish only this method's explicit pixel aspect.

Exact acceptance limits: max_input_bytes=33554432, max_coded_axis=4096,
max_decoded_pixels=4000000, accepted_presentations=1. Dimensions must be positive,
each axis within its limit and their product within the pixel limit. These method
acceptance limits are not hard RSS, CPU, wall-clock or native decoder allocation bounds.

Future COMPLETE success requires every STRUCTURAL_OBLIGATIONS and
COMPLETE_OBLIGATIONS entry: accepted preflight; restricted decoder identification
as PNG; dimension/mode agreement and dimension limits before raster decode;
permissive truncated-image behavior disabled; successful full raster decode;
dimension/mode agreement afterward; required alpha inspection; exact M76 mapping.
Header parsing alone and Image.verify-like behavior alone are insufficient.
L/RGB may declare OPAQUE only after full decode; tRNS is excluded, so no accepted
color-key transparency exists. For LA/RGBA every decoded alpha sample must be
inspected: all == 255 means OPAQUE, any < 255 means NOT_OPAQUE. UNKNOWN opacity
is forbidden in a successful COMPLETE result. M79 never inspects pixels.

Exact M76 mapping (using its existing types, not a parallel schema):

- byte_identity must bind the exact M77 verified identity in future runtime.
  validate_fact_mapping accepts only a detached expected SourceByteIdentity,
  validates both upstream inputs publicly and compares exact identity including
  byte_count. Equality does not establish M77 verification.
- Exactly one visual stream, inventory complete True, stream_index=0,
  source_kind=STILL_IMAGE, accepted IHDR coded dimensions.
- display_width=ExactRational(width,1), display_height=ExactRational(height,1),
  sample_aspect_ratio=ExactRational(1,1), reported_display_aspect_ratio=None.
- orientation=IDENTITY, rotation_degrees=ExactRational(0,1),
  other_display_transform_status=ABSENT; alpha/mode/opacity as above.
- decoded_presentation_count=1, presentation_multiplicity=SINGLE_STILL.
- timestamp_enumeration_status=COMPLETE, frames exactly one FrameObservation
  with ordinal=0, pts_ticks=None (M76's presentation timestamp field),
  duration_ticks=None, timestamp_origin=UNKNOWN. This completely enumerates one
  untimed presentation without creating a time domain; ABSENT is not accepted.
- nominal_frame_rate, average_frame_rate, time_base, stream_start_ticks,
  stream_duration_ticks, presentation_start_ticks, presentation_end_exclusive_ticks
  and container_duration_us are all None. No video timing is synthesized.

Future M78 SUCCEEDED + COMPLETE means all obligations of this narrow fixed
method completed. It does not mean all conceivable media facts are known.
M78 remains unchanged; M79 creates no execution record and issues no authority.

A valid spec/profile/mapping proves only structural and semantic contract validity.
It does not prove M77 bytes were accessed, PNG parsed, CRC checked, Pillow invoked,
pixels decoded, alpha inspected, execution occurred, physical observation or actual
physical completeness. There is no physical_byte_verification,
physical_observation_authority, observation_execution, M75 presentation_compliance,
M73 blocker discharge, renderer_adapter_compatibility or executability established.
Copying, deep copying and serialization/reconstruction remain detached and grant
no authority. No media I/O, filesystem access, snapshot byte access, hashing,
decoder/parser, subprocess, network, provider, renderer, Manifest/persistence,
runtime registry, live capability or authority issuance exists here.
