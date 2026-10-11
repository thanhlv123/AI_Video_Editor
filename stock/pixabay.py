import os

import requests


from stock.base import BaseStockProvider
from stock.models import StockMedia


class PixabayProvider(
    BaseStockProvider
):

    VIDEO_URL = (
        "https://pixabay.com/api/videos/"
    )

    IMAGE_URL = (
        "https://pixabay.com/api/"
    )


    def __init__(
        self,
        api_key=None,
        timeout=20,
    ):

        self.api_key = (

            api_key

            or os.getenv(
                "PIXABAY_API_KEY"
            )

            or ""
        )

        self.timeout = int(
            timeout
        )


    # ==================================================
    # NAME
    # ==================================================

    @property
    def name(
        self,
    ):

        return "pixabay"


    # ==================================================
    # CHECK KEY
    # ==================================================

    def _has_key(
        self,
    ):

        return bool(
            str(
                self.api_key
                or ""
            ).strip()
        )


    # ==================================================
    # PICK VIDEO VERSION
    # ==================================================

    def _best_video(
        self,
        videos,
    ):

        renditions = []


        for key in (
            "large",
            "medium",
            "small",
            "tiny",
        ):

            item = videos.get(
                key,
                {}
            )


            url = item.get(
                "url"
            )


            if not url:

                continue


            width = int(
                item.get(
                    "width",
                    0,
                )
                or 0
            )


            height = int(
                item.get(
                    "height",
                    0,
                )
                or 0
            )


            renditions.append(
                {
                    "name":
                        key,

                    "url":
                        url,

                    "width":
                        width,

                    "height":
                        height,

                    "thumbnail":
                        item.get(
                            "thumbnail",
                            "",
                        )
                        or "",
                }
            )


        if not renditions:

            return None


        # Prefer landscape footage.

        landscape = [

            item

            for item
            in renditions

            if (
                item["width"]
                >= item["height"]
            )
        ]


        pool = (
            landscape
            or renditions
        )


        # Pick version closest to 1920x1080.

        best = min(

            pool,

            key=lambda item: (

                abs(
                    item["width"]
                    - 1920
                )

                + abs(
                    item["height"]
                    - 1080
                )
            ),
        )


        return best


    # ==================================================
    # SEARCH VIDEO
    # ==================================================

    def search_videos(
        self,
        query,
        per_page=10,
    ):

        if not self._has_key():

            return []


        query = str(
            query
            or ""
        ).strip()


        if not query:

            return []


        params = {

            "key":
                self.api_key,

            "q":
                query[:100],

            "per_page":
                max(
                    3,
                    min(
                        int(
                            per_page
                        ),
                        50,
                    ),
                ),

            "video_type":
                "film",

            "safesearch":
                "true",

            "order":
                "popular",
        }


        try:

            response = requests.get(

                self.VIDEO_URL,

                params=params,

                timeout=self.timeout,
            )


        except Exception as error:

            print(
                "[PIXABAY] Request error:",
                error,
            )

            return []


        if response.status_code != 200:

            print(
                "[PIXABAY] HTTP",
                response.status_code,
            )

            return []


        try:

            data = response.json()

        except Exception as error:

            print(
                "[PIXABAY] Invalid JSON:",
                error,
            )

            return []


        results = []


        for item in data.get(
            "hits",
            [],
        ):

            media_id = item.get(
                "id"
            )


            if media_id is None:

                continue


            best = self._best_video(

                item.get(
                    "videos",
                    {},
                )
            )


            if not best:

                continue


            thumbnail = (

                best.get(
                    "thumbnail"
                )

                or item.get(
                    "videos",
                    {}
                )
                .get(
                    "medium",
                    {}
                )
                .get(
                    "thumbnail",
                    "",
                )

                or ""
            )


            title = str(
                item.get(
                    "tags",
                    ""
                )
                or ""
            )


            photographer = str(
                item.get(
                    "user",
                    ""
                )
                or "Unknown"
            )


            results.append(

                StockMedia(

                    provider=
                        "pixabay",

                    media_id=
                        str(
                            media_id
                        ),

                    media_type=
                        "video",

                    title=
                        title,

                    width=
                        int(
                            best.get(
                                "width",
                                0,
                            )
                            or 0
                        ),

                    height=
                        int(
                            best.get(
                                "height",
                                0,
                            )
                            or 0
                        ),

                    duration=
                        float(
                            item.get(
                                "duration",
                                0,
                            )
                            or 0
                        ),

                    preview_url=
                        thumbnail,

                    thumbnail_url=
                        thumbnail,

                    download_url=
                        best.get(
                            "url",
                            "",
                        ),

                    source_url=
                        item.get(
                            "pageURL",
                            "",
                        )
                        or "",

                    photographer=
                        photographer,

                    score=
                        0.0,
                )
            )


        return results


    # ==================================================
    # SEARCH IMAGE
    # ==================================================

    def search_images(
        self,
        query,
        per_page=10,
    ):

        if not self._has_key():

            return []


        query = str(
            query
            or ""
        ).strip()


        if not query:

            return []


        params = {

            "key":
                self.api_key,

            "q":
                query[:100],

            "per_page":
                max(
                    3,
                    min(
                        int(
                            per_page
                        ),
                        50,
                    ),
                ),

            "image_type":
                "photo",

            "orientation":
                "horizontal",

            "safesearch":
                "true",

            "order":
                "popular",
        }


        try:

            response = requests.get(

                self.IMAGE_URL,

                params=params,

                timeout=self.timeout,
            )


        except Exception as error:

            print(
                "[PIXABAY] Image request error:",
                error,
            )

            return []


        if response.status_code != 200:

            print(
                "[PIXABAY] Image HTTP",
                response.status_code,
            )

            return []


        try:

            data = response.json()

        except Exception as error:

            print(
                "[PIXABAY] Invalid image JSON:",
                error,
            )

            return []


        results = []


        for item in data.get(
            "hits",
            [],
        ):

            media_id = item.get(
                "id"
            )


            if media_id is None:

                continue


            preview = (

                item.get(
                    "webformatURL"
                )

                or item.get(
                    "previewURL"
                )

                or ""
            )


            download_url = (

                item.get(
                    "largeImageURL"
                )

                or item.get(
                    "webformatURL"
                )

                or ""
            )


            if not download_url:

                continue


            results.append(

                StockMedia(

                    provider=
                        "pixabay",

                    media_id=
                        str(
                            media_id
                        ),

                    media_type=
                        "image",

                    title=
                        str(
                            item.get(
                                "tags",
                                "",
                            )
                            or ""
                        ),

                    width=
                        int(
                            item.get(
                                "imageWidth",
                                0,
                            )
                            or 0
                        ),

                    height=
                        int(
                            item.get(
                                "imageHeight",
                                0,
                            )
                            or 0
                        ),

                    duration=
                        0.0,

                    preview_url=
                        preview,

                    thumbnail_url=
                        (
                            item.get(
                                "previewURL"
                            )
                            or preview
                        ),

                    download_url=
                        download_url,

                    source_url=
                        item.get(
                            "pageURL",
                            "",
                        )
                        or "",

                    photographer=
                        str(
                            item.get(
                                "user",
                                "",
                            )
                            or "Unknown"
                        ),

                    score=
                        0.0,
                )
            )


        return results