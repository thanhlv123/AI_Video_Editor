import re


class MediaRanker:

    def __init__(
        self,
        target_width=1920,
        target_height=1080
    ):

        self.target_width = target_width
        self.target_height = target_height


    # ==================================================
    # RANK
    # ==================================================

    def rank(
        self,
        scene,
        candidates
    ):

        ranked = []


        for candidate in candidates:

            score_data = self._score(
                scene,
                candidate
            )


            item = dict(
                candidate
            )


            item["score"] = round(
                score_data["total"],
                3
            )


            item["score_details"] = (
                score_data
            )


            ranked.append(
                item
            )


        ranked.sort(

            key=lambda item: item[
                "score"
            ],

            reverse=True
        )


        return ranked


    # ==================================================
    # SCORE
    # ==================================================

    def _score(
        self,
        scene,
        candidate
    ):

        keyword_score = (
            self._keyword_score(
                scene,
                candidate
            )
        )


        duration_score = (
            self._duration_score(
                scene,
                candidate
            )
        )


        resolution_score = (
            self._resolution_score(
                candidate
            )
        )


        orientation_score = (
            self._orientation_score(
                candidate
            )
        )


        media_type_score = (
            self._media_type_score(
                scene,
                candidate
            )
        )


        # ----------------------------------------------
        # WEIGHTS
        # ----------------------------------------------

        total = (

            keyword_score * 0.45

            +

            duration_score * 0.20

            +

            resolution_score * 0.15

            +

            orientation_score * 0.10

            +

            media_type_score * 0.10
        )


        return {

            "keyword": round(
                keyword_score,
                3
            ),

            "duration": round(
                duration_score,
                3
            ),

            "resolution": round(
                resolution_score,
                3
            ),

            "orientation": round(
                orientation_score,
                3
            ),

            "media_type": round(
                media_type_score,
                3
            ),

            "total": round(
                total,
                3
            )
        }


    # ==================================================
    # KEYWORD
    # ==================================================

    def _keyword_score(
        self,
        scene,
        candidate
    ):

        primary = (
            scene["search"]
            .get(
                "primary_keyword",
                ""
            )
        )


        alternatives = (
            scene["search"]
            .get(
                "keywords",
                []
            )
        )


        matched_query = (
            candidate
            .get(
                "matched_query",
                ""
            )
        )


        title = (
            candidate
            .get(
                "title",
                ""
            )
        )


        primary_tokens = (
            self._tokens(
                primary
            )
        )


        query_tokens = (
            self._tokens(
                matched_query
            )
        )


        title_tokens = (
            self._tokens(
                title
            )
        )


        # ----------------------------------------------
        # Query similarity to primary keyword
        # ----------------------------------------------

        primary_similarity = (
            self._token_overlap(
                primary_tokens,
                query_tokens
            )
        )


        # ----------------------------------------------
        # Title relevance
        # ----------------------------------------------

        title_similarity = (
            self._token_overlap(
                primary_tokens,
                title_tokens
            )
        )


        # ----------------------------------------------
        # Was result found by one of AI keywords?
        # ----------------------------------------------

        known_queries = [
            primary.lower().strip()
        ]


        known_queries.extend(

            str(item)
            .lower()
            .strip()

            for item in alternatives
        )


        ai_query_bonus = 0.0


        if (
            matched_query
            .lower()
            .strip()
            in known_queries
        ):

            ai_query_bonus = 1.0


        score = (

            primary_similarity * 0.60

            +

            title_similarity * 0.20

            +

            ai_query_bonus * 0.20
        )


        return min(
            score,
            1.0
        )


    # ==================================================
    # DURATION
    # ==================================================

    def _duration_score(
        self,
        scene,
        candidate
    ):

        media_type = (
            candidate.get(
                "media_type"
            )
        )


        if media_type == "image":

            return 1.0


        candidate_duration = (
            candidate.get(
                "duration"
            )
        )


        scene_duration = (
            scene.get(
                "duration",
                0
            )
        )


        if not candidate_duration:

            return 0.0


        if candidate_duration < scene_duration:

            return 0.25


        # Enough footage for scene

        extra = (
            candidate_duration
            - scene_duration
        )


        # Best when footage is not excessively long.

        if extra <= 10:

            return 1.0


        if extra <= 30:

            return 0.85


        if extra <= 60:

            return 0.70


        return 0.55


    # ==================================================
    # RESOLUTION
    # ==================================================

    def _resolution_score(
        self,
        candidate
    ):

        width = candidate.get(
            "width"
        )

        height = candidate.get(
            "height"
        )


        if not width or not height:

            return 0.0


        if (
            width >= self.target_width
            and
            height >= self.target_height
        ):

            return 1.0


        if (
            width >= 1280
            and
            height >= 720
        ):

            return 0.80


        if (
            width >= 854
            and
            height >= 480
        ):

            return 0.55


        return 0.25


    # ==================================================
    # ORIENTATION
    # ==================================================

    def _orientation_score(
        self,
        candidate
    ):

        width = candidate.get(
            "width"
        )

        height = candidate.get(
            "height"
        )


        if not width or not height:

            return 0.0


        if width > height:

            return 1.0


        if width == height:

            return 0.60


        return 0.25


    # ==================================================
    # MEDIA TYPE
    # ==================================================

    def _media_type_score(
        self,
        scene,
        candidate
    ):

        preferred = (

            scene
            .get(
                "stock",
                {}
            )
            .get(
                "preferred_type",
                "video"
            )
        )


        media_type = candidate.get(
            "media_type"
        )


        if preferred == "either":

            return 1.0


        if media_type == preferred:

            return 1.0


        return 0.30


    # ==================================================
    # TOKENIZE
    # ==================================================

    def _tokens(
        self,
        text
    ):

        if not text:

            return set()


        words = re.findall(
            r"[a-zA-Z0-9]+",
            text.lower()
        )


        stop_words = {

            "the",
            "a",
            "an",
            "of",
            "in",
            "on",
            "at",
            "to",
            "and",
            "with",
            "for",
            "video",
            "pexels"
        }


        return {

            word

            for word in words

            if (
                word not in stop_words
                and
                len(word) > 1
            )
        }


    # ==================================================
    # TOKEN OVERLAP
    # ==================================================

    def _token_overlap(
        self,
        reference,
        candidate
    ):

        if not reference:

            return 0.0


        common = (
            reference
            &
            candidate
        )


        return (
            len(common)
            /
            len(reference)
        )