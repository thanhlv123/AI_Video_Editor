import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass
class Subtitle:
    index: int
    start: float
    end: float
    text: str

    @property
    def duration(self):
        return self.end - self.start

    def to_dict(self):
        return asdict(self)


class SRTParser:

    TIMESTAMP_PATTERN = re.compile(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    )

    def timestamp_to_seconds(self, value):

        match = self.TIMESTAMP_PATTERN.match(
            value.strip()
        )

        if not match:
            raise ValueError(
                f"Invalid SRT timestamp: {value}"
            )

        hours, minutes, seconds, milliseconds = (
            map(int, match.groups())
        )

        return (
            hours * 3600
            + minutes * 60
            + seconds
            + milliseconds / 1000
        )


    def parse(self, file_path):

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"SRT file not found: {path}"
            )

        content = path.read_text(
            encoding="utf-8-sig"
        )

        content = content.replace(
            "\r\n",
            "\n"
        )

        blocks = re.split(
            r"\n\s*\n",
            content.strip()
        )

        subtitles: List[Subtitle] = []


        for block in blocks:

            lines = [
                line.strip()
                for line in block.split("\n")
                if line.strip()
            ]

            if len(lines) < 3:
                continue


            try:
                index = int(lines[0])
            except ValueError:
                continue


            timing = lines[1]

            if "-->" not in timing:
                continue


            start_text, end_text = timing.split(
                "-->",
                1
            )


            start = self.timestamp_to_seconds(
                start_text
            )

            end = self.timestamp_to_seconds(
                end_text
            )


            text = " ".join(
                lines[2:]
            )


            subtitles.append(
                Subtitle(
                    index=index,
                    start=start,
                    end=end,
                    text=text
                )
            )


        return subtitles