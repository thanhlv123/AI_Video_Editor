from ai.providers.base import (
    BaseAIProvider
)


class MockAIProvider(BaseAIProvider):

    def analyze_scene(
        self,
        scene,
        system_prompt
    ):

        text = scene.text.lower()


        context = (
            "Everyday life in rural Vietnam"
        )

        subject = (
            "Vietnamese rural life"
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
        # SIMPLE MOCK RULES
        # ==============================================

        if (
            "morning" in text
            or "early" in text
        ):

            context = (
                "Early morning life "
                "in rural Vietnam"
            )

            action = "starting the day"

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


        return {

            "context": context,

            "subject": subject,

            "action": action,

            "location": location,

            "mood": mood,

            "shot": shot,

            "motion": motion,

            "primary_keyword": (
                primary_keyword
            ),

            "keywords": keywords,

            "avoid": avoid,

            "preferred_type": (
                preferred_type
            )
        }