from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Iterable


class AutomationStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class AutomationStageDefinition:
    key: str
    label: str
    idle_detail: str


AUTOMATION_STAGES: tuple[AutomationStageDefinition, ...] = (
    AutomationStageDefinition("script", "Kịch bản", "Lưu và kiểm tra kịch bản đầu vào."),
    AutomationStageDefinition("voice", "Tạo giọng đọc", "Tạo Voice Asset bằng giọng đã chọn."),
    AutomationStageDefinition("voice_timing", "Phân tích nội dung", "Chép lời và xác định mốc thời gian từ giọng đọc."),
    AutomationStageDefinition("scene_analysis", "Chia cảnh", "Chia nội dung thành các cảnh theo thời gian giọng đọc."),
    AutomationStageDefinition("media_search", "Tìm ảnh & video", "Tạo truy vấn và tìm tư liệu phù hợp cho từng cảnh."),
    AutomationStageDefinition("media_assignment", "Chuẩn bị tư liệu", "Xếp hạng và gán tư liệu phù hợp nhất cho từng cảnh."),
    AutomationStageDefinition("music", "Thêm nhạc nền", "Chọn hoặc tạo nhạc nền phù hợp với video."),
    AutomationStageDefinition("timeline", "Dựng video", "Khớp giọng đọc, cảnh, tư liệu và nhạc vào timeline."),
    AutomationStageDefinition("render", "Xuất video", "Kết xuất video theo thiết lập đầu ra."),
    AutomationStageDefinition("export", "Hoàn tất", "Kiểm tra và công bố video đầu ra của dự án."),
)

_STAGE_BY_KEY = {item.key: item for item in AUTOMATION_STAGES}


@dataclass
class AutomationStageState:
    key: str
    status: AutomationStageStatus = AutomationStageStatus.PENDING
    detail: str = ""
    progress: int = 0

    def normalized_progress(self) -> int:
        return max(0, min(100, int(self.progress)))


@dataclass
class AutomationWorkflowState:
    stages: list[AutomationStageState] = field(
        default_factory=lambda: [
            AutomationStageState(key=item.key, detail=item.idle_detail)
            for item in AUTOMATION_STAGES
        ]
    )
    message: str = "Sẵn sàng bắt đầu quy trình tự động."

    def _stage(self, key: str) -> AutomationStageState:
        if key not in _STAGE_BY_KEY:
            raise KeyError(f"Unknown automation stage: {key}")
        for stage in self.stages:
            if stage.key == key:
                return stage
        raise KeyError(f"Missing automation stage state: {key}")

    def set_stage(
        self,
        key: str,
        status: AutomationStageStatus | str,
        *,
        detail: str | None = None,
        progress: int | None = None,
    ) -> AutomationStageState:
        stage = self._stage(key)
        stage.status = AutomationStageStatus(status)
        if detail is not None:
            stage.detail = str(detail)
        if progress is not None:
            stage.progress = max(0, min(100, int(progress)))
        elif stage.status in (AutomationStageStatus.COMPLETED, AutomationStageStatus.SKIPPED):
            stage.progress = 100
        elif stage.status == AutomationStageStatus.PENDING:
            stage.progress = 0
        return stage

    def mark_completed(self, key: str, detail: str | None = None) -> AutomationStageState:
        return self.set_stage(
            key,
            AutomationStageStatus.COMPLETED,
            detail=detail,
            progress=100,
        )

    def mark_running(
        self,
        key: str,
        detail: str | None = None,
        *,
        progress: int = 0,
    ) -> AutomationStageState:
        for stage in self.stages:
            if stage.status == AutomationStageStatus.RUNNING and stage.key != key:
                stage.status = AutomationStageStatus.PENDING
                stage.progress = 0
        return self.set_stage(
            key,
            AutomationStageStatus.RUNNING,
            detail=detail,
            progress=progress,
        )

    def mark_failed(self, key: str, detail: str) -> AutomationStageState:
        return self.set_stage(
            key,
            AutomationStageStatus.FAILED,
            detail=detail,
        )

    def stage_status(self, key: str) -> AutomationStageStatus:
        return self._stage(key).status

    def first_incomplete_key(self) -> str | None:
        for stage in self.stages:
            if stage.status not in (
                AutomationStageStatus.COMPLETED,
                AutomationStageStatus.SKIPPED,
            ):
                return stage.key
        return None

    def current_stage_key(self) -> str | None:
        for stage in self.stages:
            if stage.status == AutomationStageStatus.RUNNING:
                return stage.key
        return self.first_incomplete_key()

    def overall_progress(self) -> int:
        if not self.stages:
            return 0
        total = 0.0
        for stage in self.stages:
            if stage.status in (
                AutomationStageStatus.COMPLETED,
                AutomationStageStatus.SKIPPED,
            ):
                total += 1.0
            elif stage.status == AutomationStageStatus.RUNNING:
                total += stage.normalized_progress() / 100.0
        return int(round((total / len(self.stages)) * 100.0))

    def to_dict(self) -> dict:
        return {
            "format": "creator_studio_automation_workflow_m110_1",
            "message": self.message,
            "stages": [
                {
                    **asdict(stage),
                    "status": stage.status.value,
                    "progress": stage.normalized_progress(),
                }
                for stage in self.stages
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "AutomationWorkflowState":
        if not isinstance(payload, dict):
            raise TypeError("Automation workflow payload must be a dict.")
        raw_stages = payload.get("stages")
        if not isinstance(raw_stages, list):
            raise ValueError("Automation workflow stages must be a list.")

        by_key = {}
        for item in raw_stages:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            if key not in _STAGE_BY_KEY:
                continue
            by_key[key] = AutomationStageState(
                key=key,
                status=AutomationStageStatus(item.get("status", AutomationStageStatus.PENDING.value)),
                detail=str(item.get("detail") or _STAGE_BY_KEY[key].idle_detail),
                progress=max(0, min(100, int(item.get("progress", 0) or 0))),
            )

        stages = []
        for definition in AUTOMATION_STAGES:
            stages.append(
                by_key.get(
                    definition.key,
                    AutomationStageState(
                        key=definition.key,
                        detail=definition.idle_detail,
                    ),
                )
            )
        return cls(
            stages=stages,
            message=str(payload.get("message") or "Sẵn sàng bắt đầu quy trình tự động."),
        )

    def apply_completed(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.mark_completed(key)
