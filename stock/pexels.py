import os
import json
import urllib.parse
import urllib.request
import urllib.error

from stock.base import (
    BaseStockProvider,
    StockProviderError
)

from stock.models import (
    StockMedia
)


class PexelsProvider(BaseStockProvider):

    VIDEO_URL = (
        "https://api.pexels.com/videos/search"
    )

    IMAGE_URL = (
        "https://api.pexels.com/v1/search"
    )


    def __init__(
        self,
        timeout=30
    ):

        self.api_key = os.getenv(
            "PEXELS_API_KEY"
        )

        if not self.api_key:

            raise StockProviderError(
                "PEXELS_API_KEY is not set."
            )

        self.timeout = timeout


    @property
    def name(self):

        return "pexels"


    # ==================================================
    # VIDEO SEARCH
    # ==================================================

    def search_videos(
        self,
        query,
        per_page=10
    ):

        params = urllib.parse.urlencode({

            "query": query,

            "per_page": per_page,

            "orientation": "landscape"
        })


        url = (
            f"{self.VIDEO_URL}?{params}"
        )


        data = self._request(
            url
        )


        results = []


        for video in data.get(
            "videos",
            []
        ):

            best_file = (
                self._select_video_file(
                    video.get(
                        "video_files",
                        []
                    )
                )
            )


            if not best_file:

                continue


            pictures = video.get(
                "video_pictures",
                []
            )


            thumbnail_url = None


            if pictures:

                thumbnail_url = (
                    pictures[0].get(
                        "picture"
                    )
                )


            user = video.get(
                "user",
                {}
            )


            item = StockMedia(

                provider="pexels",

                media_id=str(
                    video.get("id")
                ),

                media_type="video",

                title=(
                    f"Pexels Video "
                    f"{video.get('id')}"
                ),

                width=best_file.get(
                    "width"
                ),

                height=best_file.get(
                    "height"
                ),

                duration=video.get(
                    "duration"
                ),

                preview_url=best_file.get(
                    "link"
                ),

                thumbnail_url=(
                    thumbnail_url
                ),

                download_url=best_file.get(
                    "link"
                ),

                source_url=video.get(
                    "url"
                ),

                photographer=user.get(
                    "name"
                )
            )


            results.append(
                item
            )


        return results


    # ==================================================
    # IMAGE SEARCH
    # ==================================================

    def search_images(
        self,
        query,
        per_page=10
    ):

        params = urllib.parse.urlencode({

            "query": query,

            "per_page": per_page,

            "orientation": "landscape"
        })


        url = (
            f"{self.IMAGE_URL}?{params}"
        )


        data = self._request(
            url
        )


        results = []


        for photo in data.get(
            "photos",
            []
        ):

            src = photo.get(
                "src",
                {}
            )


            item = StockMedia(

                provider="pexels",

                media_id=str(
                    photo.get("id")
                ),

                media_type="image",

                title=(
                    photo.get("alt")
                    or
                    f"Pexels Image "
                    f"{photo.get('id')}"
                ),

                width=photo.get(
                    "width"
                ),

                height=photo.get(
                    "height"
                ),

                duration=None,

                preview_url=src.get(
                    "large"
                ),

                thumbnail_url=src.get(
                    "medium"
                ),

                download_url=(
                    src.get("original")
                ),

                source_url=photo.get(
                    "url"
                ),

                photographer=photo.get(
                    "photographer"
                )
            )


            results.append(
                item
            )


        return results


    # ==================================================
    # HTTP REQUEST
    # ==================================================

    def _request(
        self,
        url
    ):

        request = urllib.request.Request(

            url=url,

            method="GET",

            headers={
                "Authorization": (
                    self.api_key
                ),

                "User-Agent": (
                    "AI-Video-Editor/1.0"
                )
            }
        )


        try:

            with urllib.request.urlopen(
                request,
                timeout=self.timeout
            ) as response:

                body = (
                    response
                    .read()
                    .decode("utf-8")
                )


                return json.loads(
                    body
                )


        except urllib.error.HTTPError as error:

            body = (
                error
                .read()
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )


            raise StockProviderError(

                f"Pexels HTTP "
                f"{error.code}: "
                f"{body}"

            ) from error


        except Exception as error:

            raise StockProviderError(

                f"Pexels request failed: "
                f"{error}"

            ) from error


    # ==================================================
    # SELECT VIDEO FILE
    # ==================================================

    def _select_video_file(
        self,
        files
    ):

        candidates = []


        for file in files:

            width = file.get(
                "width"
            )

            height = file.get(
                "height"
            )


            if not width or not height:

                continue


            # Landscape only

            if width < height:

                continue


            candidates.append(
                file
            )


        if not candidates:

            return None


        # ----------------------------------------------
        # Prefer 1080p-ish footage.
        # Avoid automatically selecting huge 4K files.
        # ----------------------------------------------

        target_width = 1920

        target_height = 1080


        candidates.sort(

            key=lambda item: (

                abs(
                    item.get(
                        "width",
                        0
                    )
                    - target_width
                )

                +

                abs(
                    item.get(
                        "height",
                        0
                    )
                    - target_height
                )
            )
        )


        return candidates[0]