from pathlib import Path
import os
import sys


ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

sys.path.insert(
    0,
    str(ROOT),
)


from config.api_key_manager import APIKeyManager
from stock.storyblocks import StoryblocksProvider


# ==================================================
# LOAD SECURE CREDENTIALS
# ==================================================

manager = APIKeyManager(
    ROOT
)

runtime = (
    manager.runtime_environment()
)

for key, value in runtime.items():

    os.environ[
        key
    ] = value


# ==================================================
# STATUS
# ==================================================

print("=" * 70)
print("STORYBLOCKS SEARCH TEST")
print("=" * 70)


required = [

    "STORYBLOCKS_PUBLIC_KEY",

    "STORYBLOCKS_SECRET_KEY",

    "STORYBLOCKS_PROJECT_ID",

    "STORYBLOCKS_USER_ID",
]


missing = []


for name in required:

    ready = bool(
        os.getenv(
            name
        )
    )

    print(
        f"{name}:",
        (
            "READY"
            if ready
            else "MISSING"
        ),
    )

    if not ready:

        missing.append(
            name
        )


if missing:

    print()
    print(
        "STORYBLOCKS CREDENTIALS: NOT READY"
    )

    print(
        "Enable Storyblocks and enter all "
        "four credentials in API KEYS / SETTINGS."
    )

    raise SystemExit(
        2
    )


# ==================================================
# PROVIDER
# ==================================================

provider = StoryblocksProvider()


print()
print(
    "Provider:",
    provider.name
)

print(
    "Credentials ready:",
    provider.credentials_ready()
)


# ==================================================
# SEARCH
# ==================================================

print()
print("=" * 70)
print("SEARCH: peaceful nature sunrise")
print("=" * 70)


results = provider.search(

    "peaceful nature sunrise",

    limit=5,
)


print()
print(
    "Results:",
    len(results)
)


for index, item in enumerate(
    results,
    start=1,
):

    print()
    print(
        f"[{index}]"
    )

    print(
        "Provider:",
        item.get(
            "provider"
        )
    )

    print(
        "ID:",
        item.get(
            "media_id"
        )
    )

    print(
        "Title:",
        item.get(
            "title"
        )
    )

    print(
        "Duration:",
        item.get(
            "duration"
        )
    )

    print(
        "Resolution:",
        (
            f"{item.get('width')}x"
            f"{item.get('height')}"
        )
    )

    print(
        "Thumbnail:",
        bool(
            item.get(
                "thumbnail_url"
            )
        )
    )

    print(
        "Preview:",
        bool(
            item.get(
                "preview_url"
            )
        )
    )

    print(
        "Download deferred:",
        (
            item.get(
                "download_resolver"
            )
            == "storyblocks"
        )
    )


print()
print("=" * 70)


if results:

    print(
        "STORYBLOCKS HMAC AUTH: PASS"
    )

    print(
        "STORYBLOCKS SEARCH: PASS"
    )

else:

    print(
        "STORYBLOCKS SEARCH: FAIL"
    )


print("=" * 70)