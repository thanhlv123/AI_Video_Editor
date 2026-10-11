import os
from pathlib import Path
from copy import deepcopy

from stock.pexels import PexelsProvider
from stock.pixabay import PixabayProvider
from stock.balanced_search_manager import BalancedStockSearchManager as StockSearchManager
from stock.ranker import MediaRanker
from stock.visual_ranker import VisualRanker
from stock.selector import MediaSelector
from stock.downloader import DownloadManager, DownloadError
from stock.validator import MediaValidator, MediaValidationError


from pipeline.context_geo import (
    filter_geography_candidates,
)


from pipeline.visual_strategy import (
    enrich_manifest_with_visual_strategy,
    filter_adaptive_geography_candidates,
)

class ScenePipeline:

    @staticmethod
    def _env_enabled(
        name,
        default=True,
    ):

        raw = os.getenv(
            name
        )

        if raw is None:
            return bool(
                default
            )

        value = str(
            raw
        ).strip().lower()

        return value not in (
            "0",
            "false",
            "no",
            "off",
            "disabled",
        )


    def __init__(
        self,
        download_dir,
        per_query=5,
        max_candidates=20,
        visual_top_n=10,
        review_mode="safe",
        max_search_retries=1,
        duration_tolerance=0.05,
        minimum_fallback_score=0.75,
    ):

        if review_mode not in (
            "safe",
            "auto",
        ):
            raise ValueError(
                "review_mode must be 'safe' or 'auto'"
            )

        if max_search_retries < 0:
            raise ValueError(
                "max_search_retries cannot be negative"
            )

        if duration_tolerance < 0:
            raise ValueError(
                "duration_tolerance cannot be negative"
            )

        self.download_dir = Path(
            download_dir
        )

        self.visual_top_n = int(
            visual_top_n
        )

        self.review_mode = review_mode

        self.max_search_retries = int(
            max_search_retries
        )

        self.duration_tolerance = float(
            duration_tolerance
        )

        self.minimum_fallback_score = float(
            minimum_fallback_score
        )

        # ==========================================
        # STOCK PROVIDERS
        # ==========================================

        self.stock_providers = []

        self.pexels = None
        self.pixabay = None

        pexels_enabled = self._env_enabled(
            "STOCK_PROVIDER_PEXELS",
            default=True,
        )

        pixabay_enabled = self._env_enabled(
            "STOCK_PROVIDER_PIXABAY",
            default=True,
        )

        if pexels_enabled:

            self.pexels = PexelsProvider()

            self.stock_providers.append(
                self.pexels
            )

        if pixabay_enabled:

            self.pixabay = PixabayProvider()

            self.stock_providers.append(
                self.pixabay
            )

        if not self.stock_providers:

            raise RuntimeError(
                "No stock providers are enabled."
            )

        print(
            "Stock providers enabled:",
            [
                provider.name
                for provider
                in self.stock_providers
            ],
        )

        self.search_manager = StockSearchManager(

            providers=
                self.stock_providers,

            per_query=
                per_query,

            max_candidates=
                max_candidates,
        )


        self.media_ranker = MediaRanker(
            target_width=1920,
            target_height=1080,
        )

        self.visual_ranker = VisualRanker(
            model="gpt-6-luna",
            reasoning_effort="low",
            local_weight=0.30,
            visual_weight=0.70,
        )

        self.selector = MediaSelector(
            auto_threshold=0.85,
            margin_threshold=0.08,
            minimum_threshold=0.75,
        )

        self.downloader = DownloadManager(
            output_dir=self.download_dir
        )

        self.validator = MediaValidator()


    # ==================================================
    # BASIC HELPERS
    # ==================================================

    def _to_float(
        self,
        value,
        default=None,
    ):

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return default


    def _scene_duration(
        self,
        scene,
    ):

        duration = self._to_float(
            scene.get(
                "duration"
            ),
            default=None,
        )

        if (
            duration is not None
            and duration > 0
        ):

            return duration


        start = self._to_float(
            scene.get(
                "start"
            ),
            default=0.0,
        )

        end = self._to_float(
            scene.get(
                "end"
            ),
            default=start,
        )


        return max(
            0.0,
            end - start,
        )


    def _media_identity(
        self,
        media,
    ):

        if not isinstance(
            media,
            dict,
        ):

            return None


        provider = str(
            media.get(
                "provider",
                ""
            )
            or ""
        ).strip().lower()


        media_id = str(
            media.get(
                "media_id",
                ""
            )
            or ""
        ).strip()


        if not media_id:

            return None


        return (
            provider,
            media_id,
        )


    def _known_media_duration(
        self,
        media,
    ):

        if not isinstance(
            media,
            dict,
        ):

            return None


        duration = self._to_float(
            media.get(
                "duration"
            ),
            default=None,
        )


        if (
            duration is None
            or duration <= 0
        ):

            return None


        return duration


    def _is_video(
        self,
        media,
    ):

        return (
            str(
                media.get(
                    "media_type",
                    ""
                )
                or ""
            )
            .strip()
            .lower()
            == "video"
        )


    # ==================================================
    # REJECTED MEDIA
    # ==================================================

    def _get_rejected_identities(
        self,
        stock,
    ):

        rejected = set()


        for item in stock.get(
            "rejected_media",
            [],
        ):

            identity = (
                self._media_identity(
                    item
                )
            )


            if identity is not None:

                rejected.add(
                    identity
                )


        return rejected


    def _record_rejection(
        self,
        stock,
        media,
        reason,
        validation=None,
        download=None,
    ):

        rejected = stock.setdefault(
            "rejected_media",
            [],
        )


        identity = (
            self._media_identity(
                media
            )
        )


        entry = {

            "provider":
                media.get(
                    "provider"
                ),

            "media_id":
                media.get(
                    "media_id"
                ),

            "media_type":
                media.get(
                    "media_type"
                ),

            "title":
                media.get(
                    "title"
                ),

            "reason":
                str(
                    reason
                ),
        }


        if validation is not None:

            entry[
                "validation"
            ] = validation


        if download is not None:

            entry[
                "download"
            ] = download


        if identity is not None:

            for index, existing in enumerate(
                rejected
            ):

                if (
                    self._media_identity(
                        existing
                    )
                    == identity
                ):

                    rejected[
                        index
                    ] = entry

                    return


        rejected.append(
            entry
        )


    # ==================================================
    # DURATION FILTER
    # BEFORE LOCAL / VISUAL RANK
    # ==================================================

    def _filter_candidates_by_duration(
        self,
        scene,
        candidates,
        stock,
    ):

        required_duration = (
            self._scene_duration(
                scene
            )
        )


        rejected_ids = (
            self._get_rejected_identities(
                stock
            )
        )


        kept = []

        removed_short = []

        removed_previous = []

        unknown_duration = []


        for candidate in candidates:

            identity = (
                self._media_identity(
                    candidate
                )
            )


            if (
                identity is not None
                and identity in rejected_ids
            ):

                removed_previous.append(
                    candidate
                )

                continue


            # Images can stay on screen as long as needed.

            if not self._is_video(
                candidate
            ):

                kept.append(
                    candidate
                )

                continue


            candidate_duration = (
                self._known_media_duration(
                    candidate
                )
            )


            # Unknown provider duration is allowed.
            # FFprobe checks it later.

            if candidate_duration is None:

                unknown_duration.append(
                    candidate
                )

                kept.append(
                    candidate
                )

                continue


            if (
                candidate_duration
                + self.duration_tolerance
                < required_duration
            ):

                removed_short.append(
                    candidate
                )

                continue


            kept.append(
                candidate
            )


        print()

        print(
            "[DURATION FILTER]"
        )

        print(
            "Required scene duration:",
            round(
                required_duration,
                3,
            ),
            "s",
        )

        print(
            "Candidates before:",
            len(
                candidates
            ),
        )

        print(
            "Removed too short:",
            len(
                removed_short
            ),
        )

        print(
            "Removed previously rejected:",
            len(
                removed_previous
            ),
        )

        print(
            "Unknown duration kept:",
            len(
                unknown_duration
            ),
        )

        print(
            "Candidates after:",
            len(
                kept
            ),
        )


        return {

            "candidates":
                kept,

            "required_duration":
                required_duration,

            "removed_short":
                removed_short,

            "removed_previous":
                removed_previous,

            "unknown_duration":
                unknown_duration,
        }


    # ==================================================
    # BUILD RETRY QUERIES
    # ==================================================

    def _build_retry_queries(
        self,
        scene,
    ):

        search = scene.get(
            "search",
            {},
        )


        original_queries = []


        primary = search.get(
            "primary_keyword"
        )


        if primary:

            original_queries.append(
                primary
            )


        for key in (

            "keywords",

            "search_queries",

            "queries",

            "alternatives",

            "secondary_keywords",

        ):

            value = search.get(
                key
            )


            if isinstance(
                value,
                list,
            ):

                original_queries.extend(
                    value
                )


            elif isinstance(
                value,
                str,
            ):

                original_queries.append(
                    value
                )


        dialogue = str(
            scene.get(
                "dialogue",
                ""
            )
            or ""
        ).lower()


        analysis_section = scene.get(
            "analysis",
            {},
        )


        context = str(
            scene.get(
                "context",
                analysis_section.get(
                    "context",
                    "",
                ),
            )
            or ""
        ).lower()


        combined_text = (

            dialogue

            + " "

            + context

            + " "

            + " ".join(
                str(
                    item
                )
                for item
                in original_queries
            ).lower()
        )


        retry_queries = []


        # ==================================================
        # ANIMALS
        # ==================================================

        animal_words = (

            "animal",

            "animals",

            "livestock",

            "chicken",

            "chickens",

            "cow",

            "cows",

            "cattle",

            "goat",

            "goats",

            "pig",

            "pigs",

            "duck",

            "ducks",

            "buffalo",
        )


        if any(
            word in combined_text
            for word in animal_words
        ):

            retry_queries.extend([

                "farmer feeding animals",

                "farmer caring for livestock",

                "rural livestock farming",

                "farm animal care",

                "feeding chickens farm",

                "feeding cows farm",
            ])


        # ==================================================
        # FARM
        # ==================================================

        farm_words = (

            "farm",

            "farmer",

            "field",

            "farming",

            "agriculture",

            "rice",

            "harvest",

            "crop",
        )


        if any(
            word in combined_text
            for word in farm_words
        ):

            retry_queries.extend([

                "farmer working field",

                "rural farming",

                "farm work countryside",

                "farmer daily work",

                "agriculture countryside",
            ])


        # ==================================================
        # RURAL
        # ==================================================

        rural_words = (

            "rural",

            "village",

            "countryside",

            "country life",
        )


        if any(
            word in combined_text
            for word in rural_words
        ):

            retry_queries.extend([

                "rural daily life",

                "village daily life",

                "countryside people working",

                "rural home life",

                "village countryside",
            ])


        # ==================================================
        # MORNING
        # ==================================================

        if any(
            word in combined_text
            for word in (
                "morning",
                "sunrise",
                "dawn",
                "early",
            )
        ):

            retry_queries.extend([

                "rural morning",

                "village morning",

                "countryside sunrise",

                "farmer morning work",
            ])


        # ==================================================
        # GENERIC QUERY SIMPLIFICATION
        # ==================================================

        removable_words = {

            "people",

            "person",

            "family",

            "daily",

            "simple",

            "peaceful",

            "quiet",

            "near",

            "home",

            "traditional",

            "local",
        }


        for query in original_queries:

            words = (

                str(
                    query
                )
                .lower()
                .replace(
                    ",",
                    " "
                )
                .replace(
                    ".",
                    " "
                )
                .split()
            )


            simplified = [

                word

                for word
                in words

                if word
                not in removable_words
            ]


            if len(
                simplified
            ) >= 2:

                retry_queries.append(
                    " ".join(
                        simplified
                    )
                )


        unique = []

        seen = set()


        for query in retry_queries:

            query = " ".join(
                query.split()
            ).strip()


            if not query:

                continue


            key = query.lower()


            if key in seen:

                continue


            seen.add(
                key
            )


            unique.append(
                query
            )


        return unique[
            :6
        ]


    # ==================================================
    # RETRY SCENE
    # ==================================================

    def _make_retry_scene(
        self,
        scene,
    ):

        retry_scene = deepcopy(
            scene
        )


        retry_queries = (
            self._build_retry_queries(
                scene
            )
        )


        if not retry_queries:

            return None


        retry_scene.setdefault(
            "search",
            {},
        )


        retry_scene[
            "search"
        ][
            "primary_keyword"
        ] = retry_queries[
            0
        ]


        retry_scene[
            "search"
        ][
            "keywords"
        ] = retry_queries[
            1:
        ]


        retry_scene[
            "search"
        ][
            "search_queries"
        ] = retry_queries


        retry_scene[
            "search"
        ][
            "queries"
        ] = retry_queries


        return retry_scene


    # ==================================================
    # SEARCH + RANK + VISUAL + SELECT
    # ==================================================

    def _search_and_select(
        self,
        scene,
        attempt=0,
        real_stock=None,
    ):

        stock = scene[
            "stock"
        ]


        if real_stock is None:

            real_stock = stock


        print()

        print(
            f"[SEARCH ATTEMPT {attempt + 1}]"
        )


        # ==================================================
        # VISUAL PROXY SEARCH 58D V1
        #
        # Only first search attempt activates the strategy.
        # Existing retry logic remains unchanged.
        # ==================================================

        if (
            attempt == 0
            and
            not scene.get(
                "search",
                {},
            ).get(
                "visual_proxy_search"
            )
        ):

            enrich_manifest_with_visual_strategy(
                {
                    "scenes": [
                        scene
                    ]
                },
                activate_search=True,
            )


        visual_strategy = scene.get(
            "visual_strategy",
            {},
        )


        print(
            "Visual strategy:",
            visual_strategy.get(
                "geo_policy",
                "STRICT",
            ),
        )


        if visual_strategy.get(
            "explicit_place"
        ):

            print(
                "Visual location:",
                visual_strategy.get(
                    "explicit_place"
                ),
            )


        # VISUAL QUERY ORDER 58D V2
        #
        # First attempt uses interleaved Visual Strategy
        # queries.
        #
        # Retry attempts keep the old retry-search logic.
        scene.setdefault(
            "search",
            {},
        )[
            "visual_strategy_query_order_active"
        ] = (
            attempt == 0
        )


        candidates = (
            self.search_manager.search_scene(
                scene
            )
        )

        # ADAPTIVE GEOGRAPHY GUARD 58D V1
        (
            candidates,
            geography_rejected,
            geography_bypassed,
        ) = filter_adaptive_geography_candidates(
            scene,
            candidates,
        )

        if geography_rejected:

            stock.setdefault(
                "geography_rejected",
                [],
            ).extend(
                geography_rejected
            )

            print(
                "Geography guard rejected:",
                len(geography_rejected),
            )

            for rejected in (
                geography_rejected[:5]
            ):

                print(
                    "  -",
                    rejected.get("provider"),
                    rejected.get("media_id"),
                    rejected.get("detected_countries"),
                )

        if geography_bypassed:

            print(
                "Geography guard safety bypass: "
                "all candidates conflicted."
            )


        if not candidates:

            return {

                "success":
                    False,

                "status":
                    "search_failed",

                "reason":
                    "No stock candidates found.",
            }


        print(
            "Candidates:",
            len(
                candidates
            ),
        )


        # ==================================================
        # FILTER SHORT VIDEOS BEFORE AI VISUAL RANK
        # ==================================================

        duration_filter = (
            self._filter_candidates_by_duration(
                scene=scene,
                candidates=candidates,
                stock=real_stock,
            )
        )


        candidates = (
            duration_filter[
                "candidates"
            ]
        )


        if not candidates:

            return {

                "success":
                    False,

                "status":
                    "duration_filter_failed",

                "reason":
                    (
                        "All stock video candidates "
                        "were shorter than the scene "
                        "or were previously rejected."
                    ),

                "duration_filter":
                    duration_filter,
            }


        stock[
            "candidates"
        ] = candidates


        # ==================================================
        # LOCAL RANK
        # ==================================================

        print()

        print(
            "Local ranking..."
        )


        ranked = (
            self.media_ranker.rank(
                scene=scene,
                candidates=candidates,
            )
        )


        if not ranked:

            return {

                "success":
                    False,

                "status":
                    "ranking_failed",

                "reason":
                    (
                        "Local ranking returned "
                        "no candidates."
                    ),

                "duration_filter":
                    duration_filter,
            }


        print(
            "Best local score:",
            ranked[
                0
            ].get(
                "score"
            ),
        )


        # ==================================================
        # VISUAL RANK
        # ==================================================

        print()

        print(
            "AI visual ranking..."
        )


        top_candidates = ranked[
            :self.visual_top_n
        ]


        # AI VISUAL FALLBACK V5
        try:

            visual_ranked = (
                self.visual_ranker.rank(
                    scene=scene,
                    candidates=top_candidates,
                    top_n=self.visual_top_n,
                )
            )

        except Exception as error:

            error_text = str(
                error
            ).lower()

            transient_error = any(
                token in error_text
                for token in (
                    "http 429",
                    "http 500",
                    "http 502",
                    "http 503",
                    "http 504",
                    "server_error",
                    "server exception",
                    "timeout",
                    "timed out",
                    "connection",
                )
            )

            if (
                self.review_mode != "auto"
                or not transient_error
            ):
                raise

            print()
            print("=" * 70)
            print("AI VISUAL RANKING FALLBACK")
            print("=" * 70)

            print(
                "KIE unavailable after retries:",
                str(error),
            )

            print(
                "Using LOCAL ranking for this scene."
            )

            visual_ranked = []

            for candidate in top_candidates:

                item = dict(
                    candidate
                )

                try:
                    local_score = float(
                        item.get("score", 0)
                        or 0
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    local_score = 0.0

                item["local_score"] = (
                    round(
                        local_score,
                        3,
                    )
                )

                item["visual_score"] = None

                item["visual_reason"] = (
                    "KIE transient failure; "
                    "local-ranking fallback used."
                )

                item["final_score"] = (
                    round(
                        local_score,
                        3,
                    )
                )

                item["ranking_fallback"] = (
                    "local_only"
                )

                visual_ranked.append(
                    item
                )

            visual_ranked.sort(
                key=lambda item: (
                    item.get(
                        "final_score",
                        0,
                    )
                ),
                reverse=True,
            )


        if not visual_ranked:

            return {

                "success":
                    False,

                "status":
                    "visual_ranking_failed",

                "reason":
                    (
                        "Visual ranking returned "
                        "no candidates."
                    ),

                "duration_filter":
                    duration_filter,
            }


        print(
            "Best final score:",
            visual_ranked[
                0
            ].get(
                "final_score"
            ),
        )


        # ==================================================
        # SELECT
        # ==================================================

        decision = (
            self.selector.decide(
                visual_ranked
            )
        )


        print()

        print(
            "Decision:",
            decision.get(
                "decision"
            ),
        )


        print(
            "Best score:",
            decision.get(
                "best_score"
            ),
        )


        print(
            "Second score:",
            decision.get(
                "second_score"
            ),
        )


        print(
            "Margin:",
            decision.get(
                "margin"
            ),
        )


        return {

            "success":
                True,

            "status":
                decision[
                    "decision"
                ],

            "candidates":
                ranked,

            "visual_ranking":
                visual_ranked,

            "decision":
                decision,

            "duration_filter":
                duration_filter,
        }


    # ==================================================
    # BUILD TECHNICAL FALLBACK QUEUE
    # ==================================================

    def _build_candidate_queue(
        self,
        result,
        decision_name,
    ):

        visual_ranked = result.get(
            "visual_ranking",
            [],
        )


        decision = result.get(
            "decision",
            {},
        )


        if not visual_ranked:

            return []


        if (
            decision_name
            == "auto_selected"
        ):

            primary = decision.get(
                "selected"
            )

        else:

            primary = visual_ranked[
                0
            ]


        queue = []

        seen = set()


        def add_candidate(
            candidate,
            force=False,
        ):

            if not isinstance(
                candidate,
                dict,
            ):

                return


            identity = (
                self._media_identity(
                    candidate
                )
            )


            if (
                identity is not None
                and identity in seen
            ):

                return


            final_score = (
                self._to_float(
                    candidate.get(
                        "final_score"
                    ),
                    default=0.0,
                )
            )


            if (
                not force
                and final_score
                < self.minimum_fallback_score
            ):

                return


            if identity is not None:

                seen.add(
                    identity
                )


            queue.append(
                candidate
            )


        # Primary candidate always tried first.

        add_candidate(
            primary,
            force=True,
        )


        # Other sufficiently strong candidates can be
        # technical fallbacks if the first file is invalid.

        for candidate in visual_ranked:

            add_candidate(
                candidate,
                force=False,
            )


        return queue


    # ==================================================
    # DOWNLOAD + FFPROBE + REAL DURATION CHECK
    # ==================================================

    def _download_and_validate(
        self,
        scene,
        candidate,
        stock,
    ):

        scene_id = scene[
            "scene_id"
        ]


        required_duration = (
            self._scene_duration(
                scene
            )
        )


        # ==================================================
        # PROVIDER METADATA CHECK AGAIN
        # ==================================================

        if self._is_video(
            candidate
        ):

            known_duration = (
                self._known_media_duration(
                    candidate
                )
            )


            if (
                known_duration is not None
                and (
                    known_duration
                    + self.duration_tolerance
                    < required_duration
                )
            ):

                reason = (

                    "Provider duration is too short: "

                    f"{known_duration:.3f}s < "

                    f"{required_duration:.3f}s"
                )


                self._record_rejection(
                    stock=stock,
                    media=candidate,
                    reason=reason,
                )


                return {

                    "success":
                        False,

                    "reason":
                        reason,
                }


        # ==================================================
        # DOWNLOAD
        # ==================================================

        print()

        print(
            "[DOWNLOAD] Trying media:",
            candidate.get(
                "media_id"
            ),
        )


        try:

            download_result = (
                self.downloader.download(
                    media=candidate,
                    scene_id=scene_id,
                )
            )


        except DownloadError as error:

            reason = (
                f"Download failed: {error}"
            )


            self._record_rejection(
                stock=stock,
                media=candidate,
                reason=reason,
            )


            print(
                "Rejected:",
                reason,
            )


            return {

                "success":
                    False,

                "reason":
                    reason,
            }


        print(
            "Download status:",
            download_result[
                "status"
            ],
        )


        print(
            "File:",
            download_result[
                "filename"
            ],
        )


        print(
            "Size:",
            download_result[
                "size"
            ],
            "bytes",
        )


        # ==================================================
        # FFPROBE VALIDATION
        # ==================================================

        print()

        print(
            "[VALIDATE] Validating media..."
        )


        try:

            validation = (
                self.validator.validate(
                    file_path=download_result[
                        "path"
                    ],
                    expected_type=candidate.get(
                        "media_type"
                    ),
                )
            )


        except MediaValidationError as error:

            reason = (
                f"Media validation failed: {error}"
            )


            self._record_rejection(
                stock=stock,
                media=candidate,
                reason=reason,
                download=download_result,
            )


            print(
                "Rejected:",
                reason,
            )


            return {

                "success":
                    False,

                "reason":
                    reason,

                "download":
                    download_result,
            }


        if not validation.get(
            "valid"
        ):

            reason = (
                "Media validator returned valid=False."
            )


            self._record_rejection(
                stock=stock,
                media=candidate,
                reason=reason,
                validation=validation,
                download=download_result,
            )


            print(
                "Rejected:",
                reason,
            )


            return {

                "success":
                    False,

                "reason":
                    reason,

                "validation":
                    validation,

                "download":
                    download_result,
            }


        # ==================================================
        # REAL VIDEO DURATION CHECK
        # ==================================================

        if self._is_video(
            candidate
        ):

            actual_duration = (
                self._to_float(
                    validation.get(
                        "duration"
                    ),
                    default=None,
                )
            )


            if (
                actual_duration is None
                or actual_duration <= 0
            ):

                reason = (

                    "FFprobe did not return "

                    "a valid video duration."
                )


                self._record_rejection(
                    stock=stock,
                    media=candidate,
                    reason=reason,
                    validation=validation,
                    download=download_result,
                )


                print(
                    "Rejected:",
                    reason,
                )


                return {

                    "success":
                        False,

                    "reason":
                        reason,

                    "validation":
                        validation,

                    "download":
                        download_result,
                }


            if (
                actual_duration
                + self.duration_tolerance
                < required_duration
            ):

                reason = (

                    "Actual video is too short: "

                    f"{actual_duration:.3f}s < "

                    f"{required_duration:.3f}s "

                    f"(tolerance "

                    f"{self.duration_tolerance:.3f}s)"
                )


                self._record_rejection(
                    stock=stock,
                    media=candidate,
                    reason=reason,
                    validation=validation,
                    download=download_result,
                )


                print()

                print(
                    "DURATION SAFETY: REJECTED"
                )

                print(
                    reason
                )


                return {

                    "success":
                        False,

                    "reason":
                        reason,

                    "validation":
                        validation,

                    "download":
                        download_result,
                }


        # ==================================================
        # SUCCESS
        # ==================================================

        print(
            "Validated:",
            validation.get(
                "valid"
            ),
        )


        print(
            "Duration:",
            validation.get(
                "duration"
            ),
        )


        print(
            "Resolution:",
            f"{validation.get('width')}x"
            f"{validation.get('height')}",
        )


        print(
            "FPS:",
            validation.get(
                "fps"
            ),
        )


        return {

            "success":
                True,

            "download":
                download_result,

            "validation":
                validation,

            "selected_media":
                candidate,
        }


    # ==================================================
    # SEARCH RETRY HELPER
    # ==================================================

    def _prepare_retry(
        self,
        scene,
        attempt,
    ):

        if (
            attempt
            >= self.max_search_retries
        ):

            return None


        retry_scene = (
            self._make_retry_scene(
                scene
            )
        )


        if retry_scene is None:

            return None


        retry_queries = (
            retry_scene[
                "search"
            ].get(
                "search_queries",
                [],
            )
        )


        print()

        print("=" * 70)

        print(
            "SEARCH RETRY REQUIRED"
        )

        print("=" * 70)


        print()

        print(
            "Retry queries:"
        )


        for query in retry_queries:

            print(
                "  -",
                query,
            )


        return retry_scene


    # ==================================================
    # RUN
    # ==================================================

    def run(
        self,
        scene,
    ):

        scene_id = scene[
            "scene_id"
        ]


        stock = scene[
            "stock"
        ]


        print()

        print("=" * 70)

        print(
            f"SCENE PIPELINE: {scene_id}"
        )

        print("=" * 70)


        print(
            "Review mode:",
            self.review_mode,
        )


        print(
            "Visual top N:",
            self.visual_top_n,
        )


        print(
            "Max search retries:",
            self.max_search_retries,
        )


        print(
            "Required duration:",
            round(
                self._scene_duration(
                    scene
                ),
                3,
            ),
            "s",
        )


        attempt = 0

        current_scene = scene

        search_history = []


        last_status = (
            "search_failed"
        )


        last_reason = None


        while (
            attempt
            <= self.max_search_retries
        ):

            result = (
                self._search_and_select(
                    current_scene,
                    attempt=attempt,
                    real_stock=stock,
                )
            )


            # ==================================================
            # SEARCH / RANK FAILURE
            # ==================================================

            if not result.get(
                "success"
            ):

                last_status = result.get(
                    "status",
                    "search_failed",
                )


                last_reason = result.get(
                    "reason"
                )


                search_history.append({

                    "attempt":
                        attempt + 1,

                    "status":
                        last_status,

                    "reason":
                        last_reason,
                })


                retry_scene = (
                    self._prepare_retry(
                        scene=scene,
                        attempt=attempt,
                    )
                )


                if retry_scene is not None:

                    current_scene = (
                        retry_scene
                    )

                    attempt += 1

                    continue


                stock[
                    "status"
                ] = last_status


                stock[
                    "search_history"
                ] = search_history


                return {

                    "success":
                        False,

                    "scene_id":
                        scene_id,

                    "status":
                        last_status,

                    "reason":
                        last_reason,
                }


            decision = result[
                "decision"
            ]


            decision_name = decision[
                "decision"
            ]


            duration_filter = result.get(
                "duration_filter",
                {},
            )


            history_entry = {

                "attempt":
                    attempt + 1,

                "decision":
                    decision_name,

                "best_score":
                    decision.get(
                        "best_score"
                    ),

                "second_score":
                    decision.get(
                        "second_score"
                    ),

                "margin":
                    decision.get(
                        "margin"
                    ),

                "duration_filter": {

                    "required_duration":
                        duration_filter.get(
                            "required_duration"
                        ),

                    "removed_short":
                        len(
                            duration_filter.get(
                                "removed_short",
                                [],
                            )
                        ),

                    "removed_previous":
                        len(
                            duration_filter.get(
                                "removed_previous",
                                [],
                            )
                        ),
                },
            }


            # ==================================================
            # SEARCH AGAIN
            # ==================================================

            if (
                decision_name
                == "search_again"
            ):

                history_entry[
                    "status"
                ] = "search_again"

                search_history.append(
                    history_entry
                )

                retry_scene = (
                    self._prepare_retry(
                        scene=scene,
                        attempt=attempt,
                    )
                )

                if retry_scene is not None:

                    current_scene = (
                        retry_scene
                    )

                    attempt += 1

                    continue

                # AUTO SEARCH FALLBACK V5
                if (
                    self.review_mode == "auto"
                    and
                    result.get(
                        "visual_ranking"
                    )
                ):

                    print()
                    print("=" * 70)
                    print("AUTO FALLBACK AFTER SEARCH RETRIES")
                    print("=" * 70)

                    print(
                        "Search threshold was not reached."
                    )

                    print(
                        "Using best available candidate in AUTO mode."
                    )

                    decision = dict(
                        decision
                    )

                    decision["original_decision"] = (
                        "search_again"
                    )

                    decision["decision"] = (
                        "needs_review"
                    )

                    decision["auto_fallback"] = (
                        "search_retries_exhausted"
                    )

                    decision["reason"] = (
                        str(
                            decision.get(
                                "reason",
                                "",
                            )
                        )
                        + " | AUTO fallback after "
                        + "search retries exhausted."
                    )

                    decision_name = "needs_review"

                    result["decision"] = decision

                    history_entry[
                        "status"
                    ] = "auto_fallback"

                    history_entry[
                        "auto_fallback"
                    ] = (
                        "search_retries_exhausted"
                    )

                    search_history[-1] = (
                        history_entry
                    )

                else:

                    stock[
                        "candidates"
                    ] = result[
                        "candidates"
                    ]

                    stock[
                        "visual_ranking"
                    ] = result[
                        "visual_ranking"
                    ]

                    stock[
                        "search_history"
                    ] = search_history

                    stock[
                        "selected_media"
                    ] = None

                    stock[
                        "status"
                    ] = "search_again"

                    return {

                        "success":
                            False,

                        "scene_id":
                            scene_id,

                        "status":
                            "search_again",

                        "decision":
                            decision,
                    }


            # ==================================================
            # SAFE MODE REVIEW
            # ==================================================

            if (
                decision_name
                == "needs_review"
                and self.review_mode
                == "safe"
            ):

                history_entry[
                    "status"
                ] = "needs_review"


                search_history.append(
                    history_entry
                )


                stock[
                    "candidates"
                ] = result[
                    "candidates"
                ]


                stock[
                    "visual_ranking"
                ] = result[
                    "visual_ranking"
                ]


                stock[
                    "search_history"
                ] = search_history


                stock[
                    "selected_media"
                ] = None


                stock[
                    "status"
                ] = "needs_review"


                stock[
                    "selection"
                ] = {

                    "decision":
                        decision_name,

                    "best_score":
                        decision.get(
                            "best_score"
                        ),

                    "second_score":
                        decision.get(
                            "second_score"
                        ),

                    "margin":
                        decision.get(
                            "margin"
                        ),

                    "reason":
                        decision.get(
                            "reason"
                        ),

                    "attempts":
                        len(
                            search_history
                        ),
                }


                print()

                print(
                    "Scene requires manual review."
                )


                return {

                    "success":
                        False,

                    "scene_id":
                        scene_id,

                    "status":
                        "needs_review",

                    "decision":
                        decision,
                }


            # ==================================================
            # UNKNOWN DECISION
            # ==================================================

            if decision_name not in (
                "auto_selected",
                "needs_review",
            ):

                stock[
                    "status"
                ] = "selection_failed"


                return {

                    "success":
                        False,

                    "scene_id":
                        scene_id,

                    "status":
                        "selection_failed",

                    "reason":
                        (
                            f"Unknown decision: "
                            f"{decision_name}"
                        ),
                }


            # ==================================================
            # CANDIDATE QUEUE
            # ==================================================

            queue = (
                self._build_candidate_queue(
                    result=result,
                    decision_name=decision_name,
                )
            )


            if not queue:

                history_entry[
                    "status"
                ] = "selection_failed"


                search_history.append(
                    history_entry
                )


                last_status = (
                    "selection_failed"
                )


                last_reason = (
                    "No usable candidate queue."
                )


            else:

                print()

                print(
                    "Technical candidate queue:",
                    len(
                        queue
                    ),
                )


                candidate_failures = []


                successful_media = None


                for (
                    queue_index,
                    candidate
                ) in enumerate(
                    queue,
                    start=1,
                ):

                    print()

                    print(
                        "-" * 70
                    )


                    print(
                        f"MEDIA TRY "
                        f"{queue_index}/"
                        f"{len(queue)}"
                    )


                    print(
                        "Media ID:",
                        candidate.get(
                            "media_id"
                        ),
                    )


                    print(
                        "Final score:",
                        candidate.get(
                            "final_score"
                        ),
                    )


                    print(
                        "Provider duration:",
                        candidate.get(
                            "duration"
                        ),
                    )


                    media_result = (
                        self._download_and_validate(
                            scene=scene,
                            candidate=candidate,
                            stock=stock,
                        )
                    )


                    if media_result.get(
                        "success"
                    ):

                        successful_media = (
                            media_result
                        )

                        break


                    candidate_failures.append({

                        "media_id":
                            candidate.get(
                                "media_id"
                            ),

                        "reason":
                            media_result.get(
                                "reason"
                            ),
                    })


                history_entry[
                    "candidate_failures"
                ] = candidate_failures


                # ==============================================
                # SUCCESS
                # ==============================================

                if successful_media is not None:

                    selected = (
                        successful_media[
                            "selected_media"
                        ]
                    )


                    download_result = (
                        successful_media[
                            "download"
                        ]
                    )


                    validation = (
                        successful_media[
                            "validation"
                        ]
                    )


                    history_entry[
                        "status"
                    ] = "validated"


                    search_history.append(
                        history_entry
                    )


                    stock[
                        "candidates"
                    ] = result[
                        "candidates"
                    ]


                    stock[
                        "visual_ranking"
                    ] = result[
                        "visual_ranking"
                    ]


                    stock[
                        "search_history"
                    ] = search_history


                    stock[
                        "selected_media"
                    ] = selected


                    stock[
                        "download"
                    ] = {

                        "status":
                            download_result[
                                "status"
                            ],

                        "path":
                            download_result[
                                "path"
                            ],

                        "filename":
                            download_result[
                                "filename"
                            ],

                        "size":
                            download_result[
                                "size"
                            ],
                    }


                    stock[
                        "validation"
                    ] = validation


                    stock[
                        "status"
                    ] = "validated"


                    selection = {

                        "decision":
                            decision_name,

                        "best_score":
                            decision.get(
                                "best_score"
                            ),

                        "second_score":
                            decision.get(
                                "second_score"
                            ),

                        "margin":
                            decision.get(
                                "margin"
                            ),

                        "reason":
                            decision.get(
                                "reason"
                            ),

                        "attempts":
                            len(
                                search_history
                            ),
                    }


                    if (
                        decision_name
                        == "needs_review"
                    ):

                        selection[
                            "override"
                        ] = (
                            "auto_review_override"
                        )


                    primary_identity = (
                        self._media_identity(
                            queue[
                                0
                            ]
                        )
                    )


                    selected_identity = (
                        self._media_identity(
                            selected
                        )
                    )


                    if (
                        selected_identity
                        != primary_identity
                    ):

                        selection[
                            "technical_fallback"
                        ] = True


                        selection[
                            "fallback_media_id"
                        ] = selected.get(
                            "media_id"
                        )


                    stock[
                        "selection"
                    ] = selection


                    print()

                    print("=" * 70)

                    print(
                        f"SCENE COMPLETE: "
                        f"{scene_id}"
                    )

                    print("=" * 70)


                    return {

                        "success":
                            True,

                        "scene_id":
                            scene_id,

                        "status":
                            "validated",

                        "selected_media":
                            selected,

                        "download":
                            download_result,

                        "validation":
                            validation,

                        "search_attempts":
                            len(
                                search_history
                            ),
                    }


                # ==============================================
                # ALL CANDIDATES FAILED
                # ==============================================

                history_entry[
                    "status"
                ] = (
                    "media_candidates_failed"
                )


                search_history.append(
                    history_entry
                )


                last_status = (
                    "media_candidates_failed"
                )


                last_reason = (

                    "All visual-ranked candidates "

                    "failed download, validation, "

                    "or duration safety."
                )


            # ==================================================
            # RETRY SEARCH AFTER TECHNICAL FAILURE
            # ==================================================

            retry_scene = (
                self._prepare_retry(
                    scene=scene,
                    attempt=attempt,
                )
            )


            if retry_scene is not None:

                current_scene = (
                    retry_scene
                )

                attempt += 1

                continue


            stock[
                "candidates"
            ] = result[
                "candidates"
            ]


            stock[
                "visual_ranking"
            ] = result[
                "visual_ranking"
            ]


            stock[
                "search_history"
            ] = search_history


            stock[
                "selected_media"
            ] = None


            stock[
                "status"
            ] = last_status


            return {

                "success":
                    False,

                "scene_id":
                    scene_id,

                "status":
                    last_status,

                "reason":
                    last_reason,
            }


        # ==================================================
        # FINAL FAILURE
        # ==================================================

        stock[
            "status"
        ] = last_status


        stock[
            "search_history"
        ] = search_history


        return {

            "success":
                False,

            "scene_id":
                scene_id,

            "status":
                last_status,

            "reason":
                last_reason,
        }
