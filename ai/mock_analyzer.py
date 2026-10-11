from ai.scene_schema import (
    SceneAnalysis,
    SceneContentAnalysis,
    SceneSearchData,
    SceneMediaData
)

from ai.scene_validator import (
    SceneAnalysisValidator
)


class MockSceneAnalyzer:

    def __init__(self):

        self.validator = (
            SceneAnalysisValidator()
        )


    def analyze(self, scene):

        text = scene.text.lower()


        # ==============================================
        # DEFAULT VALUES
        # ==============================================

        context = (
            "Everyday life in rural Vietnam"
        )

        subject = (
            "rural Vietnamese life"
        )

        action = (
            "daily activity"
        )

        location = (
            "Vietnam countryside"
        )

        mood = "peaceful"

        shot = "wide"

        motion = "slow"

        preferred_type = "video"


        primary_keyword = (
            "rural Vietnam daily life"
        )


        keywords = [
            "rural Vietnam daily life",
            "Vietnam countryside",
            "Vietnam village life"
        ]


        avoid = [
            "modern city",
            "office",
            "western countryside"
        ]


        # ==============================================
        # SIMPLE RULE ANALYSIS
        # ==============================================

        if (
            "morning" in text
            or "early" in text
        ):

            context = (
                "Early morning life "
                "in rural Vietnam"
            )

            action = (
                "starting the day"
            )

            mood = "peaceful"

            primary_keyword = (
                "rural Vietnam morning"
            )

            keywords = [
                "rural Vietnam morning",
                "Vietnam countryside morning",
                "Vietnam village sunrise",
                "rural village morning"
            ]


        if (
            "field" in text
            or "work" in text
        ):

            context = (
                "Rural Vietnamese people "
                "working outdoors"
            )

            subject = (
                "Vietnamese rural workers"
            )

            action = (
                "working in the countryside"
            )

            primary_keyword = (
                "Vietnam rural workers"
            )

            keywords = [
                "Vietnam rural workers",
                "Vietnam farmer working",
                "Vietnam countryside work",
                "Vietnam rice field farmer"
            ]


        if (
            "animal" in text
            or "animals" in text
        ):

            context = (
                "Rural family raising "
                "animals near home"
            )

            subject = (
                "Vietnamese rural family"
            )

            action = (
                "raising farm animals"
            )

            shot = "medium"

            primary_keyword = (
                "Vietnam rural farm animals"
            )

            keywords = [
                "Vietnam rural farm animals",
                "Vietnam village animals",
                "Vietnam countryside farm",
                "rural family animals"
            ]


        # ==============================================
        # BUILD RESULT
        # ==============================================

        result = SceneAnalysis(

            scene_id=scene.id,

            start=scene.start,

            end=scene.end,

            duration=scene.duration,

            dialogue=scene.text,

            analysis=SceneContentAnalysis(

                context=context,

                subject=subject,

                action=action,

                location=location,

                mood=mood,

                shot=shot,

                motion=motion
            ),

            search=SceneSearchData(

                primary_keyword=(
                    primary_keyword
                ),

                keywords=keywords,

                avoid=avoid
            ),

            media=SceneMediaData(

                preferred_type=(
                    preferred_type
                ),

                selected=None
            )
        )


        # ==============================================
        # VALIDATE
        # ==============================================

        self.validator.validate(
            result
        )


        return result