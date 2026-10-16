import os
import json
import urllib.request
import urllib.error


print("=" * 70)
print("AI VIDEO EDITOR")
print("KIE.AI API KEY TEST")
print("=" * 70)


# ==================================================
# READ KEY
# ==================================================

api_key = os.getenv(
    "KIE_API_KEY"
)


if not api_key:

    raise RuntimeError(
        "KIE_API_KEY is not set."
    )


print()
print("API key found: YES")
print("Key length:", len(api_key))


# ==================================================
# KIE CREDIT ENDPOINT
# ==================================================

url = (
    "https://api.kie.ai"
    "/api/v1/chat/credit"
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


# ==================================================
# REQUEST
# ==================================================

try:

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        status = response.status

        body = response.read().decode(
            "utf-8"
        )


        print()
        print("=" * 70)
        print("KIE RESPONSE")
        print("=" * 70)

        print(
            "HTTP status:",
            status
        )


        try:

            data = json.loads(
                body
            )

            print(
                json.dumps(
                    data,
                    indent=4,
                    ensure_ascii=False
                )
            )


            if (
                data.get("code") == 200
            ):

                print()
                print("=" * 70)
                print("KIE API KEY WORKS")
                print("=" * 70)

                print(
                    "Remaining credits:",
                    data.get("data")
                )


        except json.JSONDecodeError:

            print(body)


except urllib.error.HTTPError as error:

    body = error.read().decode(
        "utf-8",
        errors="replace"
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
        body
    )


except Exception as error:

    print()
    print("=" * 70)
    print("CONNECTION ERROR")
    print("=" * 70)

    print(
        type(error).__name__,
        ":",
        error
    )