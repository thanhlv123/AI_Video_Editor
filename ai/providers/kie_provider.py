import os
import json
import time
import socket
import urllib.request
import urllib.error

from ai.providers.base import (
    BaseAIProvider,
    AIProviderError
)


class KieAIProvider(BaseAIProvider):

    def __init__(
        self,
        model="gpt-6-luna",
        reasoning_effort="low",
        timeout=180,
        max_retries=2,
        retry_delay=2
    ):

        self.api_key = os.getenv(
            "KIE_API_KEY"
        )

        if not self.api_key:

            raise AIProviderError(
                "KIE_API_KEY is not set."
            )

        self.model = model

        self.reasoning_effort = (
            reasoning_effort
        )

        self.timeout = int(
            timeout
        )

        self.max_retries = int(
            max_retries
        )

        self.retry_delay = float(
            retry_delay
        )

        if self.timeout <= 0:

            raise ValueError(
                "timeout must be greater than 0"
            )

        if self.max_retries < 0:

            raise ValueError(
                "max_retries cannot be negative"
            )

        if self.retry_delay < 0:

            raise ValueError(
                "retry_delay cannot be negative"
            )

        self.url = (
            "https://api.kie.ai"
            "/openai/v1/responses"
        )


    # ==================================================
    # ANALYZE SCENE
    # ==================================================

    def analyze_scene(
        self,
        scene,
        system_prompt
    ):

        user_prompt = f"""
Analyze this narration scene for stock-footage selection.

SCENE INFORMATION

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


Return ONLY a valid JSON object.

The JSON object MUST contain exactly these fields:

{{
    "context": "string",
    "subject": "string",
    "action": "string",
    "location": "string",
    "mood": "string",
    "shot": "wide | medium | close_up | aerial | detail | any",
    "motion": "static | slow | normal | fast | any",
    "primary_keyword": "string",
    "keywords": [
        "keyword 1",
        "keyword 2",
        "keyword 3"
    ],
    "avoid": [
        "concept 1",
        "concept 2"
    ],
    "preferred_type": "video | image | either"
}}

RULES:

1. Think visually.

2. The result will be used to search stock-footage websites.

3. primary_keyword should normally contain about 2-6 useful search words.

4. keywords should contain 3-6 useful stock-search phrases.

5. Use concrete visual search terms.

6. Do not simply copy the narration.

7. Do not invent unsupported people, locations, landmarks or events.

8. Prefer video unless an image would clearly work better.

9. Do not include Markdown.

10. Do not include ```json.

11. Return the JSON object only.
"""

        payload = {

            "model": self.model,

            "stream": False,

            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt
                        }
                    ]
                },

                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt
                        }
                    ]
                }
            ],

            "reasoning": {
                "effort": (
                    self.reasoning_effort
                )
            }
        }

        # ==============================================
        # SEND REQUEST WITH RETRY
        # ==============================================

        response_data = self._send_request(
            payload
        )

        # ==============================================
        # EXTRACT OUTPUT TEXT
        # ==============================================

        output_text = self._extract_output_text(
            response_data
        )

        if not output_text:

            raise AIProviderError(
                "Kie returned no output text."
            )

        # ==============================================
        # CLEAN RESPONSE
        # ==============================================

        output_text = (
            output_text.strip()
        )

        if output_text.startswith(
            "```json"
        ):

            output_text = (
                output_text[7:]
            )

        elif output_text.startswith(
            "```"
        ):

            output_text = (
                output_text[3:]
            )

        if output_text.endswith(
            "```"
        ):

            output_text = (
                output_text[:-3]
            )

        output_text = (
            output_text.strip()
        )

        # ==============================================
        # PARSE JSON
        # ==============================================

        try:

            result = json.loads(
                output_text
            )

        except json.JSONDecodeError as error:

            raise AIProviderError(

                "Kie returned invalid JSON.\n\n"

                f"Raw output:\n"
                f"{output_text}"

            ) from error

        if not isinstance(
            result,
            dict
        ):

            raise AIProviderError(
                "Kie response JSON "
                "must be an object."
            )

        return result


    # ==================================================
    # SEND REQUEST
    # ==================================================

    def _send_request(
        self,
        payload
    ):

        body = json.dumps(
            payload
        ).encode(
            "utf-8"
        )

        total_attempts = (
            self.max_retries + 1
        )

        last_error = None

        for attempt in range(
            1,
            total_attempts + 1
        ):

            print(
                f"[KIE] Request attempt "
                f"{attempt}/{total_attempts}"
            )

            # Create a fresh Request for each attempt.
            request = urllib.request.Request(

                url=self.url,

                data=body,

                method="POST",

                headers={
                    "Authorization": (
                        f"Bearer {self.api_key}"
                    ),

                    "Content-Type": (
                        "application/json"
                    )
                }
            )

            try:

                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout
                ) as response:

                    response_body = (
                        response
                        .read()
                        .decode(
                            "utf-8",
                            errors="replace"
                        )
                    )

                response_data = json.loads(
                    response_body
                )

                print(
                    f"[KIE] Request succeeded "
                    f"on attempt {attempt}"
                )

                return response_data

            # ==========================================
            # HTTP ERROR
            # ==========================================

            except urllib.error.HTTPError as error:

                error_body = (
                    error
                    .read()
                    .decode(
                        "utf-8",
                        errors="replace"
                    )
                )

                # --------------------------------------
                # RETRY TEMPORARY HTTP ERRORS
                # --------------------------------------

                if error.code in (
                    408,
                    429,
                    500,
                    502,
                    503,
                    504
                ):

                    last_error = error

                    print(
                        f"[KIE] Temporary HTTP "
                        f"error {error.code}"
                    )

                    if attempt < total_attempts:

                        self._wait_before_retry(
                            attempt
                        )

                        continue

                # --------------------------------------
                # DO NOT RETRY PERMANENT HTTP ERRORS
                # --------------------------------------

                raise AIProviderError(
                    f"Kie HTTP {error.code}: "
                    f"{error_body}"
                ) from error

            # ==========================================
            # URL ERROR
            # ==========================================

            except urllib.error.URLError as error:

                last_error = error

                reason = getattr(
                    error,
                    "reason",
                    error
                )

                print(
                    "[KIE] URL/network error:",
                    reason
                )

                if attempt < total_attempts:

                    self._wait_before_retry(
                        attempt
                    )

                    continue

            # ==========================================
            # TIMEOUT
            # ==========================================

            except (
                TimeoutError,
                socket.timeout
            ) as error:

                last_error = error

                print(
                    "[KIE] Request timed out."
                )

                if attempt < total_attempts:

                    self._wait_before_retry(
                        attempt
                    )

                    continue

            # ==========================================
            # INVALID RESPONSE JSON
            # ==========================================

            except json.JSONDecodeError as error:

                raise AIProviderError(
                    "Kie returned invalid "
                    "HTTP response JSON."
                ) from error

            # ==========================================
            # OTHER ERROR
            # ==========================================

            except Exception as error:

                last_error = error

                print(
                    "[KIE] Unexpected request error:",
                    error
                )

                if attempt < total_attempts:

                    self._wait_before_retry(
                        attempt
                    )

                    continue

        # ==============================================
        # ALL RETRIES FAILED
        # ==============================================

        raise AIProviderError(
            "Kie request failed after "
            f"{total_attempts} attempts: "
            f"{last_error}"
        ) from last_error


    # ==================================================
    # RETRY WAIT
    # ==================================================

    def _wait_before_retry(
        self,
        attempt
    ):

        # Exponential backoff:
        #
        # retry 1 -> 2 seconds
        # retry 2 -> 4 seconds
        #
        # when retry_delay = 2

        delay = (
            self.retry_delay
            * (2 ** (attempt - 1))
        )

        print(
            f"[KIE] Retrying in "
            f"{delay:g} seconds..."
        )

        time.sleep(
            delay
        )


    # ==================================================
    # EXTRACT RESPONSES API OUTPUT
    # ==================================================

    def _extract_output_text(
        self,
        response_data
    ):

        texts = []

        for item in response_data.get(
            "output",
            []
        ):

            if item.get(
                "type"
            ) != "message":

                continue

            for content in item.get(
                "content",
                []
            ):

                if (
                    content.get("type")
                    == "output_text"
                ):

                    text = content.get(
                        "text"
                    )

                    if text:

                        texts.append(
                            text
                        )

        if not texts:

            return None

        return "\n".join(
            texts
        )