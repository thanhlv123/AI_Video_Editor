from pathlib import Path
import os
import sys


ROOT = (
    Path(
        __file__
    )
    .resolve()
    .parent
    .parent
)


sys.path.insert(
    0,
    str(
        ROOT
    )
)


from config.api_key_manager import (
    APIKeyManager,
)

from stock.pixabay import (
    PixabayProvider,
)


print(
    "=" * 70
)

print(
    "PIXABAY PROVIDER TEST"
)

print(
    "=" * 70
)


manager = APIKeyManager(
    ROOT
)


runtime = (
    manager.runtime_environment()
)


for name, value in runtime.items():

    os.environ[
        name
    ] = value


if not os.getenv(
    "PIXABAY_API_KEY"
):

    raise RuntimeError(
        "PIXABAY_API_KEY is not configured "
        "or Pixabay is not Enabled."
    )


provider = (
    PixabayProvider()
)


results = (
    provider.search_videos(

        query=
            "person listening music headphones",

        per_page=
            5,
    )
)


print(
    "Results:",
    len(
        results
    )
)


for index, item in enumerate(
    results[:5],
    start=1,
):

    print()

    print(
        f"[{index}]"
    )

    print(
        "Provider:",
        item.provider
    )

    print(
        "ID:",
        item.media_id
    )

    print(
        "Type:",
        item.media_type
    )

    print(
        "Duration:",
        item.duration
    )

    print(
        "Resolution:",
        f"{item.width}x{item.height}"
    )

    print(
        "Photographer:",
        item.photographer
    )


if not results:

    raise RuntimeError(
        "Pixabay returned no videos."
    )


print()

print(
    "=" * 70
)

print(
    "PIXABAY PROVIDER: PASS"
)

print(
    "=" * 70
)