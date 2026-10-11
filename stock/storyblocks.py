import hashlib
import hmac
import os
import time

import requests


class StoryblocksProvider:

    BASE_URL = (
        "https://api.storyblocks.com"
    )

    SEARCH_RESOURCE = (
        "/api/v2/videos/search"
    )


    @property
    def name(self):

        return "storyblocks"


    def __init__(
        self,
        timeout=25,
    ):

        self.timeout = int(
            timeout
        )

        self.public_key = str(
            os.getenv(
                "STORYBLOCKS_PUBLIC_KEY",
                "",
            )
            or ""
        ).strip()

        self.secret_key = str(
            os.getenv(
                "STORYBLOCKS_SECRET_KEY",
                "",
            )
            or ""
        ).strip()

        self.project_id = str(
            os.getenv(
                "STORYBLOCKS_PROJECT_ID",
                "",
            )
            or ""
        ).strip()

        self.user_id = str(
            os.getenv(
                "STORYBLOCKS_USER_ID",
                "",
            )
            or ""
        ).strip()


    # ==================================================
    # CREDENTIAL STATUS
    # ==================================================

    def credentials_ready(self):

        return all(
            [
                self.public_key,
                self.secret_key,
                self.project_id,
                self.user_id,
            ]
        )


    # ==================================================
    # HMAC
    # ==================================================

    def _build_auth(
        self,
        resource,
    ):

        if not self.credentials_ready():

            raise RuntimeError(
                "Storyblocks credentials are incomplete."
            )


        # Storyblocks allows EXPIRES to be in the future.
        # 5 minutes gives enough room for network delay.

        expires = str(
            int(time.time())
            + 300
        )


        signing_key = (
            self.secret_key
            + expires
        ).encode(
            "utf-8"
        )


        message = str(
            resource
        ).encode(
            "utf-8"
        )


        signature = hmac.new(

            signing_key,

            message,

            hashlib.sha256,

        ).hexdigest()


        return {

            "APIKEY":
                self.public_key,

            "EXPIRES":
                expires,

            "HMAC":
                signature,
        }


    # ==================================================
    # REQUEST
    # ==================================================

    def _get_json(
        self,
        resource,
        params=None,
    ):

        params = dict(
            params
            or {}
        )


        auth = self._build_auth(
            resource
        )

        params.update(
            auth
        )


        url = (
            self.BASE_URL
            + resource
        )


        response = requests.get(

            url,

            params=params,

            timeout=self.timeout,

            headers={
                "Accept":
                    "application/json",

                "User-Agent":
                    "AI-Video-Editor/1.0",
            },
        )


        if response.status_code != 200:

            message = (
                response.text
                or ""
            )[:500]


            raise RuntimeError(

                "Storyblocks HTTP "
                + str(
                    response.status_code
                )
                + ": "
                + message
            )


        try:

            return response.json()

        except Exception as error:

            raise RuntimeError(
                "Storyblocks returned invalid JSON: "
                + str(error)
            )


    # ==================================================
    # PREVIEW
    # ==================================================

    @staticmethod
    def _best_preview(
        item,
    ):

        previews = (
            item.get(
                "preview_urls"
            )
            or {}
        )


        if isinstance(
            previews,
            dict,
        ):

            for key in (
                "_720p",
                "_480p",
                "_360p",
                "_180p",
            ):

                url = previews.get(
                    key
                )

                if url:

                    return url


            for url in previews.values():

                if isinstance(
                    url,
                    str,
                ) and url:

                    return url


        preview_url = item.get(
            "preview_url"
        )


        if isinstance(
            preview_url,
            str,
        ):

            return preview_url


        return ""


    # ==================================================
    # VIDEO DIMENSIONS
    # ==================================================

    @staticmethod
    def _extract_dimensions(
        item,
    ):

        best_width = 0
        best_height = 0
        best_area = 0


        formats = (
            item.get(
                "download_formats"
            )
            or {}
        )


        def walk(value):

            nonlocal best_width
            nonlocal best_height
            nonlocal best_area


            if isinstance(
                value,
                dict,
            ):

                width = value.get(
                    "width"
                )

                height = value.get(
                    "height"
                )


                try:

                    width = int(
                        width
                        or 0
                    )

                    height = int(
                        height
                        or 0
                    )

                except Exception:

                    width = 0
                    height = 0


                area = (
                    width
                    * height
                )


                if area > best_area:

                    best_area = area

                    best_width = width
                    best_height = height


                for child in value.values():

                    walk(
                        child
                    )


            elif isinstance(
                value,
                list,
            ):

                for child in value:

                    walk(
                        child
                    )


        walk(
            formats
        )


        # Safe fallback for ordinary HD landscape footage.

        if (
            best_width <= 0
            or
            best_height <= 0
        ):

            max_resolution = (
                item.get(
                    "maxResolution"
                )
                or
                item.get(
                    "max_resolution"
                )
            )


            if isinstance(
                max_resolution,
                dict,
            ):

                try:

                    best_width = int(
                        max_resolution.get(
                            "width",
                            0,
                        )
                        or 0
                    )

                    best_height = int(
                        max_resolution.get(
                            "height",
                            0,
                        )
                        or 0
                    )

                except Exception:

                    pass


        return (
            best_width,
            best_height,
        )


    # ==================================================
    # SEARCH
    # ==================================================

    def search(
        self,
        query,
        limit=5,
        per_page=None,
        **kwargs,
    ):

        if not self.credentials_ready():

            print(
                "[Storyblocks] credentials missing."
            )

            return []


        if per_page is not None:

            limit = per_page


        try:

            limit = int(
                limit
            )

        except Exception:

            limit = 5


        limit = max(
            1,
            min(
                limit,
                250,
            ),
        )


        query = str(
            query
            or ""
        ).strip()


        if not query:

            return []


        params = {

            "project_id":
                self.project_id,

            "user_id":
                self.user_id,

            "keywords":
                query,

            "content_type":
                "footage",

            "quality":
                "HD",

            "page":
                1,

            "results_per_page":
                limit,

            "sort_by":
                "most_relevant",

            "sort_order":
                "DESC",

            "safe_search":
                "true",

            "orientation":
                "horizontal",

            "extended": (
                "download_formats,"
                "maxResolution,"
                "aspectRatio,"
                "durationMs,"
                "description"
            ),
        }


        try:

            data = self._get_json(

                self.SEARCH_RESOURCE,

                params=params,
            )


        except Exception as error:

            print(
                "[Storyblocks] search error:",
                error,
            )

            return []


        raw_results = (
            data.get(
                "results"
            )
            or []
        )


        if not isinstance(
            raw_results,
            list,
        ):

            print(
                "[Storyblocks] unexpected result format."
            )

            return []


        candidates = []


        for item in raw_results:

            if not isinstance(
                item,
                dict,
            ):

                continue


            media_id = item.get(
                "id"
            )


            if media_id is None:

                continue


            thumbnail = str(
                item.get(
                    "thumbnail_url",
                    "",
                )
                or ""
            )


            preview = (
                self._best_preview(
                    item
                )
            )


            if not thumbnail:

                thumbnail = preview


            if not thumbnail:

                continue


            width, height = (
                self._extract_dimensions(
                    item
                )
            )


            try:

                duration = float(
                    item.get(
                        "duration",
                        0,
                    )
                    or 0
                )

            except Exception:

                duration = 0.0


            if duration <= 0:

                try:

                    duration_ms = float(
                        item.get(
                            "durationMs",
                            0,
                        )
                        or 0
                    )

                    duration = (
                        duration_ms
                        / 1000.0
                    )

                except Exception:

                    duration = 0.0


            contributor = (
                item.get(
                    "contributor"
                )
                or {}
            )


            if isinstance(
                contributor,
                dict,
            ):

                author = (
                    contributor.get(
                        "username"
                    )
                    or
                    "Storyblocks"
                )

            else:

                author = (
                    "Storyblocks"
                )


            candidate = {

                # ------------------------------------------
                # CURRENT STOCK SCHEMA
                # ------------------------------------------

                "source":
                    "storyblocks",

                "type":
                    "video",

                "id":
                    media_id,

                "title":
                    item.get(
                        "title",
                        "",
                    ),

                "thumb_url":
                    thumbnail,

                "preview_url":
                    preview,

                # IMPORTANT:
                # full-size URL is resolved ONLY after
                # the AI selects this candidate.
                "download_url":
                    "",

                "width":
                    width,

                "height":
                    height,

                "duration":
                    duration,

                "author":
                    author,

                "author_url":
                    "",

                "page_url":
                    "",

                "search_query":
                    query,


                # ------------------------------------------
                # NORMALIZED ALIASES
                # ------------------------------------------

                "provider":
                    "storyblocks",

                "media_type":
                    "video",

                "media_id":
                    media_id,

                "thumbnail_url":
                    thumbnail,


                # ------------------------------------------
                # DEFERRED DOWNLOAD
                # ------------------------------------------

                "download_resolver":
                    "storyblocks",

                "storyblocks_asset_id":
                    item.get(
                        "asset_id"
                    ),

                "storyblocks_content_id":
                    item.get(
                        "content_id"
                    ),

                "storyblocks_url_id":
                    item.get(
                        "url_id"
                    ),
            }


            candidates.append(
                candidate
            )


        return candidates


    # ==================================================
    # ALIAS
    # ==================================================

    def search_videos(
        self,
        query,
        per_page=5,
    ):

        return self.search(
            query=query,
            limit=per_page,
        )


    # ==================================================
    # DOWNLOAD URL RESOLVER
    # ==================================================

    def resolve_download_url(
        self,
        media,
    ):

        if isinstance(
            media,
            dict,
        ):

            media_id = (
                media.get(
                    "media_id"
                )
                or
                media.get(
                    "id"
                )
            )

        else:

            media_id = media


        if media_id is None:

            raise RuntimeError(
                "Storyblocks media ID missing."
            )


        resource = (
            "/api/v2/videos/"
            "stock-item/download/"
            + str(media_id)
        )


        params = {

            "project_id":
                self.project_id,

            "user_id":
                self.user_id,
        }


        data = self._get_json(

            resource,

            params=params,
        )


        urls = []


        # ==================================================
        # RECURSIVELY FIND DOWNLOAD LINKS
        # ==================================================

        def walk(
            value,
            path="",
        ):

            if isinstance(
                value,
                str,
            ):

                if value.startswith(
                    (
                        "http://",
                        "https://",
                    )
                ):

                    urls.append(
                        (
                            path.lower(),
                            value,
                        )
                    )

                return


            if isinstance(
                value,
                dict,
            ):

                for key, child in value.items():

                    new_path = (
                        path
                        + "/"
                        + str(key)
                    )

                    walk(
                        child,
                        new_path,
                    )


            elif isinstance(
                value,
                list,
            ):

                for index, child in enumerate(
                    value
                ):

                    walk(
                        child,
                        (
                            path
                            + "/"
                            + str(index)
                        ),
                    )


        walk(
            data
        )


        if not urls:

            raise RuntimeError(
                "Storyblocks download endpoint "
                "returned no file URL."
            )


        # ==================================================
        # PREFER MP4 + HIGHEST PRACTICAL RESOLUTION
        # ==================================================

        def score(
            entry,
        ):

            path, url = entry


            value = (
                path
                + " "
                + url.lower()
            )


            points = 0


            if "mp4" in value:

                points += 10000


            if "2160" in value:

                points += 5000

            elif "4k" in value:

                points += 5000

            elif "1080" in value:

                points += 4000

            elif "720" in value:

                points += 3000

            elif "480" in value:

                points += 2000


            return points


        urls.sort(
            key=score,
            reverse=True,
        )


        return urls[0][1]


    # ==================================================
    # BASIC LIVE TEST
    # ==================================================

    def test_connection(self):

        if not self.credentials_ready():

            return (
                False,
                "Credentials missing",
            )


        try:

            results = self.search(

                "nature",

                limit=1,
            )


            if results:

                return (
                    True,
                    "Search successful",
                )


            return (
                False,
                "Search returned no results",
            )


        except Exception as error:

            return (
                False,
                str(error),
            )