import os
import json
import urllib.request
import urllib.error


print("=" * 70)
print("AI VIDEO EDITOR")
print("KIE.AI GPT-6-LUNA TEST")
print("=" * 70)


api_key = os.getenv("KIE_API_KEY")

if not api_key:
    raise RuntimeError(
        "KIE_API_KEY is not set."
    )


# ==================================================
# ENDPOINT
# ==================================================

url = (
    "https://api.kie.ai"
    "/openai/v1/responses"
)


# ==================================================
# VERY SMALL TEST REQUEST
# ==================================================

payload = {

    "model": "gpt-6-luna",

    "stream": False,

    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "Reply with exactly this text "
                        "and nothing else: KIE_OK"
                    )
                }
            ]
        }
    ],

    "reasoning": {
        "effort": "low"
    }
}


body = json.dumps(
    payload
).encode("utf-8")


request = urllib.request.Request(

    url=url,

    data=body,

    method="POST",

    headers={
        "Authorization": (
            f"Bearer {api_key}"
        ),

        "Content-Type": (
            "application/json"
        )
    }
)


print()
print("Model: gpt-6-luna")
print("Reasoning: low")
print("Sending small test request...")


# ==================================================
# REQUEST
# ==================================================

try:

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        response_text = (
            response
            .read()
            .decode("utf-8")
        )

        data = json.loads(
            response_text
        )


        print()
        print("=" * 70)
        print("KIE RESPONSE")
        print("=" * 70)

        print(
            "HTTP status:",
            response.status
        )


        # ------------------------------------------
        # Find output_text
        # ------------------------------------------

        output_text = None


        for item in data.get(
            "output",
            []
        ):

            if item.get("type") != "message":
                continue


            for content in item.get(
                "content",
                []
            ):

                if (
                    content.get("type")
                    == "output_text"
                ):

                    output_text = (
                        content.get("text")
                    )


        print()
        print(
            "Model response:",
            output_text
        )


        # ------------------------------------------
        # USAGE
        # ------------------------------------------

        usage = data.get(
            "usage",
            {}
        )


        print()
        print("USAGE")
        print("-" * 70)

        print(
            "Input tokens:",
            usage.get("input_tokens")
        )

        print(
            "Output tokens:",
            usage.get("output_tokens")
        )

        print(
            "Total tokens:",
            usage.get("total_tokens")
        )


        # ------------------------------------------
        # CREDITS
        # ------------------------------------------

        if "credits_consumed" in data:

            print(
                "Credits consumed:",
                data.get(
                    "credits_consumed"
                )
            )


        # ------------------------------------------
        # VERIFY
        # ------------------------------------------

        print()
        print("=" * 70)


        if (
            output_text
            and output_text.strip()
            == "KIE_OK"
        ):

            print(
                "KIE MODEL TEST SUCCESS"
            )

        else:

            print(
                "MODEL RESPONDED, "
                "BUT TEXT WAS NOT KIE_OK"
            )


        print("=" * 70)


except urllib.error.HTTPError as error:

    error_body = (
        error
        .read()
        .decode(
            "utf-8",
            errors="replace"
        )
    )

    print()
    print("=" * 70)
    print("KIE HTTP ERROR")
    print("=" * 70)

    print(
        "HTTP status:",
        error.code
    )

    print(
        "Response:",
        error_body
    )


except Exception as error:

    print()
    print("=" * 70)
    print("KIE CONNECTION ERROR")
    print("=" * 70)

    print(
        type(error).__name__,
        ":",
        error
    )