"""Manual export controls for previously assembled Creator Studio timelines."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from creator_studio.manual_export import find_ready_timelines
from creator_studio.render_backend import RenderBackendCancelled, RenderCancellationToken
from creator_studio.render_export import RenderExportService
from creator_studio.render_readiness import require_render_ready


class ManualExportWorker(QThread):
    progress = pyqtSignal(str, float, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal(str)

    def __init__(self, timeline_path: Path, project_root: Path, parent=None):
        super().__init__(parent)
        self.timeline_path = Path(timeline_path)
        self.project_root = Path(project_root)
        self.cancel_token = RenderCancellationToken()

    def request_cancel(self):
        self.cancel_token.cancel()

    def run(self):
        try:
            result = RenderExportService().export(
                self.timeline_path,
                self.project_root,
                cancel_token=self.cancel_token,
                progress_callback=lambda event: self.progress.emit(
                    str(event.phase), float(event.percent), str(event.detail)
                ),
            )
        except RenderBackendCancelled as exc:
            self.cancelled.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.succeeded.emit(result)


class ManualExportPage(QWidget):
    """Nonblocking manual re-export of an existing ready timeline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: Path | None = None
        self._worker: ManualExportWorker | None = None
        self._output: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)
        title = QLabel("Xuất video thủ công")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        description = QLabel(
            "Chọn timeline đã tạo từ quy trình tự động để xuất lại MP4. "
            "Video cũ được giữ nguyên; mỗi lần xuất dùng tên mới."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        row = QHBoxLayout()
        self.timeline_combo = QComboBox()
        self.timeline_combo.setMinimumWidth(340)
        self.refresh_button = QPushButton("Làm mới danh sách")
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.timeline_combo, 1)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self.render_button = QPushButton("Xuất MP4")
        self.render_button.setProperty("class", "primaryButton")
        self.render_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("Hủy xuất")
        self.cancel_button.clicked.connect(self.cancel_export)
        self.open_button = QPushButton("Mở video")
        self.open_button.clicked.connect(self._open_output)
        self.folder_button = QPushButton("Mở thư mục xuất")
        self.folder_button.clicked.connect(self._open_folder)
        for button in (self.render_button, self.cancel_button, self.open_button, self.folder_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Hãy mở dự án và chọn timeline đã sẵn sàng.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.refresh()

    def set_project(self, manifest, manifest_path):
        self._root = Path(manifest_path).parent.resolve() if manifest_path is not None else None
        self._output = None
        if not self.is_exporting():
            self.refresh()

    def is_exporting(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def refresh(self):
        if self.is_exporting():
            return
        previous = self.timeline_combo.currentData()
        self.timeline_combo.clear()
        if self._root is not None:
            for path in find_ready_timelines(self._root):
                self.timeline_combo.addItem(path.parent.name, str(path))
        index = self.timeline_combo.findData(previous)
        if index >= 0:
            self.timeline_combo.setCurrentIndex(index)
        available = self._root is not None and self.timeline_combo.count() > 0
        self.render_button.setEnabled(available)
        self.timeline_combo.setEnabled(available)
        self.cancel_button.setEnabled(False)
        self.open_button.setEnabled(self._output is not None and self._output.is_file())
        self.folder_button.setEnabled(self._root is not None)
        if not available:
            self.status_label.setText(
                "Không có timeline sẵn sàng. Hãy tạo video tự động trước."
                if self._root is not None else "Hãy mở hoặc tạo dự án trước."
            )

    def _start(self):
        if self.is_exporting() or self._root is None:
            return
        value = self.timeline_combo.currentData()
        if not value:
            return
        path = Path(str(value))
        try:
            require_render_ready(path, self._root)
        except Exception as exc:
            self.status_label.setText(f"Timeline chưa sẵn sàng: {exc}")
            return

        self._output = None
        self.progress_bar.setValue(0)
        self.status_label.setText("Đang xuất video...")
        self.render_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.timeline_combo.setEnabled(False)
        self.open_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        worker = ManualExportWorker(path, self._root, parent=self)
        self._worker = worker
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_finished)
        worker.start()

    def cancel_export(self):
        if self.is_exporting() and self._worker is not None:
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Đang yêu cầu hủy xuất video...")

    def _on_progress(self, phase: str, percent: float, detail: str):
        self.progress_bar.setValue(max(0, min(100, int(percent))))
        self.status_label.setText(f"{phase}: {detail}")

    def _on_success(self, result):
        self._output = Path(result.output_path)
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Đã xuất video: {self._output}")
        self.open_button.setEnabled(self._output.is_file())

    def _on_error(self, message: str):
        self.status_label.setText(f"Xuất video thất bại: {message}")
        QMessageBox.warning(self, "Xuất video", message)

    def _on_cancelled(self, message: str):
        self.status_label.setText("Đã hủy xuất video. " + message)

    def _on_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.refresh_button.setEnabled(True)
        self.refresh()

    def _open_output(self):
        if self._output is not None and self._output.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._output)))

    def _open_folder(self):
        folder = self._output.parent if self._output is not None else (
            self._root / "exports" if self._root is not None else None
        )
        if folder is not None and folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
