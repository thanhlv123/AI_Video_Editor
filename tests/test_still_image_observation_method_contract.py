"""Synthetic detached declarations only: no media fixtures or observer runtime."""
import ast
from copy import copy, deepcopy
from dataclasses import fields, replace, FrozenInstanceError
import inspect
import pickle
import unittest

import creator_studio.still_image_observation_method as public
from creator_studio.still_image_observation_method import models, validation
from creator_studio.source_observation import models as facts
from creator_studio.source_observation.validation import validate_claim


def profile(**changes):
    values = dict(coded_width_px=640, coded_height_px=480, bit_depth=8,
                  color_type=2, compression_method=0, filter_method=0,
                  interlace_method=0, phys_x_pixels_per_unit=100,
                  phys_y_pixels_per_unit=100, phys_unit_specifier=0)
    values.update(changes)
    return public.EncodedStillImageProfile(**values)


def identity(count=100):
    digest = "a" * 64
    return facts.SourceByteIdentity("asset:sha256:" + digest, digest, count)


def claim(mode="RGB", opacity=facts.EffectiveOpacity.OPAQUE):
    stream = facts.VisualStreamObservation(
        stream_index=0, source_kind=facts.SourceKind.STILL_IMAGE,
        coded_width_px=640, coded_height_px=480,
        display_width=facts.ExactRational(640, 1),
        display_height=facts.ExactRational(480, 1),
        sample_aspect_ratio=facts.ExactRational(1, 1),
        reported_display_aspect_ratio=None, orientation=facts.Orientation.IDENTITY,
        rotation_degrees=facts.ExactRational(0, 1),
        other_display_transform_status=facts.OtherDisplayTransformStatus.ABSENT,
        alpha_presence=(facts.AlphaPresence.PRESENT if mode in ("LA", "RGBA")
                        else facts.AlphaPresence.ABSENT),
        effective_opacity=opacity, pixel_format=mode, decoded_presentation_count=1,
        presentation_multiplicity=facts.PresentationMultiplicity.SINGLE_STILL,
        nominal_frame_rate=None, average_frame_rate=None, time_base=None,
        stream_start_ticks=None, stream_duration_ticks=None,
        presentation_start_ticks=None, presentation_end_exclusive_ticks=None,
        timestamp_enumeration_status=facts.TimestampEnumerationStatus.COMPLETE,
        frames=(facts.FrameObservation(0, None, None, facts.TimestampOrigin.UNKNOWN),),
    )
    return facts.SourceObservationClaim(
        identity(), "pillow_png8_still", "12.3.0",
        "png8_single_still_identity_square", "1", True, (stream,), None,
    )


