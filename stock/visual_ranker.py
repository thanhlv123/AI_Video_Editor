import os
import json
import time
import socket
import urllib.request
import urllib.error


class VisualRankerError(Exception):
    pass


class VisualRanker:

    def __init__(
        self,
        model="gpt-6-luna",
        reasoning_effort="low",
        timeout=180,
        local_weight=0.30,
        visual_weight=0.70,
        max_retries=2,
        retry_delay=2,
    ):

        # ==================================================
        # API KEY
        # ==================================================

        self.api_key = os.getenv(
            "KIE_API_KEY"
        )


        if not self.api_key:

            raise VisualRankerError(
                "KIE_API_KEY is not set."
            )


        # ==================================================
        # SETTINGS
        # ==================================================

        self.model = model


        self.reasoning_effort = (
            reasoning_effort
        )


        self.timeout = int(
            timeout
        )


        self.local_weight = float(
            local_weight
        )


        self.visual_weight = float(
            visual_weight
        )


        self.max_retries = int(
            max_retries
        )


        self.retry_delay = float(
            retry_delay
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
    # RANK
    # ==================================================

    def rank(
        self,
        scene,
        candidates,
        top_n=5,
    ):

        candidates = candidates[
            :top_n
        ]


        if not candidates:

            return []


        # ==================================================
        # BUILD REQUEST
        # ==================================================

        payload = self._build_payload(
            scene,
            candidates,
        )


        # ==================================================
        # KIE REQUEST
        # ==================================================

        response_data = self._request(
            payload
        )


        # ==================================================
        # EXTRACT OUTPUT
        # ==================================================

        output_text = (
            self._extract_output_text(
                response_data
            )
        )


        if not output_text:

            raise VisualRankerError(
                "Kie returned no output text."
            )


        # ==================================================
        # PARSE JSON
        # ==================================================

        result = self._parse_json(
            output_text
        )


        rankings = result.get(
            "rankings",
            [],
        )


        visual_scores = {}


        for item in rankings:

            media_id = str(
                item.get(
                    "media_id",
                    "",
                )
            )


            try:

                score = float(
                    item.get(
                        "visual_score",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                score = 0.0


            score = max(
                0.0,
                min(
                    score,
                    1.0,
                ),
            )


            visual_scores[
                media_id
            ] = {

                "score":
                    score,

                "reason":
                    item.get(
                        "reason",
                        "",
                    ),
            }


        # ==================================================
        # MERGE LOCAL + VISUAL SCORES
        # ==================================================

        ranked = []


        for candidate in candidates:

            item = dict(
                candidate
            )


            media_id = str(
                item.get(
                    "media_id"
                )
            )


            try:

                local_score = float(
                    item.get(
                        "score",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                local_score = 0.0


            visual = visual_scores.get(
                media_id,
                {
                    "score":
                        0.0,

                    "reason":
                        "No visual score returned.",
                },
            )


            visual_score = (
                visual[
                    "score"
                ]
            )


            final_score = (

                local_score
                * self.local_weight

                +

                visual_score
                * self.visual_weight
            )


            item[
                "local_score"
            ] = round(
                local_score,
                3,
            )


            item[
                "visual_score"
            ] = round(
                visual_score,
                3,
            )


            item[
                "visual_reason"
            ] = visual[
                "reason"
            ]


            item[
                "final_score"
            ] = round(
                final_score,
                3,
            )


            ranked.append(
                item
            )


        ranked.sort(

            key=lambda item: item[
                "final_score"
            ],

            reverse=True,
        )


        return ranked


    # ==================================================
    # BUILD REQUEST
    # ==================================================

    def _build_payload(
        self,
        scene,
        candidates,
    ):

        analysis = scene.get(
            "analysis",
            {},
        )


        context = analysis.get(
            "context",
            "",
        )


        subject = analysis.get(
            "subject",
            "",
        )


        action = analysis.get(
            "action",
            "",
        )


        location = analysis.get(
            "location",
            "",
        )


        mood = analysis.get(
            "mood",
            "",
        )


        dialogue = scene.get(
            "dialogue",
            "",
        )


        prompt = f"""
You are ranking stock footage thumbnails for a video editing system.

Evaluate how well each candidate visually matches the scene.

SCENE

Narration:
{dialogue}

Context:
{context}

Subject:
{subject}

Action:
{action}

Location:
{location}

Mood:
{mood}

SCORING RULES

Give each candidate a visual_score from 0.0 to 1.0.

Consider:

1. Semantic match to the narration.
2. Visible subject.
3. Visible action.
4. Location/environment.
5. Mood and atmosphere.
6. Whether the image would make sense during this narration.
7. Avoid visually misleading footage.

Do not reward a candidate simply because its search keyword matches.

Judge the actual visible thumbnail.

Return ONLY JSON in this structure:

{{
  "rankings": [
    {{
      "media_id": "123",
      "visual_score": 0.95,
      "reason": "short explanation"
    }}
  ]
}}

Return one ranking for every candidate.
"""


        content = [

            {
                "type":
                    "input_text",

                "text":
                    prompt,
            }
        ]


        # ==================================================
        # ADD THUMBNAILS
        # ==================================================

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):

            media_id = str(
                candidate.get(
                    "media_id"
                )
            )


            thumbnail = candidate.get(
                "thumbnail_url"
            )


            content.append({

                "type":
                    "input_text",

                "text": (
                    f"Candidate {index} "
                    f"| media_id={media_id}"
                ),
            })


            if thumbnail:

                content.append({

                    "type":
                        "input_image",

                    "image_url":
                        thumbnail,
                })


        return {

            "model":
                self.model,

            "stream":
                False,

            "reasoning": {

                "effort":
                    self.reasoning_effort,
            },

            "input": [

                {
                    "role":
                        "user",

                    "content":
                        content,
                }
            ],
        }


    # ==================================================
    # TRANSIENT HTTP ERROR
    # ==================================================

    def _is_retryable_http_code(
        self,
        code,
    ):

        return code in {

            408,

            409,

            425,

            429,

            500,

            502,

            503,

            504,

            520,

            522,

            523,

            524,
        }


    # ==================================================
    # WAIT BEFORE RETRY
    # ==================================================

    def _sleep_before_retry(
        self,
        attempt_number,
    ):

        # attempt_number:
        #
        # first retry  -> 1 -> 2 seconds
        # second retry -> 2 -> 4 seconds

        delay = (

            self.retry_delay

            * (
                2
                ** (
                    attempt_number
                    - 1
                )
            )
        )


        print(
            f"[KIE VISUAL] "
            f"Retrying in "
            f"{delay:.1f}s..."
        )


        time.sleep(
            delay
        )


    # ==================================================
    # ONE HTTP REQUEST
    # ==================================================

    def _request_once(
        self,
        payload,
    ):

        body = json.dumps(
            payload
        ).encode(
            "utf-8"
        )


        request = urllib.request.Request(

            url=self.url,

            data=body,

            method="POST",

            headers={

                "Authorization": (
                    f"Bearer "
                    f"{self.api_key}"
                ),

                "Content-Type":
                    "application/json",
            },
        )


        with urllib.request.urlopen(
            request,
            timeout=self.timeout,
        ) as response:

            response_body = (
                response
                .read()
                .decode(
                    "utf-8"
                )
            )


            try:

                return json.loads(
                    response_body
                )

            except json.JSONDecodeError as error:

                raise VisualRankerError(
                    "Kie HTTP response "
                    "was not valid JSON."
                ) from error


    # ==================================================
    # HTTP REQUEST WITH RETRY
    # ==================================================

    def _request(
        self,
        payload,
    ):

        total_attempts = (
            self.max_retries
            + 1
        )


        last_error = None


        for attempt_index in range(
            total_attempts
        ):

            attempt_number = (
                attempt_index
                + 1
            )


            print(
                f"[KIE VISUAL] "
                f"Request attempt "
                f"{attempt_number}/"
                f"{total_attempts}"
            )


            try:

                response = (
                    self._request_once(
                        payload
                    )
                )


                print(
                    f"[KIE VISUAL] "
                    f"Request succeeded "
                    f"on attempt "
                    f"{attempt_number}"
                )


                return response


            # ==================================================
            # HTTP ERROR
            # ==================================================

            except urllib.error.HTTPError as error:

                try:

                    error_body = (
                        error
                        .read()
                        .decode(
                            "utf-8",
                            errors="replace",
                        )
                    )

                except Exception:

                    error_body = (
                        "<unable to read "
                        "error response>"
                    )


                message = (

                    f"Kie HTTP "
                    f"{error.code}: "
                    f"{error_body}"
                )


                last_error = (
                    VisualRankerError(
                        message
                    )
                )


                print(
                    f"[KIE VISUAL] "
                    f"HTTP error "
                    f"{error.code}"
                )


                # ------------------------------------------
                # NON-RETRYABLE HTTP ERROR
                # ------------------------------------------

                if not self._is_retryable_http_code(
                    error.code
                ):

                    raise last_error from error


                # ------------------------------------------
                # RETRIES EXHAUSTED
                # ------------------------------------------

                if (
                    attempt_index
                    >= self.max_retries
                ):

                    raise last_error from error


                self._sleep_before_retry(
                    attempt_number
                )


                continue


            # ==================================================
            # TIMEOUT
            # ==================================================

            except (
                TimeoutError,
                socket.timeout,
            ) as error:

                message = (

                    "Kie visual request "
                    f"timed out: {error}"
                )


                last_error = (
                    VisualRankerError(
                        message
                    )
                )


                print(
                    "[KIE VISUAL] "
                    "Request timed out."
                )


                if (
                    attempt_index
                    >= self.max_retries
                ):

                    raise last_error from error


                self._sleep_before_retry(
                    attempt_number
                )


                continue


            # ==================================================
            # URL / NETWORK ERROR
            # ==================================================

            except urllib.error.URLError as error:

                message = (

                    "Kie visual network "
                    f"error: {error}"
                )


                last_error = (
                    VisualRankerError(
                        message
                    )
                )


                print(
                    "[KIE VISUAL] "
                    "Network error."
                )


                if (
                    attempt_index
                    >= self.max_retries
                ):

                    raise last_error from error


                self._sleep_before_retry(
                    attempt_number
                )


                continue


            # ==================================================
            # OTHER EXCEPTION
            # ==================================================

            except VisualRankerError:

                raise


            except Exception as error:

                message = (

                    "Kie visual request "
                    f"failed: {error}"
                )


                last_error = (
                    VisualRankerError(
                        message
                    )
                )


                print(
                    "[KIE VISUAL] "
                    f"Unexpected request "
                    f"error: {error}"
                )


                if (
                    attempt_index
                    >= self.max_retries
                ):

                    raise last_error from error


                self._sleep_before_retry(
                    attempt_number
                )


                continue


        # ==================================================
        # SAFETY FALLBACK
        # ==================================================

        if last_error is not None:

            raise last_error


        raise VisualRankerError(
            "Kie visual request failed "
            "for an unknown reason."
        )


    # ==================================================
    # EXTRACT OUTPUT
    # ==================================================

    def _extract_output_text(
        self,
        response_data,
    ):

        texts = []


        for item in response_data.get(
            "output",
            [],
        ):

            if item.get(
                "type"
            ) != "message":

                continue


            for content in item.get(
                "content",
                [],
            ):

                if (
                    content.get(
                        "type"
                    )
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


    # ==================================================
    # PARSE JSON
    # ==================================================

    def _parse_json(
        self,
        text,
    ):

        text = text.strip()


        if text.startswith(
            "```json"
        ):

            text = text[
                7:
            ]


        elif text.startswith(
            "```"
        ):

            text = text[
                3:
            ]


        if text.endswith(
            "```"
        ):

            text = text[
                :-3
            ]


        text = text.strip()


        try:

            data = json.loads(
                text
            )

        except json.JSONDecodeError as error:

            raise VisualRankerError(

                "Kie returned invalid JSON.\n"

                f"{text}"

            ) from error


        if not isinstance(
            data,
            dict,
        ):

            raise VisualRankerError(
                "Visual ranking response "
                "must be a JSON object."
            )


        return data