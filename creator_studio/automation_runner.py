from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from creator_studio.automation_workflow import (
    AutomationStageStatus,
    AutomationWorkflowState,
)


RUN_FORMAT = "creator_studio_automation_run_m110_2"
RUN_FILENAME = "automation_run.json"


class AutomationRunStatus(str, Enum):
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _run_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _script_sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _safe_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    return str(value)


@dataclass
class AutomationPipelineCoordinator:
    """Persisted, UI-neutral coordinator for the one-click video workflow.

    The same persisted state machine now covers:
        script -> TTS voice -> VoicePipeline timing/scenes -> media query planning

    M110.1.2 batches scene-intelligence requests, reuses safe project-local
    cache entries, and falls back deterministically when KIE is unavailable.
    M110.2 continues the same run through Pexels/Pixabay stock acquisition,
    M106 asset promotion and M107 automatic scene assignment. M110.3 then
    performs preview-only YouTube reference discovery for unresolved or weak
    stock scenes without downloading YouTube audiovisual content.
    """

    project_root: Path
    config: dict[str, Any]
    language: str
    script_hash: str
    run_id: str
    run_dir: Path
    state: AutomationWorkflowState = field(default_factory=AutomationWorkflowState)
    status: AutomationRunStatus = AutomationRunStatus.RUNNING
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    error: str = ""

    @classmethod
    def create(
        cls,
        project_root: Path,
        *,
        script_text: str,
        language: str,
        config: dict[str, Any] | None = None,
    ) -> "AutomationPipelineCoordinator":
        root = Path(project_root).resolve()
        automation_root = root / "work" / "automation"
        automation_root.mkdir(parents=True, exist_ok=True)

        base = f"run_{_run_stamp()}"
        run_dir = automation_root / base
        suffix = 1
        while run_dir.exists():
            run_dir = automation_root / f"{base}_{suffix:02d}"
            suffix += 1
        run_dir.mkdir(parents=True, exist_ok=False)

        obj = cls(
            project_root=root,
            config=dict(config or {}),
            language=str(language or "und"),
            script_hash=_script_sha256(script_text),
            run_id=run_dir.name,
            run_dir=run_dir,
        )
        obj.state.message = "Đang chuẩn bị quy trình tạo video tự động."
        obj.save()
        return obj

    @property
    def state_path(self) -> Path:
        return self.run_dir / RUN_FILENAME

    def save(self) -> Path:
        self.updated_at = _now_iso()
        payload = {
            "format": RUN_FORMAT,
            "run_id": self.run_id,
            "project_root": str(self.project_root),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "language": self.language,
            "script_sha256": self.script_hash,
            "config": _safe_json(self.config),
            "error": self.error,
            "workflow": self.state.to_dict(),
        }
        self.run_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{RUN_FILENAME}.",
            suffix=".tmp",
            dir=str(self.run_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(temp_name, self.state_path)
        except Exception:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except Exception:
                pass
            raise
        return self.state_path

    def begin(self) -> AutomationWorkflowState:
        self.status = AutomationRunStatus.RUNNING
        self.error = ""
        self.state.mark_completed("script", "Kịch bản đã được lưu vào dự án.")
        self.state.mark_running(
            "voice",
            "Đang tạo giọng đọc từ toàn bộ kịch bản...",
            progress=5,
        )
        self.state.message = "Đang tạo giọng đọc."
        self.save()
        return self.state

    def voice_completed(self, *, filename: str, duration_seconds: float = 0.0) -> AutomationWorkflowState:
        duration = max(0.0, float(duration_seconds or 0.0))
        detail = f"Đã tạo giọng đọc: {filename}"
        if duration:
            detail += f" · {duration:.1f} giây"
        self.state.mark_completed("voice", detail)
        self.state.mark_running(
            "voice_timing",
            "Đang chép lời và xác định mốc thời gian từ giọng đọc...",
            progress=10,
        )
        self.state.message = "Đang phân tích nội dung và thời gian giọng đọc."
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def voice_pipeline_completed(
        self,
        *,
        scene_count: int,
        duration_seconds: float = 0.0,
        run_name: str = "",
    ) -> AutomationWorkflowState:
        duration = max(0.0, float(duration_seconds or 0.0))
        timing_detail = "Đã hoàn tất nhận dạng lời nói và mốc thời gian."
        if duration:
            timing_detail += f" Thời lượng {duration:.1f} giây."
        self.state.mark_completed("voice_timing", timing_detail)
        scene_detail = f"Đã chia thành {max(0, int(scene_count))} cảnh."
        if run_name:
            scene_detail += f" Run: {run_name}."
        self.state.mark_completed("scene_analysis", scene_detail)
        self.state.mark_running(
            "media_search",
            "Đang phân tích từng cảnh để tạo truy vấn tìm ảnh & video...",
            progress=1,
        )
        self.state.message = "Đang tạo truy vấn tìm tư liệu cho từng cảnh."
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_query_progress(
        self,
        *,
        current: int,
        total: int,
        scene_id: str = "",
        primary_query: str = "",
    ) -> AutomationWorkflowState:
        total_i = max(1, int(total or 1))
        current_i = max(0, min(total_i, int(current or 0)))
        # Query planning is the first quarter of the media-search stage.
        stage_progress = max(1, min(25, int(round((current_i / total_i) * 25))))
        detail = f"Đang tạo truy vấn cho cảnh {current_i}/{total_i}"
        if scene_id:
            detail += f" · {scene_id}"
        if primary_query:
            detail += f" · {primary_query}"
        self.state.mark_running("media_search", detail, progress=stage_progress)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_query_activity(
        self,
        detail: str,
        *,
        progress: int = 1,
    ) -> AutomationWorkflowState:
        message = str(detail or "Đang phân tích nhóm cảnh...").strip()
        self.state.mark_running(
            "media_search",
            message,
            progress=max(1, min(25, int(progress or 1))),
        )
        self.state.message = message
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_query_plan_completed(
        self,
        *,
        scene_count: int,
        planned_count: int,
        reused_gap_count: int = 0,
        ai_count: int = 0,
        cache_hit_count: int = 0,
        fallback_count: int = 0,
        batch_request_count: int = 0,
        plan_filename: str = "visual_query_plan.json",
    ) -> AutomationWorkflowState:
        detail = (
            f"Đã tạo truy vấn cho {max(0, int(planned_count))}/{max(0, int(scene_count))} cảnh."
        )
        stats = []
        if ai_count:
            stats.append(f"AI {int(ai_count)}")
        if cache_hit_count:
            stats.append(f"cache {int(cache_hit_count)}")
        if fallback_count:
            stats.append(f"fallback {int(fallback_count)}")
        if batch_request_count:
            stats.append(f"{int(batch_request_count)} batch KIE")
        if stats:
            detail += " " + " · ".join(stats) + "."
        if reused_gap_count:
            detail += f" {int(reused_gap_count)} cảnh khoảng lặng sẽ tái sử dụng hình trước."
        detail += " Bước kế tiếp sẽ tìm trên Pexels, Pixabay và nguồn tham chiếu YouTube."
        self.state.mark_running("media_search", detail, progress=25)
        self.state.message = f"Đã tạo kế hoạch tìm tư liệu: {plan_filename}. Đang chuẩn bị tìm stock."
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_stock_progress(
        self,
        *,
        current: int,
        total: int,
        scene_id: str = "",
        phase: str = "searching",
    ) -> AutomationWorkflowState:
        total_i = max(1, int(total or 1))
        current_i = max(0, min(total_i, int(current or 0)))
        # Stock acquisition occupies the remaining 75% of media_search in M110.2.
        fraction = current_i / total_i
        progress = max(26, min(95, 25 + int(round(fraction * 70))))
        phase_text = {
            "searching": "Đang tìm Pexels/Pixabay",
            "validated": "Đã tải và kiểm tra",
            "cached": "Đã dùng media cache",
            "search_again": "Chưa tìm được stock phù hợp",
            "needs_review": "Cần nguồn fallback",
            "search_failed": "Không có kết quả stock",
            "download_failed": "Tải stock thất bại",
            "validation_failed": "Stock không đạt kiểm tra",
        }.get(str(phase or "").strip().lower(), str(phase or "Đang xử lý stock"))
        if current_i <= 0:
            detail = "Đang khởi động tìm Pexels/Pixabay..."
        else:
            detail = f"{phase_text} · cảnh {current_i}/{total_i}"
            if scene_id:
                detail += f" · {scene_id}"
        self.state.mark_running("media_search", detail, progress=progress)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_stock_completed(
        self,
        *,
        total_search_scenes: int,
        validated_count: int,
        assigned_count: int,
        unresolved_count: int,
        cache_hit_count: int = 0,
        provider_names: list[str] | tuple[str, ...] = (),
        continue_to_youtube: bool = False,
    ) -> AutomationWorkflowState:
        total = max(0, int(total_search_scenes or 0))
        validated = max(0, int(validated_count or 0))
        assigned = max(0, int(assigned_count or 0))
        unresolved = max(0, int(unresolved_count or 0))
        providers = ", ".join(str(item) for item in provider_names if str(item).strip())
        source_text = f" Nguồn: {providers}." if providers else ""
        cache_text = f" Cache hit: {int(cache_hit_count)}." if cache_hit_count else ""

        if not continue_to_youtube:
            # Preserve the public M110.2 contract for historical regression tests
            # and non-M110.3 callers.
            if unresolved == 0:
                self.state.mark_completed(
                    "media_search",
                    f"Pexels/Pixabay hoàn tất: {validated}/{total} cảnh có stock hợp lệ.{source_text}{cache_text}",
                )
                self.state.mark_completed(
                    "media_assignment",
                    f"Đã tự động gán tư liệu cho {assigned}/{total} cảnh tìm kiếm.",
                )
                self.state.message = (
                    "Stock media đã hoàn tất. M110.3 sẽ bổ sung YouTube Reference làm nguồn fallback/tham chiếu; "
                    "bước sản xuất tiếp theo là nhạc nền."
                )
            else:
                self.state.mark_running(
                    "media_search",
                    (
                        f"Pexels/Pixabay đã xử lý {validated}/{total} cảnh; "
                        f"còn {unresolved} cảnh chưa có stock phù hợp và sẽ chuyển sang YouTube Reference ở M110.3."
                        f"{source_text}{cache_text}"
                    ),
                    progress=95,
                )
                self.state.set_stage(
                    "media_assignment",
                    AutomationStageStatus.PENDING,
                    detail=f"Đã có tư liệu cho {assigned}/{total} cảnh; chờ fallback cho {unresolved} cảnh.",
                    progress=0,
                )
                self.state.message = (
                    f"Pexels/Pixabay hoàn tất; còn {unresolved} cảnh chờ YouTube Reference M110.3."
                )
            self.status = AutomationRunStatus.WAITING
            self.save()
            return self.state

        if unresolved == 0:
            detail = (
                f"Pexels/Pixabay đã có stock hợp lệ cho {validated}/{total} cảnh."
                f"{source_text}{cache_text} Đang kiểm tra xem có cảnh chất lượng thấp cần YouTube Reference hay không."
            )
            self.state.mark_completed(
                "media_assignment",
                f"Đã tự động gán tư liệu cho {assigned}/{total} cảnh tìm kiếm.",
            )
        else:
            detail = (
                f"Pexels/Pixabay đã xử lý {validated}/{total} cảnh; còn {unresolved} cảnh chưa có stock phù hợp."
                f"{source_text}{cache_text} Đang chuyển các cảnh cần thiết sang YouTube Reference."
            )
            self.state.set_stage(
                "media_assignment",
                AutomationStageStatus.PENDING,
                detail=f"Đã có tư liệu cho {assigned}/{total} cảnh; chờ fallback cho {unresolved} cảnh.",
                progress=0,
            )

        self.state.mark_running("media_search", detail, progress=95)
        self.state.message = "Stock đã hoàn tất. Đang kiểm tra YouTube Reference cho các cảnh chưa tốt."
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_youtube_progress(
        self,
        *,
        current: int,
        total: int,
        scene_id: str = "",
        query: str = "",
    ) -> AutomationWorkflowState:
        total_i = max(1, int(total or 1))
        current_i = max(0, min(total_i, int(current or 0)))
        progress = max(96, min(99, 95 + int(round((current_i / total_i) * 4))))
        detail = f"Đang tìm YouTube Reference · cảnh {current_i}/{total_i}"
        if scene_id:
            detail += f" · {scene_id}"
        if query:
            detail += f" · {query}"
        self.state.mark_running("media_search", detail, progress=progress)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_youtube_completed(
        self,
        *,
        target_count: int,
        searched_count: int,
        reference_scene_count: int,
        candidate_count: int,
        chapter_segment_count: int,
        unresolved_stock_count: int,
        weak_stock_count: int,
        missing_api_key: bool = False,
        error_count: int = 0,
        manifest_filename: str = "youtube_reference_manifest.json",
    ) -> AutomationWorkflowState:
        targets = max(0, int(target_count or 0))
        refs = max(0, int(reference_scene_count or 0))
        candidates = max(0, int(candidate_count or 0))
        segments = max(0, int(chapter_segment_count or 0))
        unresolved = max(0, int(unresolved_stock_count or 0))
        weak = max(0, int(weak_stock_count or 0))
        errors = max(0, int(error_count or 0))

        if targets == 0:
            self.state.mark_completed(
                "media_search",
                "Stock hiện tại đã đủ tốt; không cần mở rộng sang YouTube Reference.",
            )
            if unresolved == 0 and self.state.stage_status("media_assignment") != AutomationStageStatus.COMPLETED:
                self.state.mark_completed("media_assignment", "Tư liệu stock đã được gán đầy đủ.")
            self.state.message = "Tư liệu hình ảnh/video đã hoàn tất. Bước tiếp theo là nhạc nền."
            self.status = AutomationRunStatus.WAITING
        elif missing_api_key:
            detail = (
                f"YouTube Reference chưa được chạy vì chưa cấu hình YOUTUBE_API_KEY · "
                f"{weak} cảnh stock dưới ngưỡng · {unresolved} cảnh chưa có stock phù hợp."
            )
            self.state.mark_running("media_search", detail, progress=95)
            self.state.message = (
                "Cần cấu hình YOUTUBE_API_KEY để hoàn tất kiểm tra các cảnh stock yếu/chưa đủ."
            )
            self.status = AutomationRunStatus.WAITING
        elif errors > 0:
            detail = (
                f"YouTube Reference gặp lỗi ở {errors}/{targets} cảnh · "
                f"đã tìm {refs} cảnh có reference · {candidates} ứng viên · "
                f"{segments} đoạn timestamp. Stock render hiện có vẫn được giữ."
            )
            self.state.mark_running("media_search", detail, progress=99)
            self.state.message = (
                f"YouTube Reference chưa hoàn tất. Xem {manifest_filename} để biết HTTP/network reason rồi thử lại."
            )
            self.status = AutomationRunStatus.WAITING
        elif unresolved > 0:
            self.state.mark_running(
                "media_search",
                (
                    f"YouTube đã tìm reference cho {refs}/{targets} cảnh · {candidates} ứng viên · "
                    f"{segments} đoạn có timestamp. Còn {unresolved} cảnh chưa có render asset; "
                    "M110.4 sẽ dùng reference để cải thiện truy vấn và tìm lại stock."
                ),
                progress=99,
            )
            self.state.message = f"YouTube Reference đã lưu: {manifest_filename}. Chờ M110.4 re-search stock."
            self.status = AutomationRunStatus.WAITING
        else:
            detail = (
                f"YouTube Reference hoàn tất cho {refs}/{targets} cảnh cần kiểm tra · "
                f"{candidates} ứng viên · {segments} đoạn timestamp."
            )
            self.state.mark_completed("media_search", detail)
            if self.state.stage_status("media_assignment") != AutomationStageStatus.COMPLETED:
                self.state.mark_completed("media_assignment", "Tư liệu stock hiện tại đã được gán đầy đủ.")
            self.state.message = "Tư liệu hình ảnh/video đã hoàn tất. Bước tiếp theo là nhạc nền."
            self.status = AutomationRunStatus.WAITING

        self.save()
        return self.state


    def media_ranking_started(self, *, total_scene_count: int = 0) -> AutomationWorkflowState:
        total = max(0, int(total_scene_count or 0))
        detail = "Đang xếp hạng thống nhất giữa stock và YouTube Reference..."
        if total:
            detail += f" {total} cảnh."
        self.state.mark_running("media_search", detail, progress=99)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_ranking_progress(
        self,
        *,
        current: int,
        total: int,
        scene_id: str = "",
        action: str = "",
    ) -> AutomationWorkflowState:
        total_i = max(1, int(total or 1))
        current_i = max(0, min(total_i, int(current or 0)))
        action_text = {
            "keep_stock": "Giữ stock",
            "reference_guided_research": "Reference hướng dẫn tìm lại",
            "broaden_stock_search": "Mở rộng tìm stock",
        }.get(str(action or "").strip(), "Đang đánh giá")
        detail = f"Xếp hạng tư liệu · cảnh {current_i}/{total_i}"
        if scene_id:
            detail += f" · {scene_id}"
        detail += f" · {action_text}"
        self.state.mark_running("media_search", detail, progress=99)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_ranking_completed(
        self,
        *,
        total_scene_count: int,
        keep_stock_count: int,
        reference_guided_count: int,
        broaden_search_count: int,
        render_ready_count: int,
        unresolved_render_count: int,
        manifest_filename: str = "media_ranking_manifest.json",
    ) -> AutomationWorkflowState:
        total = max(0, int(total_scene_count or 0))
        keep = max(0, int(keep_stock_count or 0))
        guided = max(0, int(reference_guided_count or 0))
        broaden = max(0, int(broaden_search_count or 0))
        ready = max(0, int(render_ready_count or 0))
        unresolved = max(0, int(unresolved_render_count or 0))
        research = guided + broaden

        if unresolved == 0:
            if self.state.stage_status("media_assignment") != AutomationStageStatus.COMPLETED:
                self.state.mark_completed(
                    "media_assignment",
                    f"Đã có render-safe stock cho {ready}/{total} cảnh tìm kiếm.",
                )
        else:
            self.state.set_stage(
                "media_assignment",
                AutomationStageStatus.PENDING,
                detail=f"Đã có render-safe asset cho {ready}/{total} cảnh; còn {unresolved} cảnh cần tìm lại.",
                progress=0,
            )

        if research > 0:
            detail = (
                f"M110.4 đã xếp hạng {total} cảnh · giữ stock {keep} · "
                f"reference hướng dẫn {guided} · mở rộng stock {broaden}. "
                "YouTube vẫn chỉ là reference; M110.5 sẽ tự tìm lại nguồn render-safe cho các cảnh cần cải thiện."
            )
            self.state.mark_running("media_search", detail, progress=99)
            self.state.message = f"Đã lưu {manifest_filename}. Chờ M110.5 Automatic Fallback / Re-search."
        elif unresolved > 0:
            detail = (
                f"M110.4 đã xếp hạng {total} cảnh nhưng còn {unresolved} cảnh chưa có render asset. "
                "M110.5 sẽ tiếp tục fallback/re-search."
            )
            self.state.mark_running("media_search", detail, progress=99)
            self.state.message = f"Đã lưu {manifest_filename}. Chờ M110.5."
        else:
            self.state.mark_completed(
                "media_search",
                f"M110.4 xếp hạng hoàn tất: giữ stock {keep}/{total}; không cần tìm lại tư liệu.",
            )
            self.state.message = "Tư liệu hình ảnh/video đã hoàn tất. Bước tiếp theo là nhạc nền."

        self.status = AutomationRunStatus.WAITING
        self.save()
        return self.state

    def media_research_started(
        self,
        *,
        target_count: int,
    ) -> AutomationWorkflowState:
        total = max(0, int(target_count or 0))
        detail = (
            f"M110.5 đang tự tìm lại stock cho {total} cảnh cần cải thiện."
            if total
            else "M110.5 đang kiểm tra fallback tư liệu."
        )
        self.state.mark_running("media_search", detail, progress=99)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_research_progress(
        self,
        *,
        current: int,
        total: int,
        scene_id: str = "",
        phase: str = "",
    ) -> AutomationWorkflowState:
        total_i = max(1, int(total or 1))
        current_i = max(0, min(total_i, int(current or 0)))
        phase_text = {
            "searching": "Đang tìm lại stock",
            "validated": "Đã tải stock mới",
            "cached": "Đã dùng media cache",
            "improved": "Đã thay bằng stock tốt hơn",
            "render_asset_acquired": "Đã có render asset",
            "fallback_preserved": "Giữ stock cũ làm fallback",
            "still_unresolved": "Chưa có render asset",
            "search_again": "Đang mở rộng truy vấn",
        }.get(str(phase or "").strip(), str(phase or "Đang re-search"))
        detail = f"{phase_text} · cảnh {current_i}/{total_i}"
        if scene_id:
            detail += f" · {scene_id}"
        self.state.mark_running("media_search", detail, progress=99)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def media_research_completed(
        self,
        *,
        total_scene_count: int,
        target_count: int,
        improved_count: int,
        acquired_count: int,
        fallback_preserved_count: int,
        unresolved_count: int,
        manifest_filename: str = "media_research_manifest.json",
    ) -> AutomationWorkflowState:
        total = max(0, int(total_scene_count or 0))
        targets = max(0, int(target_count or 0))
        improved = max(0, int(improved_count or 0))
        acquired = max(0, int(acquired_count or 0))
        preserved = max(0, int(fallback_preserved_count or 0))
        unresolved = max(0, int(unresolved_count or 0))

        if unresolved == 0:
            self.state.mark_completed(
                "media_search",
                (
                    f"M110.5 hoàn tất {targets} cảnh cần cải thiện · "
                    f"tốt hơn {improved} · bổ sung asset {acquired} · giữ fallback {preserved}."
                ),
            )
            self.state.mark_completed(
                "media_assignment",
                f"Đã có render-safe asset cho {total}/{total} cảnh tìm kiếm.",
            )
            self.state.message = (
                f"Đã lưu {manifest_filename}. Tư liệu hình ảnh/video đã sẵn sàng; "
                "bước tiếp theo là nhạc nền."
            )
        else:
            self.state.mark_running(
                "media_search",
                (
                    f"M110.5 đã re-search {targets} cảnh nhưng còn {unresolved} cảnh chưa có "
                    "render-safe asset. M110.6 sẽ xử lý fallback cuối cùng."
                ),
                progress=99,
            )
            self.state.set_stage(
                "media_assignment",
                AutomationStageStatus.PENDING,
                detail=f"Còn {unresolved} cảnh chưa có render-safe asset.",
                progress=0,
            )
            self.state.message = f"Đã lưu {manifest_filename}. Chờ M110.6 Scene → Renderable Asset."

        self.status = AutomationRunStatus.WAITING
        self.save()
        return self.state

    def final_renderable_started(
        self,
        *,
        total_scene_count: int = 0,
    ) -> AutomationWorkflowState:
        total = max(0, int(total_scene_count or 0))
        detail = "M110.6 đang chốt asset render cuối cùng cho từng cảnh."
        if total:
            detail += f" {total} cảnh."
        self.state.mark_running("media_assignment", detail, progress=99)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def final_renderable_progress(
        self,
        *,
        current: int,
        total: int,
        scene_id: str = "",
        status: str = "",
    ) -> AutomationWorkflowState:
        total_i = max(1, int(total or 1))
        current_i = max(0, min(total_i, int(current or 0)))
        label = {
            "ready": "Đã chốt render asset",
            "unresolved": "Cảnh chưa sẵn sàng render",
        }.get(str(status or "").strip(), "Đang xác minh render asset")
        detail = f"{label} · cảnh {current_i}/{total_i}"
        if scene_id:
            detail += f" · {scene_id}"
        self.state.mark_running("media_assignment", detail, progress=99)
        self.state.message = detail
        self.status = AutomationRunStatus.RUNNING
        self.save()
        return self.state

    def final_renderable_completed(
        self,
        *,
        total_scene_count: int,
        ready_count: int,
        unresolved_count: int,
        video_count: int,
        image_count: int,
        manifest_filename: str = "final_renderable_assets.json",
    ) -> AutomationWorkflowState:
        total = max(0, int(total_scene_count or 0))
        ready = max(0, int(ready_count or 0))
        unresolved = max(0, int(unresolved_count or 0))
        videos = max(0, int(video_count or 0))
        images = max(0, int(image_count or 0))

        if unresolved == 0 and ready == total:
            self.state.mark_completed(
                "media_search",
                f"Tìm kiếm/xếp hạng tư liệu hoàn tất cho {total} cảnh.",
            )
            self.state.mark_completed(
                "media_assignment",
                f"M110.6 đã chốt {ready}/{total} render asset · video {videos} · ảnh {images}.",
            )
            self.state.message = (
                f"Đã lưu {manifest_filename}. Tư liệu cuối cùng đã sẵn sàng; "
                "bước tiếp theo là nhạc nền."
            )
        else:
            self.state.mark_running(
                "media_search",
                f"M110.6 còn {unresolved}/{total} cảnh chưa có render asset hợp lệ.",
                progress=99,
            )
            self.state.set_stage(
                "media_assignment",
                AutomationStageStatus.PENDING,
                detail=f"Đã chốt {ready}/{total}; còn {unresolved} cảnh cần xử lý.",
                progress=0,
            )
            self.state.message = f"Đã lưu {manifest_filename}. Cần xử lý các cảnh unresolved trước khi dựng video."

        self.status = AutomationRunStatus.WAITING
        self.save()
        return self.state

    def fail(self, stage_key: str, detail: str) -> AutomationWorkflowState:
        message = str(detail or "Không rõ lỗi.").strip()
        self.state.mark_failed(stage_key, message)
        self.state.message = f"Quy trình dừng tại bước lỗi: {message}"
        self.status = AutomationRunStatus.FAILED
        self.error = message
        self.save()
        return self.state

    def cancel(self, detail: str = "Đã nhận yêu cầu hủy.") -> AutomationWorkflowState:
        current = self.state.current_stage_key()
        if current is not None:
            self.state.set_stage(
                current,
                AutomationStageStatus.CANCELLED,
                detail=str(detail),
            )
        self.state.message = str(detail)
        self.status = AutomationRunStatus.CANCELLED
        self.save()
        return self.state

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))