class StillImageObservationMethodTests(unittest.TestCase):
    def invalid(self, function, *args):
        with self.assertRaises(public.StillImageObservationMethodError) as caught:
            function(*args)
        self.assertEqual(str(caught.exception), "still_image_observation_method_invalid")
        self.assertIsNone(caught.exception.__cause__)

    def mapping(self, value=None, encoded=None, expected=None):
        return public.validate_fact_mapping(
            profile() if encoded is None else encoded,
            claim() if value is None else value,
            identity() if expected is None else expected,
        )

    def bad_stream(self, **changes):
        original = claim()
        value = replace(original, visual_streams=(replace(original.visual_streams[0], **changes),))
        self.invalid(public.validate_fact_mapping, profile(), value, identity())

    def test_contract_version(self):
        spec = public.StillImageObservationMethodSpec()
        self.assertEqual(spec.contract_version, "1")
        self.assertIs(public.validate_method_spec(spec), spec)
        for value in ("", "2", "01", 1, True, None, "x" * 1000):
            self.invalid(public.validate_method_spec, replace(spec, contract_version=value))

    def test_exact_identity(self):
        observer = public.StillImageObservationMethodSpec().observer
        self.assertEqual(tuple(getattr(observer, f.name) for f in fields(observer)), (
            "pillow_png8_still", "12.3.0", "png8_single_still_identity_square",
            "1", "1", facts.SourceKind.STILL_IMAGE))

    def test_identity_substitution(self):
        spec = public.StillImageObservationMethodSpec()
        for field in fields(spec.observer):
            for value in ("substitution", "x" * 1000, None):
                with self.subTest(field=field.name, value_type=type(value)):
                    self.invalid(public.validate_method_spec,
                                 replace(spec, observer=replace(spec.observer, **{field.name: value})))

    def test_resources(self):
        self.assertEqual((public.MAX_INPUT_BYTES, public.MAX_CODED_AXIS,
                          public.MAX_DECODED_PIXELS, public.ACCEPTED_PRESENTATIONS),
                         (33554432, 4096, 4000000, 1))

    def test_png_only(self):
        self.assertEqual(public.FORMAT, "PNG")
        self.assertEqual(public.PNG_SIGNATURE_HEX, "89 50 4E 47 0D 0A 1A 0A")
        self.assertEqual({f.name for f in fields(public.StillImageObservationMethodSpec)},
                         {"contract_version", "observer"})
        with self.assertRaises(TypeError):
            public.StillImageObservationMethodSpec(format="JPEG")

    def test_encoded_matrix_and_mapping(self):
        self.assertEqual(public.ENCODED_MODES,
                         ((8, 0, "L"), (8, 2, "RGB"), (8, 4, "LA"), (8, 6, "RGBA")))
        for color, mode in ((0, "L"), (2, "RGB"), (4, "LA"), (6, "RGBA")):
            encoded, value = profile(color_type=color), claim(mode)
            self.assertIs(public.validate_encoded_profile(encoded), encoded)
            self.assertIs(self.mapping(value, encoded), value)
            self.invalid(public.validate_fact_mapping, encoded, claim("RGB" if mode != "RGB" else "L"), identity())

    def test_other_encodings_rejected(self):
        for depth in (-1, 0, 1, 2, 4, 8, 16, 32):
            for color in range(-1, 9):
                if depth == 8 and color in (0, 2, 4, 6):
                    continue
                self.invalid(public.validate_encoded_profile, profile(bit_depth=depth, color_type=color))

    def test_interlace(self):
        for value in (-1, 1, 2, True, None):
            self.invalid(public.validate_encoded_profile, profile(interlace_method=value))

    def test_compression_filter(self):
        for name in ("compression_method", "filter_method"):
            for value in (-1, 1, True, None):
                self.invalid(public.validate_encoded_profile, profile(**{name: value}))

    def test_phys_mandatory(self):
        for name in ("phys_x_pixels_per_unit", "phys_y_pixels_per_unit", "phys_unit_specifier"):
            self.invalid(public.validate_encoded_profile, profile(**{name: None}))
        values = {f.name: getattr(profile(), f.name) for f in fields(public.EncodedStillImageProfile)}
        del values["phys_x_pixels_per_unit"]
        with self.assertRaises(TypeError):
            public.EncodedStillImageProfile(**values)

    def test_phys_equal_positive_axes(self):
        for x, y in ((0, 0), (-1, -1), (1, 2), (2, 1), (4294967296, 4294967296)):
            self.invalid(public.validate_encoded_profile,
                         profile(phys_x_pixels_per_unit=x, phys_y_pixels_per_unit=y))
        for axis in (1, 4294967295):
            public.validate_encoded_profile(profile(phys_x_pixels_per_unit=axis, phys_y_pixels_per_unit=axis))

    def test_phys_unit(self):
        for value in (-1, 1, 2, True):
            self.invalid(public.validate_encoded_profile, profile(phys_unit_specifier=value))

    def test_chunk_grammar(self):
        self.assertEqual(public.CHUNK_GRAMMAR,
                         ("PNG signature", "IHDR", "pHYs", "IDAT+", "IEND", "EOF"))
        self.assertEqual(public.ALLOWED_CHUNKS, ("IHDR", "pHYs", "IDAT", "IEND"))
        self.assertEqual(public.STRUCTURAL_OBLIGATIONS, (
            "exact PNG signature", "exactly one IHDR of length 13",
            "exactly one pHYs of length 9 before first IDAT",
            "one or more consecutive IDAT chunks with nonempty aggregate payload",
            "exactly one IEND of length 0 immediately followed by EOF",
            "validate every chunk CRC", "reject every non-allowlisted chunk",
            "exhaustive structural pass through EOF; n_frames == 1 alone is insufficient"))

    def test_non_allowlisted_chunks(self):
        for name in ("tEXt", "zTXt", "iTXt", "iCCP", "gAMA", "cHRM", "sRGB", "DDAT", "zzZZ"):
            self.assertNotIn(name, public.ALLOWED_CHUNKS)

    def test_animation_excluded(self):
        for name in ("acTL", "fcTL", "fdAT"):
            self.assertNotIn(name, public.ALLOWED_CHUNKS)
        self.bad_stream(presentation_multiplicity=facts.PresentationMultiplicity.ANIMATED)

    def test_orientation_metadata_excluded(self):
        self.assertNotIn("eXIf", public.ALLOWED_CHUNKS)
        self.assertNotIn("iTXt", public.ALLOWED_CHUNKS)

    def test_trns_excluded(self):
        self.assertNotIn("tRNS", public.ALLOWED_CHUNKS)

    def test_indexed_excluded(self):
        self.assertNotIn("PLTE", public.ALLOWED_CHUNKS)
        self.invalid(public.validate_encoded_profile, profile(color_type=3))

    def test_orientation_mapping(self):
        for value in facts.Orientation:
            if value is not facts.Orientation.IDENTITY:
                self.bad_stream(orientation=value)
        self.bad_stream(rotation_degrees=facts.ExactRational(0, 2))
        self.bad_stream(rotation_degrees=None)
        for value in (facts.OtherDisplayTransformStatus.PRESENT, facts.OtherDisplayTransformStatus.UNKNOWN):
            self.bad_stream(other_display_transform_status=value)

    def test_dimensions_and_display(self):
        for name in ("coded_width_px", "coded_height_px"):
            self.bad_stream(**{name: None})
            self.bad_stream(**{name: 10})
            for value in (0, -1, 4097):
                self.invalid(public.validate_encoded_profile, profile(**{name: value}))
        for name in ("display_width", "display_height"):
            self.bad_stream(**{name: None})
            self.bad_stream(**{name: facts.ExactRational(10, 1)})
        self.bad_stream(display_width=facts.ExactRational(1280, 2))
        self.invalid(public.validate_encoded_profile, profile(coded_width_px=2001, coded_height_px=2000))
        public.validate_encoded_profile(profile(coded_width_px=2000, coded_height_px=2000))
        public.validate_encoded_profile(profile(coded_width_px=4096, coded_height_px=1))

    def test_square_pixel_mapping(self):
        for value in (None, facts.ExactRational(2, 2), facts.ExactRational(2, 1)):
            self.bad_stream(sample_aspect_ratio=value)

    def test_reported_dar_absent(self):
        self.bad_stream(reported_display_aspect_ratio=facts.ExactRational(4, 3))

    def test_no_alpha_modes(self):
        for color, mode in ((0, "L"), (2, "RGB")):
            value = claim(mode)
            self.assertIs(value.visual_streams[0].alpha_presence, facts.AlphaPresence.ABSENT)
            for alpha in (facts.AlphaPresence.PRESENT, facts.AlphaPresence.UNKNOWN):
                bad = replace(value, visual_streams=(replace(value.visual_streams[0], alpha_presence=alpha),))
                self.invalid(public.validate_fact_mapping, profile(color_type=color), bad, identity())
            self.invalid(public.validate_fact_mapping, profile(color_type=color),
                         claim(mode, facts.EffectiveOpacity.NOT_OPAQUE), identity())

    def test_alpha_modes(self):
        for color, mode in ((4, "LA"), (6, "RGBA")):
            for opacity in (facts.EffectiveOpacity.OPAQUE, facts.EffectiveOpacity.NOT_OPAQUE):
                value = claim(mode, opacity)
                self.assertIs(value.visual_streams[0].alpha_presence, facts.AlphaPresence.PRESENT)
                self.mapping(value, profile(color_type=color))
            value = claim(mode)
            for alpha in (facts.AlphaPresence.ABSENT, facts.AlphaPresence.UNKNOWN):
                bad = replace(value, visual_streams=(replace(value.visual_streams[0], alpha_presence=alpha),))
                self.invalid(public.validate_fact_mapping, profile(color_type=color), bad, identity())

    def test_unknown_opacity_forbidden(self):
        for color, mode in ((0, "L"), (2, "RGB"), (4, "LA"), (6, "RGBA")):
            self.invalid(public.validate_fact_mapping, profile(color_type=color),
                         claim(mode, facts.EffectiveOpacity.UNKNOWN), identity())

    def test_full_decode_obligations(self):
        self.assertEqual(public.COMPLETE_OBLIGATIONS, (
            "bind exact M77 verified byte identity", "accepted structural preflight",
            "restricted decoder identification as PNG",
            "dimension and mode agreement with preflight before raster decode",
            "dimensions within limits before raster decode",
            "permissive truncated-image behavior disabled", "successful full raster decode",
            "dimension and mode agreement with preflight after raster decode",
            "L/RGB opaque only after full decode; inspect every LA/RGBA alpha sample",
            "all alpha samples 255 means OPAQUE; any below 255 means NOT_OPAQUE",
            "validate exact M76 fact mapping"))

    def test_count_single(self):
        for value in (None, 0, 2, True):
            self.bad_stream(decoded_presentation_count=value)

    def test_multiplicity_single(self):
        for value in facts.PresentationMultiplicity:
            if value is not facts.PresentationMultiplicity.SINGLE_STILL:
                self.bad_stream(presentation_multiplicity=value)

    def test_timestamp_complete(self):
        for value in (facts.TimestampEnumerationStatus.ABSENT, facts.TimestampEnumerationStatus.PARTIAL):
            self.bad_stream(timestamp_enumeration_status=value)

    def test_untimed_frame(self):
        self.assertEqual(self.mapping().visual_streams[0].frames,
                         (facts.FrameObservation(0, None, None, facts.TimestampOrigin.UNKNOWN),))
        frame = facts.FrameObservation(0, None, None, facts.TimestampOrigin.UNKNOWN)
        for frames_value in ((), (frame, frame), (replace(frame, ordinal=1),),
                             (replace(frame, pts_ticks=0),), (replace(frame, duration_ticks=1),),
                             (replace(frame, timestamp_origin=facts.TimestampOrigin.NORMALIZED_ZERO),)):
            self.bad_stream(frames=frames_value)

    def test_timing_absent(self):
        for name in ("nominal_frame_rate", "average_frame_rate", "time_base"):
            self.bad_stream(**{name: facts.ExactRational(1, 1)})
        for name in ("stream_start_ticks", "stream_duration_ticks", "presentation_start_ticks",
                     "presentation_end_exclusive_ticks"):
            self.bad_stream(**{name: 0})

    def test_container_duration_absent(self):
        self.invalid(public.validate_fact_mapping, profile(), replace(claim(), container_duration_us=0), identity())

    def test_exact_identity_binding(self):
        self.mapping(expected=identity())
        for expected in (identity(101), identity(33554433), identity(0)):
            self.invalid(public.validate_fact_mapping, profile(), claim(), expected)
        for count in (33554432, 33554433):
            value = replace(claim(), byte_identity=identity(count))
            if count == 33554432:
                self.mapping(value, expected=identity(count))
            else:
                self.invalid(public.validate_fact_mapping, profile(), value, identity(count))

    def test_stream_inventory(self):
        value = claim()
        for changes in (dict(visual_stream_inventory_complete=False), dict(visual_streams=()),
                        dict(visual_streams=value.visual_streams * 2)):
            self.invalid(public.validate_fact_mapping, profile(), replace(value, **changes), identity())
        self.bad_stream(stream_index=1)
        self.bad_stream(source_kind=facts.SourceKind.WHOLE_VIDEO)

    def test_mapping_labels(self):
        for name in ("observer_id", "observer_version", "observation_method_id", "observation_method_version"):
            self.invalid(public.validate_fact_mapping, profile(), replace(claim(), **{name: "different"}), identity())

    def test_complete_not_all_facts_known(self):
        result = self.mapping()
        self.assertIsNone(result.container_duration_us)
        self.assertIsNone(result.visual_streams[0].time_base)
        self.assertIs(result.visual_streams[0].frames[0].timestamp_origin, facts.TimestampOrigin.UNKNOWN)
        self.assertIsNone(result.visual_streams[0].reported_display_aspect_ratio)

    def test_complete_not_authority_or_execution(self):
        # Entirely manual, unverified declarations pass. No execution record is issued.
        value = claim()
        self.assertIs(self.mapping(value), value)
        self.assertIs(type(value), facts.SourceObservationClaim)
        for field in ("physical_byte_verification", "physical_observation_authority",
                      "observation_execution", "physical_completeness"):
            self.assertFalse(hasattr(value, field))

    def test_no_m75_compliance(self):
        self.assertFalse(hasattr(self.mapping(), "presentation_compliance"))
        self.assertNotIn("assess", " ".join(public.__all__))

    def test_no_m73_blocker_discharge(self):
        self.assertFalse(hasattr(self.mapping(), "blocker_discharge"))
        self.assertNotIn("blocker", " ".join(public.__all__))

    def test_no_manifest_persistence(self):
        for name in public.__all__:
            self.assertFalse(any(word in name.lower() for word in ("manifest", "persist", "save", "load")))
        self.assertEqual({f.name for f in fields(public.EncodedStillImageProfile)}, {
            "coded_width_px", "coded_height_px", "bit_depth", "color_type", "compression_method",
            "filter_method", "interlace_method", "phys_x_pixels_per_unit", "phys_y_pixels_per_unit",
            "phys_unit_specifier"})

    def test_copy_serialization_detached(self):
        for value, validator in ((public.StillImageObservationMethodSpec(), public.validate_method_spec),
                                 (profile(), public.validate_encoded_profile),
                                 (claim(), lambda item: self.mapping(item))):
            for clone in (copy(value), deepcopy(value), pickle.loads(pickle.dumps(value))):
                self.assertEqual(clone, value)
                self.assertIs(validator(clone), clone)
                self.assertFalse(hasattr(clone, "authority"))
                self.assertFalse(hasattr(clone, "capability"))

    def test_frozen(self):
        for value in (public.StillImageObservationMethodSpec(), profile()):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, "changed")

    def test_subclass_rejection(self):
        class SpecSubclass(public.StillImageObservationMethodSpec):
            pass
        class ProfileSubclass(public.EncodedStillImageProfile):
            pass
        class StringSubclass(str):
            pass
        self.invalid(public.validate_method_spec, SpecSubclass())
        self.invalid(public.validate_method_spec,
                     replace(public.StillImageObservationMethodSpec(), contract_version=StringSubclass("1")))
        self.invalid(public.validate_encoded_profile,
                     ProfileSubclass(**vars(profile())))
        class ClaimSubclass(facts.SourceObservationClaim):
            pass
        self.invalid(public.validate_fact_mapping, profile(), ClaimSubclass(**vars(claim())), identity())
        class ObserverSubclass(type(public.StillImageObservationMethodSpec().observer)):
            pass
        spec = public.StillImageObservationMethodSpec()
        self.invalid(public.validate_method_spec, replace(spec, observer=ObserverSubclass(**vars(spec.observer))))

    def test_bool_not_int(self):
        for field in fields(public.EncodedStillImageProfile):
            self.invalid(public.validate_encoded_profile, profile(**{field.name: True}))
        self.bad_stream(stream_index=False)
        self.invalid(public.validate_fact_mapping, profile(), claim(), replace(identity(), byte_count=True))

    def test_missing_extra_invalid_fields(self):
        for value, validator in ((public.StillImageObservationMethodSpec(), public.validate_method_spec),
                                 (profile(), public.validate_encoded_profile)):
            self.invalid(validator, None)
            missing = deepcopy(value)
            object.__getattribute__(missing, "__dict__").pop(fields(value)[0].name)
            self.invalid(validator, missing)
            extra = deepcopy(value)
            object.__setattr__(extra, "unexpected", 1)
            self.invalid(validator, extra)
        self.invalid(public.validate_fact_mapping, profile(), None, identity())
        self.invalid(public.validate_fact_mapping, profile(), claim(), None)

    def test_oversized_and_sanitized_errors(self):
        sentinel = "PRIVATE_INPUT_MUST_NOT_APPEAR" * 1000
        spec = public.StillImageObservationMethodSpec()
        self.invalid(public.validate_method_spec, replace(spec, contract_version=sentinel))
        self.invalid(public.validate_method_spec, replace(spec, observer=replace(spec.observer, observer_id=sentinel)))
        self.invalid(public.validate_encoded_profile, profile(color_type=sentinel))
        self.invalid(public.validate_fact_mapping, profile(), replace(claim(), observer_id=sentinel), identity())

    def test_upstream_validation_precedes_comparison(self):
        value = claim()
        stream = value.visual_streams[0]
        bad = replace(value, visual_streams=(replace(stream, display_width=facts.ExactRational(640, 0)),))
        self.invalid(public.validate_fact_mapping, profile(), bad, identity())
        extra = deepcopy(value)
        object.__setattr__(extra.visual_streams[0], "unexpected", "secret")
        self.invalid(public.validate_fact_mapping, profile(), extra, identity())
        self.assertIs(validate_claim(value), value)

    def test_hostile_values_do_not_run_hooks(self):
        class Hostile:
            def boom(self, *args, **kwargs):
                raise AssertionError("caller hook executed")
            __str__ = __repr__ = __eq__ = __hash__ = __len__ = boom
            __getattribute__ = boom
        bad = Hostile()
        self.invalid(public.validate_method_spec, bad)
        self.invalid(public.validate_encoded_profile, profile(bit_depth=bad))
        self.invalid(public.validate_method_spec,
                     replace(public.StillImageObservationMethodSpec(), contract_version=bad))

    def test_static_dependency_and_operation_boundary(self):
        allowed_imports = {
            "dataclasses", "models", "validation", "observation_execution.models",
            "observation_execution.validation", "source_observation.models",
            "source_observation.validation",
        }
        forbidden_calls = {"open", "read", "write", "read_bytes", "write_bytes", "snapshot_bytes",
                           "observe", "decode", "parse", "attest", "eval", "exec", "__import__",
                           "compile", "getenv", "time", "now", "crc32", "sha256"}
        for module in (public, models, validation):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.fail("contract uses an unapproved absolute module import")
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed_imports)
                    self.assertFalse(any(name.name == "*" for name in node.names))
                    for name in node.names:
                        self.assertNotIn(name.name, {"PIL", "Pillow", "Image", "PngImagePlugin",
                                                     "ObservationExecutionRecord", "SourceSnapshotDescriptor"})
                if isinstance(node, ast.Call):
                    name = node.func.id if isinstance(node.func, ast.Name) else (
                        node.func.attr if isinstance(node.func, ast.Attribute) else "")
                    self.assertNotIn(name, forbidden_calls)
                if isinstance(node, ast.Constant):
                    self.assertIsNot(type(node.value), bytes)
            for name, value in vars(module).items():
                if inspect.isfunction(value) and value.__module__ == module.__name__:
                    self.assertNotIn(name, {"observe", "decode", "parse", "attest", "register"})

    def test_public_api_exact(self):
        self.assertEqual(public.__all__, (
            "StillImageObservationMethodSpec", "EncodedStillImageProfile",
            "StillImageObservationMethodError", "MAX_INPUT_BYTES", "MAX_CODED_AXIS",
            "MAX_DECODED_PIXELS", "ACCEPTED_PRESENTATIONS", "FORMAT", "PNG_SIGNATURE_HEX",
            "CHUNK_GRAMMAR", "ALLOWED_CHUNKS", "ENCODED_MODES",
            "STRUCTURAL_OBLIGATIONS", "COMPLETE_OBLIGATIONS",
            "validate_method_spec", "validate_encoded_profile", "validate_fact_mapping"))
        self.assertEqual(len(set(public.__all__)), len(public.__all__))
        self.assertTrue(all(hasattr(public, name) for name in public.__all__))


if __name__ == "__main__":
    unittest.main()
