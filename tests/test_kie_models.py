import os
import json
import urllib.request
import urllib.error


print("=" * 70)
print("AI VIDEO EDITOR")
print("KIE.AI MODEL LIST TEST")
print("=" * 70)


api_key = os.getenv("KIE_API_KEY")


if not api_key:
    raise RuntimeError(
        "KIE_API_KEY is not set."
    )


url = (
    "https://api.kie.ai"
    "/openai/v1/models"
)


request = urllib.request.Request(
    url=url,
    method="GET",
    headers={
        "Authorization": (
            f"Bearer {api_key}"
        )
    }
)


print()
print("Connecting to Kie.ai...")
print("Endpoint:", url)


try:

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        body = response.read().decode(
            "utf-8"
        )

        data = json.loads(body)


        print()
        print("=" * 70)
        print("KIE MODEL RESPONSE")
        print("=" * 70)

        print(
            "HTTP status:",
            response.status
        )


        # ------------------------------------------
        # KIE richer model list
        # ------------------------------------------

        models = data.get(
            "models",
            []
        )


        print()
        print(
            "Models found:",
            len(models)
        )


        print()
        print("=" * 70)
        print("AVAILABLE MODEL SLUGS")
        print("=" * 70)


        for index, model in enumerate(
            models,
            start=1
        ):

            slug = model.get(
                "slug"
            )

            context_window = model.get(
                "context_window"
            )

            reasoning = model.get(
                "supported_reasoning_levels"
            )


            print()
            print(
                f"{index}. {slug}"
            )

            print(
                "   Context:",
                context_window
            )

            print(
                "   Reasoning:",
                reasoning
            )


except urllib.error.HTTPError as error:

    body = error.read().decode(
        "utf-8",
        errors="replace"
    )

    print()
    print("=" * 70)
    print("HTTP ERROR")
    print("=" * 70)

    print(
        "Status:",
        error.code
    )

    print(
        body
    )


except Exception as error:

    print()
    print("=" * 70)
    print("ERROR")
    print("=" * 70)

    print(
        type(error).__name__,
        ":",
        error
    )