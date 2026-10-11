import json
from datetime import datetime
from pathlib import Path


class AnalysisManifestBuilder:

    MANIFEST_VERSION = 1


    # ==================================================
    # GENERIC GET
    # ==================================================

    def _get(
        self,
        source,
        key,
        default=None
    ):

        if source is None:
            return default

        if isinstance(
            source,
            dict
        ):

            return source.get(
                key,
                default
            )

        return getattr(
            source,
            key,
            default
        )


    # ==================================================
    # NORMALIZE LIST
    # ==================================================

    def _to_list(
        self,
        value
    ):

        if value is None:
            return []

        if isinstance(
            value,
            list
        ):
            return value

        if isinstance(
            value,
            tuple
        ):
            return list(
                value
            )

        if isinstance(
            value,
            set
        ):
            return list(
                value
            )

        return [
            value
        ]


    # ==================================================
    # FLOAT
    # ==================================================

    def _to_float(
        self,
        value,
        default=0.0
    ):

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return float(
                default
            )


    # ==================================================
    # IS THIS A REAL SCENE ANALYSIS PAYLOAD?
    # ==================================================

    def _is_scene_payload(
        self,
        value
    ):

        # --------------------------------------------------
        # DICTIONARY
        # --------------------------------------------------

        if isinstance(
            value,
            dict
        ):

            scene_id = value.get(
                "scene_id"
            )

            has_start = (
                "start"
                in value
            )

            has_end = (
                "end"
                in value
            )

            has_analysis = (
                "analysis"
                in value
            )

            has_search = (
                "search"
                in value
            )


            return bool(
                scene_id
                and has_start
                and has_end
                and has_analysis
                and has_search
            )


        # --------------------------------------------------
        # OBJECT
        # --------------------------------------------------

        scene_id = getattr(
            value,
            "scene_id",
            None
        )

        start = getattr(
            value,
            "start",
            None
        )

        end = getattr(
            value,
            "end",
            None
        )

        analysis = getattr(
            value,
            "analysis",
            None
        )

        search = getattr(
            value,
            "search",
            None
        )


        return bool(
            scene_id
            and start is not None
            and end is not None
            and analysis is not None
            and search is not None
        )


    # ==================================================
    # FIND SCENE PAYLOAD
    #
    # Handles:
    #
    # Old object:
    #
    # SceneAnalysis(...)
    #
    # Direct dict:
    #
    # {
    #   "scene_id": ...,
    #   "start": ...,
    #   "analysis": {...},
    #   "search": {...}
    # }
    #
    # Cache:
    #
    # {
    #   "cache_version": 1,
    #   "source": {...},
    #   "analysis": {
    #       REAL SCENE DATA
    #   }
    # }
    #
    # Other wrappers:
    #
    # {
    #   "status": "cached",
    #   "result": {
    #       ...
    #   }
    # }
    #
    # The function searches recursively.
    # ==================================================

    def _find_scene_payload(
        self,
        value,
        depth=0
    ):

        # Safety against broken recursive structures.

        if depth > 12:
            return None


        # ==================================================
        # FOUND IT
        # ==================================================

        if self._is_scene_payload(
            value
        ):

            return value


        # ==================================================
        # DICTIONARY
        # ==================================================

        if isinstance(
            value,
            dict
        ):

            # --------------------------------------------------
            # Search likely wrapper keys first.
            # --------------------------------------------------

            preferred_keys = [

                "analysis",

                "result",

                "data",

                "payload",

                "value",

                "cached",

                "cache",

                "response",
            ]


            for key in preferred_keys:

                if key not in value:
                    continue


                found = (
                    self._find_scene_payload(
                        value[
                            key
                        ],
                        depth=(
                            depth + 1
                        )
                    )
                )


                if found is not None:
                    return found


            # --------------------------------------------------
            # Then inspect every nested dictionary/object.
            # --------------------------------------------------

            for nested_value in (
                value.values()
            ):

                if isinstance(
                    nested_value,
                    (
                        dict,
                        list,
                        tuple,
                    )
                ):

                    found = (
                        self._find_scene_payload(
                            nested_value,
                            depth=(
                                depth + 1
                            )
                        )
                    )


                    if found is not None:
                        return found


            return None


        # ==================================================
        # LIST / TUPLE
        # ==================================================

        if isinstance(
            value,
            (
                list,
                tuple,
            )
        ):

            for item in value:

                found = (
                    self._find_scene_payload(
                        item,
                        depth=(
                            depth + 1
                        )
                    )
                )


                if found is not None:
                    return found


            return None


        # ==================================================
        # OBJECT WRAPPERS
        # ==================================================

        preferred_attributes = [

            "analysis",

            "result",

            "data",

            "payload",

            "value",

            "response",
        ]


        for attribute in (
            preferred_attributes
        ):

            nested_value = getattr(
                value,
                attribute,
                None
            )


            if nested_value is None:
                continue


            # Avoid immediately recursing into the
            # same object reference.

            if nested_value is value:
                continue


            found = (
                self._find_scene_payload(
                    nested_value,
                    depth=(
                        depth + 1
                    )
                )
            )


            if found is not None:
                return found


        return None


    # ==================================================
    # BUILD
    # ==================================================

    def build(
        self,
        analyses,
        source_srt=None,
        provider=None
    ):

        scenes = []


        if analyses is None:
            analyses = []


        for index, raw_item in enumerate(
            analyses,
            start=1
        ):

            # ==================================================
            # LOCATE REAL ANALYSIS
            # ==================================================

            analysis = (
                self._find_scene_payload(
                    raw_item
                )
            )


            if analysis is None:

                # Helpful debug output without exposing
                # credentials or unrelated environment data.

                if isinstance(
                    raw_item,
                    dict
                ):

                    keys = list(
                        raw_item.keys()
                    )

                else:

                    keys = [
                        name
                        for name in (
                            "analysis",
                            "result",
                            "data",
                            "payload",
                            "scene_id",
                            "start",
                            "end",
                            "search",
                        )
                        if hasattr(
                            raw_item,
                            name
                        )
                    ]


                raise ValueError(
                    "Could not locate scene analysis "
                    f"payload for item #{index}. "
                    f"Available top-level fields: "
                    f"{keys}"
                )


            # ==================================================
            # CORE SCENE DATA
            # ==================================================

            scene_id = self._get(
                analysis,
                "scene_id"
            )


            start = self._to_float(
                self._get(
                    analysis,
                    "start",
                    0.0
                )
            )


            end = self._to_float(
                self._get(
                    analysis,
                    "end",
                    start
                ),
                default=start
            )


            duration_value = self._get(
                analysis,
                "duration"
            )


            if duration_value is None:

                duration = (
                    end - start
                )

            else:

                duration = self._to_float(
                    duration_value,
                    default=(
                        end - start
                    )
                )


            dialogue = str(
                self._get(
                    analysis,
                    "dialogue",
                    ""
                )
                or ""
            )


            # ==================================================
            # AI ANALYSIS SECTION
            # ==================================================

            analysis_section = self._get(
                analysis,
                "analysis",
                {}
            )


            context = str(
                self._get(
                    analysis_section,
                    "context",
                    ""
                )
                or ""
            )


            subject = str(
                self._get(
                    analysis_section,
                    "subject",
                    ""
                )
                or ""
            )


            action = str(
                self._get(
                    analysis_section,
                    "action",
                    ""
                )
                or ""
            )


            location = str(
                self._get(
                    analysis_section,
                    "location",
                    ""
                )
                or ""
            )


            mood = str(
                self._get(
                    analysis_section,
                    "mood",
                    ""
                )
                or ""
            )


            shot = str(
                self._get(
                    analysis_section,
                    "shot",
                    ""
                )
                or ""
            )


            motion = str(
                self._get(
                    analysis_section,
                    "motion",
                    ""
                )
                or ""
            )


            # ==================================================
            # SEARCH SECTION
            # ==================================================

            search_section = self._get(
                analysis,
                "search",
                {}
            )


            primary_keyword = str(
                self._get(
                    search_section,
                    "primary_keyword",
                    ""
                )
                or ""
            )


            keywords = self._to_list(
                self._get(
                    search_section,
                    "keywords",
                    []
                )
            )


            avoid = self._to_list(
                self._get(
                    search_section,
                    "avoid",
                    []
                )
            )


            # ==================================================
            # MEDIA
            # ==================================================

            media_section = self._get(
                analysis,
                "media",
                {}
            )


            preferred_type = str(
                self._get(
                    media_section,
                    "preferred_type",
                    "video"
                )
                or "video"
            )


            # ==================================================
            # VALIDATION
            # ==================================================

            if not scene_id:

                raise ValueError(
                    f"Analysis item #{index} "
                    "is missing scene_id."
                )


            if end <= start:

                raise ValueError(
                    f"{scene_id}: invalid timing "
                    f"{start} -> {end}"
                )


            if not primary_keyword:

                raise ValueError(
                    f"{scene_id}: AI analysis "
                    "is missing primary_keyword."
                )


            # ==================================================
            # MANIFEST SCENE
            # ==================================================

            scene_data = {

                "scene_id":
                    str(
                        scene_id
                    ),

                "start":
                    start,

                "end":
                    end,

                "duration":
                    duration,

                "dialogue":
                    dialogue,


                # ==========================================
                # AI ANALYSIS
                # ==========================================

                "analysis": {

                    "context":
                        context,

                    "subject":
                        subject,

                    "action":
                        action,

                    "location":
                        location,

                    "mood":
                        mood,

                    "shot":
                        shot,

                    "motion":
                        motion
                },


                # ==========================================
                # STOCK SEARCH KEYWORDS
                # ==========================================

                "search": {

                    "primary_keyword":
                        primary_keyword,

                    "keywords":
                        keywords,

                    "avoid":
                        avoid
                },


                # ==========================================
                # STOCK
                # ==========================================

                "stock": {

                    "status":
                        "pending",

                    "preferred_type":
                        preferred_type,

                    "searches":
                        [],

                    "candidates":
                        [],

                    "selected_media":
                        None
                },


                # ==========================================
                # TIMELINE
                # ==========================================

                "timeline": {

                    "clip_id":
                        None,

                    "media_id":
                        None,

                    "track_id":
                        "video_1"
                }
            }


            scenes.append(
                scene_data
            )


        # ==================================================
        # MANIFEST
        # ==================================================

        manifest = {

            "version":
                self.MANIFEST_VERSION,

            "created_at": (
                datetime.now()
                .astimezone()
                .isoformat()
            ),

            "source": {

                "srt": (
                    str(
                        source_srt
                    )
                    if source_srt
                    else None
                )
            },

            "ai": {

                "provider":
                    provider
            },

            "scene_count":
                len(
                    scenes
                ),

            "scenes":
                scenes
        }


        return manifest


    # ==================================================
    # SAVE
    # ==================================================

    def save(
        self,
        manifest,
        output_path
    ):

        output_path = Path(
            output_path
        )


        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                manifest,
                file,
                indent=4,
                ensure_ascii=False
            )


        return output_path