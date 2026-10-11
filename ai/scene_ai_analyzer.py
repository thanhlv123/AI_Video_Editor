from ai.scene_schema import (
    SceneAnalysis,
    SceneContentAnalysis,
    SceneSearchData,
    SceneMediaData
)

from ai.scene_validator import (
    SceneAnalysisValidator
)


class SceneAIAnalyzer:

    SYSTEM_PROMPT = """
You are a video scene analysis engine.

Analyze narration for stock-media selection.

Return structured information describing:

- visual context
- main subject
- visible action
- location
- mood
- camera shot
- motion
- stock-footage search keywords
- concepts that should be avoided
- preferred media type

Search keywords should be concrete,
visual, concise, and suitable for
stock-footage search engines.

Do not invent people, places or events
that are unsupported by the narration.
"""


    def __init__(
        self,
        provider
    ):

        self.provider = provider

        self.validator = (
            SceneAnalysisValidator()
        )


    def analyze(
        self,
        scene
    ):

        raw = (
            self.provider.analyze_scene(
                scene=scene,
                system_prompt=self.SYSTEM_PROMPT
            )
        )


        if not isinstance(
            raw,
            dict
        ):

            raise ValueError(
                "AI provider must return "
                "a dictionary."
            )


        result = SceneAnalysis(

            scene_id=scene.id,

            start=scene.start,

            end=scene.end,

            duration=scene.duration,

            dialogue=scene.text,


            analysis=SceneContentAnalysis(

                context=self._required(
                    raw,
                    "context"
                ),

                subject=self._required(
                    raw,
                    "subject"
                ),

                action=self._required(
                    raw,
                    "action"
                ),

                location=self._required(
                    raw,
                    "location"
                ),

                mood=self._required(
                    raw,
                    "mood"
                ),

                shot=self._required(
                    raw,
                    "shot"
                ),

                motion=self._required(
                    raw,
                    "motion"
                )
            ),


            search=SceneSearchData(

                primary_keyword=(
                    self._required(
                        raw,
                        "primary_keyword"
                    )
                ),

                keywords=raw.get(
                    "keywords",
                    []
                ),

                avoid=raw.get(
                    "avoid",
                    []
                )
            ),


            media=SceneMediaData(

                preferred_type=raw.get(
                    "preferred_type",
                    "video"
                ),

                selected=None
            )
        )


        self.validator.validate(
            result
        )


        return result


    def _required(
        self,
        data,
        key
    ):

        value = data.get(
            key
        )


        if value is None:

            raise ValueError(
                f"AI response missing "
                f"required field: {key}"
            )


        if (
            isinstance(value, str)
            and not value.strip()
        ):

            raise ValueError(
                f"AI response contains "
                f"empty field: {key}"
            )


        return value