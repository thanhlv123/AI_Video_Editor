import os
from enum import Enum

from openai import OpenAI
from pydantic import BaseModel

from ai.providers.base import (
    BaseAIProvider,
    AIProviderError
)


class Shot(str, Enum):
    wide = "wide"
    medium = "medium"
    close_up = "close_up"
    aerial = "aerial"
    detail = "detail"
    any = "any"


class Motion(str, Enum):
    static = "static"
    slow = "slow"
    normal = "normal"
    fast = "fast"
    any = "any"


class MediaType(str, Enum):
    video = "video"
    image = "image"
    either = "either"


class OpenAISceneResult(BaseModel):

    context: str
    subject: str
    action: str
    location: str
    mood: str

    shot: Shot
    motion: Motion

    primary_keyword: str

    keywords: list[str]
    avoid: list[str]

    preferred_type: MediaType


class OpenAIProvider(BaseAIProvider):

    def __init__(
        self,
        model="gpt-6-astra"
    ):

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:

            raise AIProviderError(
                "OPENAI_API_KEY is not set."
            )

        self.client = OpenAI(
            api_key=api_key
        )

        self.model = model


    def analyze_scene(
        self,
        scene,
        system_prompt
    ):

        user_prompt = f"""
Analyze this narration scene for stock-media search.

Scene ID:
{scene.id}

Start:
{scene.start}

End:
{scene.end}

Duration:
{scene.duration}

Narration:
{scene.text}

Requirements:

The search keywords must describe visible footage
that could realistically be found on stock-media sites.

Prefer concrete visual phrases.

The primary keyword should usually contain
roughly 2 to 6 useful search words.

Do not simply repeat the narration.

Do not invent a specific person, landmark,
event, country, or activity unless supported
by the narration.

Return the most useful visual interpretation
for editing this scene.
"""

        try:

            response = (
                self.client.responses.parse(

                    model=self.model,

                    input=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],

                    text_format=(
                        OpenAISceneResult
                    )
                )
            )


            result = (
                response.output_parsed
            )


            if result is None:

                raise AIProviderError(
                    "OpenAI returned no "
                    "parsed scene analysis."
                )


            data = result.model_dump()


            # Convert Enum objects to strings.
            data["shot"] = (
                result.shot.value
            )

            data["motion"] = (
                result.motion.value
            )

            data["preferred_type"] = (
                result.preferred_type.value
            )


            return data


        except AIProviderError:
            raise


        except Exception as error:

            raise AIProviderError(
                f"OpenAI analysis failed: "
                f"{error}"
            ) from error