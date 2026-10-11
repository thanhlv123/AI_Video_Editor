class MediaSelector:

    def __init__(
        self,
        auto_threshold=0.85,
        margin_threshold=0.08,
        minimum_threshold=0.75
    ):

        self.auto_threshold = (
            auto_threshold
        )

        self.margin_threshold = (
            margin_threshold
        )

        self.minimum_threshold = (
            minimum_threshold
        )


    # ==================================================
    # DECIDE
    # ==================================================

    def decide(
        self,
        ranked
    ):

        if not ranked:

            return {
                "decision": "search_again",
                "selected": None,
                "best_score": 0.0,
                "second_score": 0.0,
                "margin": 0.0,
                "reason": (
                    "No candidates available."
                )
            }


        best = ranked[0]


        best_score = float(
            best.get(
                "final_score",
                0
            )
        )


        # ----------------------------------------------
        # SECOND CANDIDATE
        # ----------------------------------------------

        if len(ranked) > 1:

            second_score = float(
                ranked[1].get(
                    "final_score",
                    0
                )
            )

        else:

            second_score = 0.0


        margin = (
            best_score
            - second_score
        )


        # ==================================================
        # LOW QUALITY
        # ==================================================

        if (
            best_score
            < self.minimum_threshold
        ):

            return {

                "decision": (
                    "search_again"
                ),

                "selected": None,

                "best_score": round(
                    best_score,
                    3
                ),

                "second_score": round(
                    second_score,
                    3
                ),

                "margin": round(
                    margin,
                    3
                ),

                "reason": (
                    "Best candidate score "
                    "is below minimum threshold."
                )
            }


        # ==================================================
        # AUTO SELECT
        # ==================================================

        if (
            best_score
            >= self.auto_threshold

            and

            margin
            >= self.margin_threshold
        ):

            return {

                "decision": (
                    "auto_selected"
                ),

                "selected": best,

                "best_score": round(
                    best_score,
                    3
                ),

                "second_score": round(
                    second_score,
                    3
                ),

                "margin": round(
                    margin,
                    3
                ),

                "reason": (
                    "Best candidate passed "
                    "score and confidence margin."
                )
            }


        # ==================================================
        # HUMAN REVIEW
        # ==================================================

        return {

            "decision": (
                "needs_review"
            ),

            "selected": None,

            "best_score": round(
                best_score,
                3
            ),

            "second_score": round(
                second_score,
                3
            ),

            "margin": round(
                margin,
                3
            ),

            "reason": (
                "Candidates are usable, "
                "but confidence is not high "
                "enough for automatic selection."
            )
        }