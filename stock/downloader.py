from pathlib import Path
import urllib.request
import urllib.error
import tempfile
import shutil


class DownloadError(Exception):
    pass


class DownloadManager:

    def __init__(
        self,
        output_dir,
        timeout=120,
        chunk_size=1024 * 1024
    ):

        self.output_dir = Path(
            output_dir
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.timeout = timeout
        self.chunk_size = chunk_size


    # ==================================================
    # DOWNLOAD
    # ==================================================

    def download(
        self,
        media,
        scene_id
    ):

        url = media.get(
            "download_url"
        )

        if not url:
            raise DownloadError(
                "Selected media has no download_url."
            )


        provider = (
            media.get(
                "provider",
                "unknown"
            )
        )


        media_id = str(
            media.get(
                "media_id",
                "unknown"
            )
        )


        media_type = media.get(
            "media_type",
            "video"
        )


        extension = self._extension(
            media_type,
            url
        )


        filename = (
            f"{scene_id}_"
            f"{provider}_"
            f"{media_id}"
            f"{extension}"
        )


        destination = (
            self.output_dir
            / filename
        )


        # ==================================================
        # ALREADY DOWNLOADED
        # ==================================================

        if (
            destination.exists()
            and
            destination.stat().st_size > 0
        ):

            return {
                "status": "existing",
                "path": str(
                    destination.resolve()
                ),
                "filename": filename,
                "size": (
                    destination.stat().st_size
                )
            }


        # ==================================================
        # TEMP FILE
        # ==================================================

        temp_file = None


        try:

            request = urllib.request.Request(

                url,

                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "AI-Video-Editor/1.0"
                    )
                }
            )


            with urllib.request.urlopen(
                request,
                timeout=self.timeout
            ) as response:

                status = getattr(
                    response,
                    "status",
                    200
                )


                if status != 200:
                    raise DownloadError(
                        f"HTTP status: {status}"
                    )


                content_type = (
                    response.headers.get(
                        "Content-Type",
                        ""
                    )
                )


                suffix = (
                    ".download"
                )


                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=suffix,
                    dir=self.output_dir
                ) as temp:

                    temp_file = Path(
                        temp.name
                    )


                    while True:

                        chunk = response.read(
                            self.chunk_size
                        )

                        if not chunk:
                            break

                        temp.write(
                            chunk
                        )


            # ==================================================
            # VALIDATE BASIC FILE
            # ==================================================

            if not temp_file.exists():
                raise DownloadError(
                    "Temporary download file "
                    "was not created."
                )


            size = temp_file.stat().st_size


            if size < 1024:
                raise DownloadError(
                    f"Downloaded file is too small: "
                    f"{size} bytes"
                )


            # Prevent accidentally saving HTML error pages.

            if (
                "text/html"
                in content_type.lower()
            ):

                raise DownloadError(
                    "Server returned HTML "
                    "instead of media."
                )


            shutil.move(
                str(temp_file),
                str(destination)
            )


            return {
                "status": "downloaded",
                "path": str(
                    destination.resolve()
                ),
                "filename": filename,
                "size": size,
                "content_type": (
                    content_type
                )
            }


        except urllib.error.HTTPError as error:

            raise DownloadError(
                f"Download HTTP error "
                f"{error.code}: {error.reason}"
            ) from error


        except urllib.error.URLError as error:

            raise DownloadError(
                f"Download network error: "
                f"{error.reason}"
            ) from error


        except DownloadError:
            raise


        except Exception as error:

            raise DownloadError(
                f"Download failed: {error}"
            ) from error


        finally:

            if (
                temp_file
                and
                temp_file.exists()
            ):

                try:
                    temp_file.unlink()
                except Exception:
                    pass


    # ==================================================
    # EXTENSION
    # ==================================================

    def _extension(
        self,
        media_type,
        url
    ):

        url_lower = url.lower()


        if media_type == "image":

            for ext in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            ):

                if ext in url_lower:
                    return ext

            return ".jpg"


        # Pexels video files are normally MP4.

        return ".mp4"