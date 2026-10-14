
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.api_key_manager import APIKeyManager
from api_keys_dialog import APIKeysDialog
from creator_studio.provider_diagnostics_host.gui_api import (
    ProviderDiagnosticsRemoteImageSource,
    ProviderDiagnosticsRequestBuilder,
)
from creator_studio.provider_diagnostics_host.runtime_api import (
    ProviderDiagnosticsHost,
)
from creator_studio.provider_diagnostics_qt_view.public_api import (
    ProviderDiagnosticsQtView,
)
from creator_studio.provider_diagnostics_qt_view.binding_api import (
    ProviderDiagnosticsQtViewBinder,
)
from creator_studio.provider_diagnostics_qt_worker.public_api import (
    ProviderDiagnosticsQtThreadBridge,
)
from creator_studio.provider_diagnostics_view_model.public_api import (
    ProviderDiagnosticsViewAction,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)

from creator_studio.manifest.models import ProjectManifest
from creator_studio.manifest.persistence import (
    PersistenceError,
    load as load_project_manifest,
    save as save_project_manifest,
)


ROOT = Path(__file__).resolve().parent

WORKSPACES_ROOT = ROOT / "projects" / "workspaces"
UI_STATE_FILE = ROOT / "config" / "creator_studio_ui_state.json"
PROJECT_MANIFEST_FILENAME = "project_manifest.json"

APP_NAME = "AI Video Editor"
APP_SUBTITLE = "Creator Studio"


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    short: str


NAV_ITEMS = [
    NavItem("dashboard", "Tổng quan", "D"),
    NavItem("project", "Dự án", "P"),
    NavItem("voice", "Giọng đọc + Kịch bản", "V"),
    NavItem("scenes", "Cảnh", "S"),
    NavItem("media", "Tìm tư liệu", "M"),
    NavItem("vision", "AI hình ảnh", "AI"),
    NavItem("timeline", "Dòng thời gian", "T"),
    NavItem("export", "Xuất video", "E"),
    NavItem("diagnostics", "Chẩn đoán", "DX"),
    NavItem("settings", "Cài đặt", "ST"),
]




DIAGNOSTICS_VIEW_STYLE = r"""
QWidget {
    background: transparent;
    color: #e8eef6;
}
QLabel {
    background: transparent;
    color: #e8eef6;
}
QPushButton {
    background: #2d7ff9;
    color: white;
    border: 1px solid #3d8cff;
    border-radius: 7px;
    padding: 8px 14px;
    font-weight: 600;
    min-height: 18px;
}
QPushButton:hover {
    background: #4894ff;
    border: 1px solid #80b4ff;
}
QPushButton:pressed {
    background: #1f62c7;
    border: 1px solid #a7d1ff;
    padding-top: 9px;
    padding-bottom: 7px;
}
QPushButton:focus {
    border: 2px solid #a7d1ff;
}
QPushButton:disabled {
    background: #202936;
    color: #6f7f94;
    border: 1px solid #2b3747;
}
QProgressBar {
    background: #0b0f14;
    color: #dce8f5;
    border: 1px solid #2b3747;
    border-radius: 5px;
    text-align: center;
}
QProgressBar::chunk {
    background: #2d7ff9;
    border-radius: 4px;
}
"""


API_DIALOG_STYLE = r"""
QDialog {
    background: #0f141b;
    color: #e8eef6;
}
QWidget {
    color: #e8eef6;
}
QLabel {
    background: transparent;
    color: #dce6f2;
}
QListWidget {
    background: #0b0f14;
    color: #dce6f2;
    border: 1px solid #2a3544;
    border-radius: 7px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 5px;
}
QListWidget::item:selected {
    background: #1d3857;
    color: #ffffff;
}
QListWidget::item:hover {
    background: #172331;
}
QLineEdit {
    background: #0b0f14;
    color: #eef4fb;
    border: 1px solid #2a3544;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #2d7ff9;
}
QLineEdit:focus {
    border: 1px solid #5da9ff;
}
QLineEdit:disabled {
    background: #111821;
    color: #718197;
    border-color: #232e3c;
}
QCheckBox {
    background: transparent;
    color: #dce6f2;
    spacing: 7px;
}
QPushButton {
    background: #151d27;
    color: #dce6f2;
    border: 1px solid #2a3544;
    border-radius: 7px;
    padding: 7px 12px;
    min-height: 20px;
}
QPushButton:hover {
    background: #223247;
    color: #ffffff;
    border-color: #5b7da5;
}
QPushButton:pressed {
    background: #0d1722;
    color: #ffffff;
    border-color: #78ade8;
    padding-top: 8px;
    padding-bottom: 6px;
}
QPushButton:focus {
    border: 2px solid #6eaef2;
}
QPushButton:disabled {
    background: #111821;
    color: #657589;
    border-color: #202a36;
}
QSplitter::handle {
    background: #202936;
}
QScrollBar:vertical {
    background: #0f141b;
    width: 11px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
"""

APP_STYLE = """
QMainWindow {
    background: #0b0f14;
}

QWidget {
    color: #e8eef6;
    font-family: "Segoe UI";
    font-size: 13px;
}

QLabel {
    background: transparent;
}

QPushButton {
    outline: none;
}

QFrame#sidebar {
    background: #0f141b;
    border-right: 1px solid #202936;
}

QFrame#topbar {
    background: #0d1218;
    border-bottom: 1px solid #202936;
}

QFrame#footer {
    background: #0d1218;
    border-top: 1px solid #202936;
}

QFrame[class="card"] {
    background: #121923;
    border: 1px solid #222d3a;
    border-radius: 12px;
}

QFrame[class="card"]:hover {
    border: 1px solid #314056;
}

QLabel#brand {
    color: #f4f8fc;
    font-size: 18px;
    font-weight: 700;
}

QLabel#brandSub {
    color: #7f8ea3;
    font-size: 11px;
}

QLabel#pageTitle {
    color: #f6f9fc;
    font-size: 22px;
    font-weight: 700;
}

QLabel#pageSubtitle {
    color: #8190a6;
    font-size: 12px;
}

QLabel#cardTitle {
    color: #96a5ba;
    font-size: 11px;
    font-weight: 600;
}

QLabel#metricValue {
    color: #f6f9fc;
    font-size: 26px;
    font-weight: 700;
}

QLabel#metricHint {
    color: #77879d;
    font-size: 11px;
}

QLabel#sectionTitle {
    color: #f4f7fb;
    font-size: 15px;
    font-weight: 700;
}

QLabel#muted {
    color: #7e8da3;
}

QLabel#statusGood {
    color: #5dd39e;
    font-weight: 600;
}

QLabel#statusWarn {
    color: #f5bd60;
    font-weight: 600;
}

QLabel#statusIdle {
    color: #8190a6;
    font-weight: 600;
}

QLabel#statusBad {
    color: #ff7b72;
    font-weight: 600;
}

QLabel#projectValue {
    color: #eef4fb;
    font-size: 14px;
    font-weight: 600;
}

QLabel#projectPath {
    color: #9fb0c5;
    font-family: "Consolas";
    font-size: 12px;
}

QFrame#diagnosticsHost {
    background: #0f151d;
    border: 1px solid #243142;
    border-radius: 10px;
}

QPushButton[class="navButton"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #9fb0c5;
    text-align: left;
    padding: 11px 12px;
    font-size: 13px;
}

QPushButton[class="navButton"]:hover {
    background: #1a2a3d;
    color: #ffffff;
    border: 1px solid #2f4d70;
}

QPushButton[class="navButton"]:pressed {
    background: #0e1d2c;
    color: #ffffff;
    border: 1px solid #5da9ff;
    padding-top: 12px;
    padding-bottom: 10px;
}

QPushButton[class="navButton"][selected="true"] {
    background: #1d3857;
    color: #ffffff;
    border: 1px solid #345f8c;
    border-left: 4px solid #62b0ff;
    padding-left: 8px;
    font-weight: 700;
}

QPushButton[class="navButton"][selected="true"]:hover {
    background: #24486f;
    border-color: #4f82b5;
    border-left: 4px solid #8ac8ff;
}

QPushButton[class="navButton"][selected="true"]:pressed {
    background: #142b43;
    border-color: #79bdff;
    border-left: 4px solid #a4d5ff;
}

QPushButton[class="primaryButton"] {
    background: #2d7ff9;
    color: white;
    border: 1px solid #5598ff;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 700;
}

QPushButton[class="primaryButton"]:hover {
    background: #4894ff;
    border: 1px solid #80b4ff;
}

QPushButton[class="primaryButton"]:pressed {
    background: #1f62c7;
    border: 1px solid #9bc5ff;
    padding-top: 10px;
    padding-bottom: 8px;
}

QPushButton[class="primaryButton"]:focus {
    border: 2px solid #a7d1ff;
}

QPushButton[class="primaryButton"]:disabled {
    background: #202936;
    color: #66778c;
    border: 1px solid #2b3747;
}

QPushButton[class="secondaryButton"] {
    background: #151d27;
    color: #d9e4f0;
    border: 1px solid #33445a;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}

QPushButton[class="secondaryButton"]:hover {
    background: #223247;
    color: #ffffff;
    border: 1px solid #5b7da5;
}

QPushButton[class="secondaryButton"]:pressed {
    background: #0e1824;
    color: #ffffff;
    border: 1px solid #78adE8;
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton[class="secondaryButton"]:focus {
    border: 2px solid #6eaef2;
}

QPushButton[class="secondaryButton"]:disabled {
    background: #111821;
    color: #5f6f83;
    border: 1px solid #222d3a;
}

QPushButton[class="projectButton"] {
    background: #121923;
    color: #d8e2ef;
    border: 1px solid #33445a;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}

QPushButton[class="projectButton"]:hover {
    background: #203149;
    color: #ffffff;
    border: 1px solid #5b7da5;
}

QPushButton[class="projectButton"]:pressed {
    background: #0e1824;
    border: 1px solid #78ade8;
    padding-top: 9px;
    padding-bottom: 7px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}
"""


def _object_has_non_default_state(value) -> bool:
    if value is None:
        return False

    try:
        default_value = type(value)()
    except Exception:
        return bool(value)

    try:
        return value != default_value
    except Exception:
        return bool(value)


def _safe_workspace_slug(project_name: str) -> str:
    normalized = unicodedata.normalize("NFKD", project_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")
    return slug[:64] or "project"


def _translate_button_texts(root: QWidget) -> None:
    """Translate known embedded/legacy button captions without changing engine code."""
    translations = {
        "Run Diagnostics": "Chạy chẩn đoán",
        "Cancel": "Hủy",
        "+ Add Provider": "+ Thêm nhà cung cấp",
        "Delete Provider": "Xóa nhà cung cấp",
        "SAVE PROVIDER": "LƯU NHÀ CUNG CẤP",
        "Save Provider": "Lưu nhà cung cấp",
        "Close": "Đóng",
        "Settings": "Cài đặt",
    }
    for button in root.findChildren(QPushButton):
        translated = translations.get(button.text())
        if translated:
            button.setText(translated)
        button.setCursor(Qt.CursorShape.PointingHandCursor)


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")


class MetricCard(Card):
    def __init__(self, title: str, value: str, hint: str, status: str = "idle"):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title.upper())
        title_label.setObjectName("cardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")

        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("metricHint")
        self.hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.hint_label)
        layout.addStretch(1)

        self.set_metric(value, hint, status)

    def set_metric(self, value: str, hint: str, status: str = "idle"):
        self.value_label.setText(str(value))
        self.hint_label.setText(str(hint))

        color = {
            "good": "#5dd39e",
            "warn": "#f5bd60",
            "bad": "#ff7b72",
        }.get(status, "#f6f9fc")

        self.value_label.setStyleSheet(f"color: {color};")


class WorkflowRow(QWidget):
    def __init__(self, name: str, detail: str, status_text: str, status_kind: str):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: 600; color: #e6edf6;")

        detail_label = QLabel(detail)
        detail_label.setObjectName("muted")

        status_label = QLabel(status_text)
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.detail_label = detail_label
        self.status_label = status_label

        self.set_status(status_text, status_kind)

        left.addWidget(name_label)
        left.addWidget(detail_label)

        layout.addLayout(left, 1)
        layout.addWidget(status_label)

    def set_status(self, status_text: str, status_kind: str = "idle", detail: str | None = None):
        self.status_label.setText(status_text)

        object_name = {
            "good": "statusGood",
            "warn": "statusWarn",
            "bad": "statusBad",
        }.get(status_kind, "statusIdle")

        self.status_label.setObjectName(object_name)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if detail is not None:
            self.detail_label.setText(detail)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 28)
        content_layout.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(12)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)

        title = QLabel("Tổng quan")
        title.setObjectName("pageTitle")

        subtitle = QLabel("Tổng quan quy trình sản xuất video hiện tại.")
        subtitle.setObjectName("pageSubtitle")

        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        self.continue_button = QPushButton("Tạo hoặc mở dự án")
        self.continue_button.setProperty("class", "primaryButton")
        self.continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_button.setMinimumHeight(38)
        self.continue_button.clicked.connect(
            lambda: self.window().navigate_to("project")
            if hasattr(self.window(), "navigate_to")
            else None
        )

        header.addLayout(header_text, 1)
        header.addWidget(self.continue_button, 0, Qt.AlignmentFlag.AlignVCenter)

        content_layout.addLayout(header)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        metrics.setVerticalSpacing(14)

        self.voice_metric = MetricCard(
            "Voice",
            "Not set",
            "Chưa mở dự án",
            "idle",
        )
        self.scenes_metric = MetricCard(
            "Cảnh",
            "0",
            "Chưa mở dự án",
            "idle",
        )
        self.media_metric = MetricCard(
            "Media",
            "0",
            "Chưa mở dự án",
            "idle",
        )
        self.export_metric = MetricCard(
            "Xuất video",
            "Chưa sẵn sàng",
            "Chưa mở dự án",
            "warn",
        )

        metrics.addWidget(self.voice_metric, 0, 0)
        metrics.addWidget(self.scenes_metric, 0, 1)
        metrics.addWidget(self.media_metric, 0, 2)
        metrics.addWidget(self.export_metric, 0, 3)

        for column in range(4):
            metrics.setColumnStretch(column, 1)

        content_layout.addLayout(metrics)

        lower = QGridLayout()
        lower.setHorizontalSpacing(14)
        lower.setVerticalSpacing(14)
        lower.setColumnStretch(0, 3)
        lower.setColumnStretch(1, 2)

        workflow_card = Card()
        workflow_layout = QVBoxLayout(workflow_card)
        workflow_layout.setContentsMargins(18, 16, 18, 18)
        workflow_layout.setSpacing(4)

        workflow_title = QLabel("Quy trình sản xuất")
        workflow_title.setObjectName("sectionTitle")

        workflow_sub = QLabel("Each module will be connected to the existing engine in later steps.")
        workflow_sub.setObjectName("muted")
        workflow_sub.setWordWrap(True)

        workflow_layout.addWidget(workflow_title)
        workflow_layout.addWidget(workflow_sub)
        workflow_layout.addSpacing(6)

        rows = [
            ("Dự án", "Create or open a production project", "Chưa bắt đầu", "idle"),
            ("Giọng đọc & Kịch bản", "Import voice, transcript and script", "Đang chờ", "idle"),
            ("Cảnh", "Generate and review scene plan", "Đang chờ", "idle"),
            ("Tìm tư liệu", "Find and assign stock/local media", "Đang chờ", "idle"),
            ("Dòng thời gian", "Synchronize media with narration", "Đang chờ", "idle"),
            ("Xuất video", "Render the final video", "Đang chờ", "idle"),
        ]

        self.workflow_rows: dict[str, WorkflowRow] = {}

        for index, row in enumerate(rows):
            row_widget = WorkflowRow(*row)
            self.workflow_rows[row[0]] = row_widget
            workflow_layout.addWidget(row_widget)
            if index < len(rows) - 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.Shape.HLine)
                divider.setStyleSheet("color: #202b38;")
                workflow_layout.addWidget(divider)

        system_card = Card()
        system_layout = QVBoxLayout(system_card)
        system_layout.setContentsMargins(18, 16, 18, 18)
        system_layout.setSpacing(12)

        system_title = QLabel("Trạng thái hệ thống")
        system_title.setObjectName("sectionTitle")

        system_sub = QLabel(
            "Creator Studio now hosts the existing M100 diagnostics stack "
            "without replacing the tested diagnostics engine."
        )
        system_sub.setObjectName("muted")
        system_sub.setWordWrap(True)

        system_layout.addWidget(system_title)
        system_layout.addWidget(system_sub)
        system_layout.addSpacing(6)

        system_layout.addWidget(
            WorkflowRow("Giao diện ứng dụng", "Creator Studio shell", "Ready", "good")
        )

        self.provider_diagnostics_row = WorkflowRow(
            "Chẩn đoán nhà cung cấp",
            "M100 host / M99 view / M98 worker",
            "Sẵn sàng chạy",
            "idle",
        )
        system_layout.addWidget(self.provider_diagnostics_row)

        system_layout.addWidget(
            WorkflowRow("Pipeline xử lý", "Existing production engine", "Untouched", "good")
        )

        system_layout.addStretch(1)

        diagnostics_button = QPushButton("Mở chẩn đoán")
        diagnostics_button.setProperty("class", "secondaryButton")
        diagnostics_button.setMinimumHeight(36)
        diagnostics_button.clicked.connect(
            lambda: self.window().navigate_to("diagnostics")
            if hasattr(self.window(), "navigate_to")
            else None
        )
        system_layout.addWidget(diagnostics_button)

        lower.addWidget(workflow_card, 0, 0)
        lower.addWidget(system_card, 0, 1)

        content_layout.addLayout(lower)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)



    def set_provider_diagnostics_status(
        self,
        status_text: str,
        status_kind: str = "idle",
        detail: str | None = None,
    ):
        self.provider_diagnostics_row.set_status(
            status_text,
            status_kind,
            detail,
        )

    def set_project_status(
        self,
        manifest: ProjectManifest | None,
        manifest_path: Path | None,
    ):
        if manifest is None:
            self.continue_button.setText("Create or Open Project")
            self.voice_metric.set_metric("Not set", "Chưa mở dự án", "idle")
            self.scenes_metric.set_metric("0", "Chưa mở dự án", "idle")
            self.media_metric.set_metric("0", "Chưa mở dự án", "idle")
            self.export_metric.set_metric(
                "Chưa sẵn sàng",
                "Chưa mở dự án",
                "warn",
            )

            project_row = self.workflow_rows.get("Dự án")
            if project_row is not None:
                project_row.set_status(
                    "Chưa bắt đầu",
                    "idle",
                    "Create or open a production project",
                )
            return

        self.continue_button.setText("Tiếp tục dự án")

        voice_ready = _object_has_non_default_state(
            getattr(manifest, "voice", None)
        )
        scenes_count = len(getattr(manifest, "scenes", []) or [])
        media_count = len(getattr(manifest, "media", []) or [])
        timeline_count = len(getattr(manifest, "timeline", []) or [])
        render_ready = _object_has_non_default_state(
            getattr(manifest, "render_preparation", None)
        )

        self.voice_metric.set_metric(
            "Configured" if voice_ready else "Not set",
            "Project voice state",
            "good" if voice_ready else "idle",
        )
        self.scenes_metric.set_metric(
            str(scenes_count),
            "Scenes in ProjectManifest",
            "good" if scenes_count else "idle",
        )
        self.media_metric.set_metric(
            str(media_count),
            "Media references in ProjectManifest",
            "good" if media_count else "idle",
        )

        if render_ready:
            export_text = "Ready"
            export_hint = "Render preparation state is present"
            export_kind = "good"
        elif timeline_count:
            export_text = "Timeline ready"
            export_hint = f"{timeline_count} timeline reference(s)"
            export_kind = "warn"
        else:
            export_text = "Chưa sẵn sàng"
            export_hint = "Chưa tạo dòng thời gian"
            export_kind = "warn"

        self.export_metric.set_metric(
            export_text,
            export_hint,
            export_kind,
        )

        project_row = self.workflow_rows.get("Dự án")
        if project_row is not None:
            project_row.set_status(
                "Loaded",
                "good",
                manifest.project_name,
            )


class ProjectWorkspacePage(QWidget):
    def __init__(
        self,
        create_callback,
        open_callback,
        save_callback,
        open_folder_callback,
    ):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(3)

        title = QLabel("Dự án")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Tạo và quản lý dự án Creator Studio sử dụng ProjectManifest làm dữ liệu chính."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        actions = Card()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(16, 14, 16, 14)
        actions_layout.setSpacing(10)

        self.new_button = QPushButton("Tạo dự án mới")
        self.new_button.setProperty("class", "primaryButton")
        self.new_button.setMinimumHeight(38)
        self.new_button.clicked.connect(create_callback)

        self.open_button = QPushButton("Mở dự án")
        self.open_button.setProperty("class", "secondaryButton")
        self.open_button.setMinimumHeight(38)
        self.open_button.clicked.connect(open_callback)

        self.save_button = QPushButton("Lưu dự án")
        self.save_button.setProperty("class", "secondaryButton")
        self.save_button.setMinimumHeight(38)
        self.save_button.clicked.connect(save_callback)

        self.open_folder_button = QPushButton("Mở thư mục dự án")
        self.open_folder_button.setProperty("class", "secondaryButton")
        self.open_folder_button.setMinimumHeight(38)
        self.open_folder_button.clicked.connect(open_folder_callback)

        actions_layout.addWidget(self.new_button)
        actions_layout.addWidget(self.open_button)
        actions_layout.addWidget(self.save_button)
        actions_layout.addWidget(self.open_folder_button)
        actions_layout.addStretch(1)

        layout.addWidget(actions)

        self.notice = QLabel("No project loaded.")
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)

        info_card = Card()
        info_layout = QGridLayout(info_card)
        info_layout.setContentsMargins(20, 18, 20, 20)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(12)

        info_title = QLabel("Dự án hiện tại")
        info_title.setObjectName("sectionTitle")
        info_layout.addWidget(info_title, 0, 0, 1, 2)

        self.project_name_value = self._make_value("-")
        self.project_status_value = self._make_value("-")
        self.project_id_value = self._make_value("-")
        self.project_schema_value = self._make_value("-")
        self.project_path_value = self._make_value("-", path=True)
        self.project_path_value.setWordWrap(True)
        self.project_path_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        rows = [
            ("Tên dự án", self.project_name_value),
            ("Trạng thái", self.project_status_value),
            ("Mã dự án", self.project_id_value),
            ("Phiên bản schema", self.project_schema_value),
            ("Tệp manifest", self.project_path_value),
        ]

        for row_index, (label_text, value_widget) in enumerate(rows, start=1):
            label = QLabel(label_text)
            label.setObjectName("muted")
            info_layout.addWidget(label, row_index, 0)
            info_layout.addWidget(value_widget, row_index, 1)

        info_layout.setColumnStretch(0, 0)
        info_layout.setColumnStretch(1, 1)

        layout.addWidget(info_card)

        summary_card = Card()
        summary_layout = QGridLayout(summary_card)
        summary_layout.setContentsMargins(20, 18, 20, 20)
        summary_layout.setHorizontalSpacing(14)
        summary_layout.setVerticalSpacing(14)

        summary_title = QLabel("Tóm tắt dự án")
        summary_title.setObjectName("sectionTitle")
        summary_layout.addWidget(summary_title, 0, 0, 1, 4)

        self.scenes_value = self._summary_metric("Cảnh", "0")
        self.media_value = self._summary_metric("Media", "0")
        self.timeline_value = self._summary_metric("Dòng thời gian", "0")
        self.inputs_value = self._summary_metric("Inputs", "0")

        for index, widget in enumerate(
            [
                self.scenes_value,
                self.media_value,
                self.timeline_value,
                self.inputs_value,
            ]
        ):
            summary_layout.addWidget(widget, 1, index)
            summary_layout.setColumnStretch(index, 1)

        layout.addWidget(summary_card)

        note_card = Card()
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(20, 18, 20, 20)
        note_layout.setSpacing(8)

        note_title = QLabel("Lưu trữ dữ liệu")
        note_title.setObjectName("sectionTitle")

        note_text = QLabel(
            "Projects use creator_studio.manifest.persistence. Saving validates "
            "ProjectManifest and keeps the previous valid revision as "
            "project_manifest.json.bak when overwriting an existing project."
        )
        note_text.setObjectName("muted")
        note_text.setWordWrap(True)

        note_layout.addWidget(note_title)
        note_layout.addWidget(note_text)

        layout.addWidget(note_card)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)

        self.set_project(None, None)

    @staticmethod
    def _make_value(text: str, path: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName("projectPath" if path else "projectValue")
        return label

    @staticmethod
    def _summary_metric(title: str, value: str) -> Card:
        card = Card()
        card.setMinimumHeight(92)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        title_label = QLabel(title.upper())
        title_label.setObjectName("cardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")

        card.value_label = value_label

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch(1)

        return card

    def set_notice(self, text: str, kind: str = "idle"):
        self.notice.setText(text)

        object_name = {
            "good": "statusGood",
            "warn": "statusWarn",
            "bad": "statusBad",
        }.get(kind, "muted")

        self.notice.setObjectName(object_name)
        self.notice.style().unpolish(self.notice)
        self.notice.style().polish(self.notice)

    def set_project(
        self,
        manifest: ProjectManifest | None,
        manifest_path: Path | None,
    ):
        loaded = manifest is not None and manifest_path is not None

        self.save_button.setEnabled(loaded)
        self.open_folder_button.setEnabled(loaded)

        if not loaded:
            self.project_name_value.setText("-")
            self.project_status_value.setText("-")
            self.project_id_value.setText("-")
            self.project_schema_value.setText("-")
            self.project_path_value.setText("-")

            for card in (
                self.scenes_value,
                self.media_value,
                self.timeline_value,
                self.inputs_value,
            ):
                card.value_label.setText("0")

            return

        status = getattr(manifest, "status", None)
        status_text = getattr(status, "value", None) or str(status)

        self.project_name_value.setText(manifest.project_name)
        self.project_status_value.setText(status_text)
        self.project_id_value.setText(str(manifest.project_id))
        self.project_schema_value.setText(str(manifest.schema_version))
        self.project_path_value.setText(str(manifest_path))

        self.scenes_value.value_label.setText(
            str(len(getattr(manifest, "scenes", []) or []))
        )
        self.media_value.value_label.setText(
            str(len(getattr(manifest, "media", []) or []))
        )
        self.timeline_value.value_label.setText(
            str(len(getattr(manifest, "timeline", []) or []))
        )
        self.inputs_value.value_label.setText(
            str(len(getattr(manifest, "inputs", []) or []))
        )


class DiagnosticsPage(QWidget):
    def __init__(
        self,
        provider_view: ProviderDiagnosticsQtView,
        open_api_settings_callback,
    ):
        super().__init__()

        self.provider_view = provider_view
        self.provider_view.setStyleSheet(DIAGNOSTICS_VIEW_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(12)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)

        title = QLabel("Chẩn đoán")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Chạy hệ thống chẩn đoán nhà cung cấp trực tiếp trong Creator Studio."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        api_button = QPushButton("API & Nhà cung cấp")
        api_button.setProperty("class", "secondaryButton")
        api_button.setMinimumHeight(36)
        api_button.clicked.connect(open_api_settings_callback)

        header.addLayout(header_text, 1)
        header.addWidget(api_button, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header)

        status_card = Card()
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(18, 14, 18, 14)
        status_layout.setSpacing(12)

        status_title = QLabel("Chẩn đoán nhà cung cấp")
        status_title.setStyleSheet("font-weight: 600; color: #e7eef7;")

        self.runtime_status = QLabel("Sẵn sàng chạy")
        self.runtime_status.setObjectName("statusIdle")
        self.runtime_status.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        status_layout.addWidget(status_title)
        status_layout.addStretch(1)
        status_layout.addWidget(self.runtime_status)

        layout.addWidget(status_card)

        host = QFrame()
        host.setObjectName("diagnosticsHost")

        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(14, 14, 14, 14)
        host_layout.setSpacing(0)

        provider_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        provider_view.setMinimumHeight(360)

        host_layout.addWidget(provider_view)
        layout.addWidget(host, 1)

        note = QLabel(
            "This page reuses the existing diagnostics request builder, host, "
            "Qt view, binder and worker. API credentials remain managed by the "
            "existing API key manager."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        scroll.setWidget(content)
        root.addWidget(scroll)

    def set_runtime_status(self, text: str, kind: str = "idle"):
        self.runtime_status.setText(text)

        object_name = {
            "good": "statusGood",
            "warn": "statusWarn",
            "bad": "statusBad",
        }.get(kind, "statusIdle")

        self.runtime_status.setObjectName(object_name)
        self.runtime_status.style().unpolish(self.runtime_status)
        self.runtime_status.style().polish(self.runtime_status)


class ModulePage(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: str,
        primary_title: str,
        primary_text: str,
        items: list[tuple[str, str]],
        button_text: str | None = None,
        button_callback=None,
    ):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)

        card_title = QLabel(primary_title)
        card_title.setObjectName("sectionTitle")

        card_text = QLabel(primary_text)
        card_text.setObjectName("muted")
        card_text.setWordWrap(True)

        card_layout.addWidget(card_title)
        card_layout.addWidget(card_text)
        card_layout.addSpacing(4)

        for item_title, item_text in items:
            row = QFrame()
            row.setStyleSheet(
                "QFrame { background: #0f151d; border: 1px solid #202a36; border-radius: 8px; }"
            )
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            row_layout.setSpacing(3)

            item_title_label = QLabel(item_title)
            item_title_label.setStyleSheet("font-weight: 600; color: #e7eef7; border: none;")

            item_text_label = QLabel(item_text)
            item_text_label.setObjectName("muted")
            item_text_label.setWordWrap(True)
            item_text_label.setStyleSheet("color: #7e8da3; border: none;")

            row_layout.addWidget(item_title_label)
            row_layout.addWidget(item_text_label)

            card_layout.addWidget(row)

        if button_text:
            card_layout.addSpacing(4)
            button = QPushButton(button_text)
            button.setProperty("class", "primaryButton")
            button.setMinimumHeight(38)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            if button_callback is not None:
                button.clicked.connect(button_callback)

            card_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(card)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)


class CreatorStudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} - {APP_SUBTITLE}")
        self.resize(1400, 880)
        self.setMinimumSize(1120, 720)

        self.nav_buttons: dict[str, QPushButton] = {}
        self.page_indexes: dict[str, int] = {}

        self.current_project: ProjectManifest | None = None
        self.current_project_path: Path | None = None
        self._ui_state = self._load_ui_state()

        self.api_manager = APIKeyManager(ROOT)

        self.provider_diagnostics_host = ProviderDiagnosticsHost()
        self.provider_diagnostics_request_builder = ProviderDiagnosticsRequestBuilder()
        self._provider_diagnostics_close_pending = False

        self.provider_diagnostics_view = ProviderDiagnosticsQtView(parent=self)
        self.provider_diagnostics_bridge = ProviderDiagnosticsQtThreadBridge(parent=self)
        self.provider_diagnostics_binder = ProviderDiagnosticsQtViewBinder(
            self.provider_diagnostics_view,
            self.provider_diagnostics_bridge,
            parent=self,
        )

        self.provider_diagnostics_view.setEnabled(False)

        self._build_ui()
        self._connect_provider_diagnostics()

        self.provider_diagnostics_view.setEnabled(True)
        self._sync_provider_diagnostics_status(self.provider_diagnostics_bridge.state)

        self._restore_recent_project()
        self.navigate_to("dashboard")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = self._build_sidebar()
        shell.addWidget(sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        topbar = self._build_topbar()
        right_layout.addWidget(topbar)

        self.pages = QStackedWidget()
        right_layout.addWidget(self.pages, 1)

        self._register_pages()

        footer = self._build_footer()
        right_layout.addWidget(footer)

        shell.addWidget(right, 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 16)
        layout.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)

        logo = QLabel("AI")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(40, 40)
        logo.setStyleSheet(
            "background: #2d7ff9; color: white; border-radius: 10px; "
            "font-size: 14px; font-weight: 800;"
        )

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)

        brand = QLabel(APP_NAME)
        brand.setObjectName("brand")

        brand_sub = QLabel(APP_SUBTITLE.upper())
        brand_sub.setObjectName("brandSub")

        brand_text.addWidget(brand)
        brand_text.addWidget(brand_sub)

        brand_row.addWidget(logo)
        brand_row.addLayout(brand_text, 1)

        layout.addLayout(brand_row)
        layout.addSpacing(16)

        workspace = QLabel("KHU VỰC LÀM VIỆC")
        workspace.setObjectName("brandSub")
        workspace.setContentsMargins(10, 0, 0, 3)
        layout.addWidget(workspace)

        for item in NAV_ITEMS:
            button = QPushButton(f"  {item.label}")
            button.setProperty("class", "navButton")
            button.setProperty("selected", False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(40)
            button.clicked.connect(lambda checked=False, key=item.key: self.navigate_to(key))

            self.nav_buttons[item.key] = button
            layout.addWidget(button)

        layout.addStretch(1)

        version = QLabel("Creator Studio · M103.1 VI")
        version.setObjectName("brandSub")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(66)

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        self.top_title = QLabel("Tổng quan")
        self.top_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #eef4fb;")

        self.top_subtitle = QLabel("Creator Studio workspace")
        self.top_subtitle.setObjectName("brandSub")

        title_box.addWidget(self.top_title)
        title_box.addWidget(self.top_subtitle)

        layout.addLayout(title_box)
        layout.addStretch(1)

        self.project_button = QPushButton("Dự án: Chưa mở dự án")
        self.project_button.setProperty("class", "projectButton")
        self.project_button.setMinimumHeight(36)
        self.project_button.clicked.connect(lambda: self.navigate_to("project"))

        settings_button = QPushButton("Cài đặt")
        settings_button.setProperty("class", "secondaryButton")
        settings_button.setMinimumHeight(36)
        settings_button.clicked.connect(lambda: self.navigate_to("settings"))

        layout.addWidget(self.project_button)
        layout.addWidget(settings_button)

        return topbar

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(34)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 0, 18, 0)

        ui_status = QLabel("● UI Ready")
        ui_status.setObjectName("statusGood")

        engine_status = QLabel("Engine: giữ nguyên")
        engine_status.setObjectName("muted")

        self.project_footer_status = QLabel("Project: none")
        self.project_footer_status.setObjectName("muted")

        self.provider_footer_status = QLabel("Provider diagnostics: ready")
        self.provider_footer_status.setObjectName("muted")

        layout.addWidget(ui_status)
        layout.addSpacing(14)
        layout.addWidget(engine_status)
        layout.addSpacing(14)
        layout.addWidget(self.project_footer_status)
        layout.addStretch(1)
        layout.addWidget(self.provider_footer_status)

        return footer

    def _register_page(self, key: str, page: QWidget):
        index = self.pages.addWidget(page)
        self.page_indexes[key] = index

    def _register_pages(self):
        self.dashboard_page = DashboardPage()
        self._register_page("dashboard", self.dashboard_page)

        self.project_page = ProjectWorkspacePage(
            self.create_new_project,
            self.open_project,
            self.save_project,
            self.open_project_folder,
        )
        self._register_page(
            "project",
            self.project_page,
        )

        self._register_page(
            "voice",
            ModulePage(
                "Giọng đọc & Kịch bản",
                "Chuẩn bị giọng đọc, bản chép lời và kịch bản trước khi tạo cảnh.",
                "Khu vực giọng đọc",
                "The existing transcription and content-ingest modules will be connected here.",
                [
                    ("Voice", "Load and preview narration audio."),
                    ("Transcript", "Generate or import timestamped transcription."),
                    ("Script", "Review the text used for scene planning."),
                ],
                "Nhập giọng đọc",
            ),
        )

        self._register_page(
            "scenes",
            ModulePage(
                "Cảnh",
                "Review every generated scene, timing, dialogue, search keyword and media assignment.",
                "Scene planner",
                "This page will replace raw JSON inspection with a visual scene table and detail panel.",
                [
                    ("Scene table", "Time range, dialogue, duration, keyword and media coverage."),
                    ("Scene detail", "Context, mood, shot type and AI-generated search terms."),
                    ("Manual control", "Reanalyze one scene without rerunning the whole project."),
                ],
                "Tạo cảnh",
            ),
        )

        self._register_page(
            "media",
            ModulePage(
                "Tìm tư liệu",
                "Search stock providers and local files, then assign the best result to each scene.",
                "Media browser",
                "Pexels, Pixabay and later providers can share one scene-oriented search workspace.",
                [
                    ("Provider filters", "Enable or disable available media providers."),
                    ("Preview grid", "Images and videos displayed visually before selection."),
                    ("Scene assignment", "Attach selected media directly to the current scene."),
                ],
                "Tìm tư liệu",
            ),
        )

        self._register_page(
            "vision",
            ModulePage(
                "AI hình ảnh",
                "Configure and inspect vision/provider operations used by the production pipeline.",
                "Vision workspace",
                "Provider, model, payload bounds and request execution will be surfaced here.",
                [
                    ("Provider", "Select the configured AI provider and model."),
                    ("Request limits", "Control bounded payload and vision input limits."),
                    ("Inspection", "Show request readiness and response diagnostics."),
                ],
                "Kiểm tra AI hình ảnh",
            ),
        )

        self._register_page(
            "timeline",
            ModulePage(
                "Dòng thời gian",
                "Synchronize narration, scenes and assigned media before export.",
                "Timeline workspace",
                "The first version will focus on reliable scene timing instead of a full Premiere-style editor.",
                [
                    ("Narration track", "Voice duration remains the timing backbone."),
                    ("Scene blocks", "Each scene shows start, end and assigned media."),
                    ("Adjustments", "Trim, extend, replace or mute scene media."),
                ],
                "Tạo dòng thời gian",
            ),
        )

        self._register_page(
            "export",
            ModulePage(
                "Xuất video",
                "Choose render settings and produce the final video through the existing engine.",
                "Render workspace",
                "FFmpeg and the current production runner will remain behind the UI.",
                [
                    ("Format", "Resolution, FPS, codec and quality presets."),
                    ("Validation", "Check project readiness before rendering."),
                    ("Progress", "Display render progress and final output path."),
                ],
                "Xuất video",
            ),
        )

        self.diagnostics_page = DiagnosticsPage(
            self.provider_diagnostics_view,
            self.open_api_settings,
        )
        self._register_page(
            "diagnostics",
            self.diagnostics_page,
        )

        self._register_page(
            "settings",
            ModulePage(
                "Cài đặt",
                "Manage application preferences, providers and API key entry points.",
                "Application settings",
                "This page will later link to the existing API key manager without moving secrets into GUI state.",
                [
                    ("API providers", "Manage configured provider profiles."),
                    ("Stock providers", "Pexels, Pixabay and future sources."),
                    ("Application", "Paths, cache, theme and default export settings."),
                ],
                "Mở quản lý API",
                self.open_api_settings,
            ),
        )

    def _load_ui_state(self) -> dict:
        try:
            if not UI_STATE_FILE.exists():
                return {}

            data = json.loads(
                UI_STATE_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if type(data) is not dict:
                return {}

            recent = data.get("recent_project")

            if recent is not None and type(recent) is not str:
                return {}

            return {
                "recent_project": recent or "",
            }

        except Exception:
            return {}

    def _save_ui_state(self):
        UI_STATE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "recent_project": (
                str(self.current_project_path)
                if self.current_project_path is not None
                else ""
            ),
        }

        payload = json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )

        temporary = UI_STATE_FILE.with_name(
            UI_STATE_FILE.name + ".tmp"
        )

        try:
            temporary.write_text(
                payload,
                encoding="utf-8",
            )

            os.replace(
                temporary,
                UI_STATE_FILE,
            )

        finally:
            try:
                temporary.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

        self._ui_state = data

    def _restore_recent_project(self):
        recent = (
            self._ui_state.get(
                "recent_project",
                ""
            )
            if type(self._ui_state) is dict
            else ""
        )

        if not recent:
            self._apply_project_to_ui(
                None,
                None,
            )
            return

        path = Path(recent)

        if not path.is_file():
            self._apply_project_to_ui(
                None,
                None,
            )
            self._save_ui_state()
            return

        try:
            manifest = load_project_manifest(
                path
            )
        except Exception:
            self._apply_project_to_ui(
                None,
                None,
            )
            self._save_ui_state()
            return

        self._set_current_project(
            manifest,
            path,
            notice=(
                f"Reopened recent project: "
                f"{manifest.project_name}"
            ),
            notice_kind="good",
            persist_recent=False,
        )

    def _apply_project_to_ui(
        self,
        manifest: ProjectManifest | None,
        manifest_path: Path | None,
    ):
        if hasattr(
            self,
            "project_page",
        ):
            self.project_page.set_project(
                manifest,
                manifest_path,
            )

        if hasattr(
            self,
            "dashboard_page",
        ):
            self.dashboard_page.set_project_status(
                manifest,
                manifest_path,
            )

        if hasattr(
            self,
            "project_button",
        ):
            self.project_button.setText(
                (
                    f"Dự án: {manifest.project_name}"
                    if manifest is not None
                    else "Dự án: Chưa mở dự án"
                )
            )

        if hasattr(
            self,
            "project_footer_status",
        ):
            self.project_footer_status.setText(
                (
                    f"Dự án: {manifest.project_name}"
                    if manifest is not None
                    else "Project: none"
                )
            )

            self.project_footer_status.setObjectName(
                "statusGood"
                if manifest is not None
                else "muted"
            )

            self.project_footer_status.style().unpolish(
                self.project_footer_status
            )
            self.project_footer_status.style().polish(
                self.project_footer_status
            )

    def _set_current_project(
        self,
        manifest: ProjectManifest,
        manifest_path: Path,
        *,
        notice: str,
        notice_kind: str = "good",
        persist_recent: bool = True,
    ):
        self.current_project = manifest
        self.current_project_path = (
            Path(manifest_path)
            .resolve()
        )

        self._apply_project_to_ui(
            self.current_project,
            self.current_project_path,
        )

        if hasattr(
            self,
            "project_page",
        ):
            self.project_page.set_notice(
                notice,
                notice_kind,
            )

        if persist_recent:
            self._save_ui_state()

    def create_new_project(self):
        if self.provider_diagnostics_binder.is_running:
            QMessageBox.information(
                self,
                "Provider Diagnostics đang chạy",
                (
                    "Hãy chờ Provider Diagnostics kết thúc "
                    "trước khi tạo project mới."
                ),
            )
            return

        name_dialog = QInputDialog(self)
        name_dialog.setWindowTitle("Tạo dự án mới")
        name_dialog.setLabelText("Tên dự án:")
        name_dialog.setOkButtonText("Tạo dự án")
        name_dialog.setCancelButtonText("Hủy")
        name_dialog.setTextValue("")
        name_dialog.setStyleSheet(API_DIALOG_STYLE)

        accepted = (
            name_dialog.exec()
            == QInputDialog.DialogCode.Accepted
        )

        if not accepted:
            return

        project_name = name_dialog.textValue().strip()

        if not project_name:
            QMessageBox.warning(
                self,
                "Tạo dự án mới",
                "Tên dự án không được để trống.",
            )
            return

        try:
            manifest = ProjectManifest(
                project_name
            )

            WORKSPACES_ROOT.mkdir(
                parents=True,
                exist_ok=True,
            )

            folder_name = (
                f"{_safe_workspace_slug(project_name)}_"
                f"{str(manifest.project_id)[:8]}"
            )

            project_folder = (
                WORKSPACES_ROOT
                / folder_name
            )

            project_folder.mkdir(
                parents=False,
                exist_ok=False,
            )

            manifest_path = (
                project_folder
                / PROJECT_MANIFEST_FILENAME
            )

            save_project_manifest(
                manifest,
                manifest_path,
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Tạo dự án mới",
                (
                    "Không thể tạo dự án.\n\n"
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            return

        self._set_current_project(
            manifest,
            manifest_path,
            notice=(
                f"Đã tạo dự án: "
                f"{manifest.project_name}"
            ),
            notice_kind="good",
        )

        self.navigate_to(
            "project"
        )

    def open_project(self):
        start_directory = (
            str(
                self.current_project_path.parent
            )
            if self.current_project_path is not None
            else str(
                WORKSPACES_ROOT
            )
        )

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Mở dự án Creator Studio",
            start_directory,
            (
                "Tệp dự án "
                "(*.json);;"
                "Tất cả tệp (*.*)"
            ),
        )

        if not file_path:
            return

        path = Path(
            file_path
        )

        try:
            manifest = load_project_manifest(
                path
            )

        except PersistenceError as exc:
            QMessageBox.warning(
                self,
                "Mở dự án",
                (
                    "Tệp đã chọn không phải "
                    "ProjectManifest hợp lệ của Creator Studio.\n\n"
                    f"{exc}"
                ),
            )
            return

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Mở dự án",
                (
                    "Không thể mở dự án đã chọn.\n\n"
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            return

        self._set_current_project(
            manifest,
            path,
            notice=(
                f"Đã mở dự án: "
                f"{manifest.project_name}"
            ),
            notice_kind="good",
        )

        self.navigate_to(
            "project"
        )

    def save_project(self):
        if (
            self.current_project is None
            or self.current_project_path is None
        ):
            QMessageBox.information(
                self,
                "Lưu dự án",
                "Hiện chưa có dự án nào được mở.",
            )
            return

        try:
            save_project_manifest(
                self.current_project,
                self.current_project_path,
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Lưu dự án",
                (
                    "Không thể lưu dự án hiện tại.\n\n"
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            return

        self._apply_project_to_ui(
            self.current_project,
            self.current_project_path,
        )

        self.project_page.set_notice(
            (
                f"Đã lưu: "
                f"{self.current_project_path.name}"
            ),
            "good",
        )

        self._save_ui_state()

    def open_project_folder(self):
        if self.current_project_path is None:
            QMessageBox.information(
                self,
                "Mở thư mục dự án",
                "Hiện chưa có dự án nào được mở.",
            )
            return

        project_folder = (
            self.current_project_path
            .parent
        )

        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(project_folder)
            )
        )

        if not opened:
            QMessageBox.warning(
                self,
                "Mở thư mục dự án",
                (
                    "Windows không thể mở thư mục dự án:\n\n"
                    f"{project_folder}"
                ),
            )

    def _connect_provider_diagnostics(self):
        self.provider_diagnostics_binder.run_requested.connect(
            self.run_provider_diagnostics
        )
        self.provider_diagnostics_binder.action_requested.connect(
            self._handle_provider_diagnostics_action
        )
        self.provider_diagnostics_binder.started.connect(
            self._on_provider_diagnostics_started
        )
        self.provider_diagnostics_binder.state_changed.connect(
            self._on_provider_diagnostics_state_changed
        )
        self.provider_diagnostics_binder.fatal.connect(
            self._on_provider_diagnostics_fatal
        )
        self.provider_diagnostics_binder.finished.connect(
            self._on_provider_diagnostics_finished
        )

    def run_provider_diagnostics(self):
        if self.provider_diagnostics_binder.is_running:
            return

        try:
            request = self.provider_diagnostics_request_builder.build_kie(
                self.api_manager,
                ProviderRuntimeDiagnosticMode.ONLINE,
            )

            remote_image_source = ProviderDiagnosticsRemoteImageSource()

            self.provider_diagnostics_host.start(
                self.api_manager,
                self.provider_diagnostics_binder,
                request,
                remote_image_source,
            )

        except Exception:
            try:
                self.provider_diagnostics_view.bind_state(
                    self.provider_diagnostics_bridge.state
                )
            except Exception:
                self.provider_diagnostics_view.reset()

            self._sync_provider_diagnostics_status(
                self.provider_diagnostics_bridge.state
            )

            QMessageBox.warning(
                self,
                "Provider Diagnostics",
                (
                    "Không thể khởi động Provider Diagnostics.\n\n"
                    "Hãy kiểm tra cấu hình KIE AI và API Key rồi thử lại."
                ),
            )

    def _handle_provider_diagnostics_action(self, action):
        if action is ProviderDiagnosticsViewAction.CONFIGURE_CREDENTIAL:
            self.open_api_settings()

    def _on_provider_diagnostics_started(self):
        self._set_provider_status(
            "Running",
            "warn",
            "M100 provider diagnostics is running.",
        )

    def _on_provider_diagnostics_state_changed(self, state):
        self._sync_provider_diagnostics_status(state)

    def _on_provider_diagnostics_fatal(self):
        self._set_provider_status(
            "Internal failure",
            "bad",
            "Diagnostics reached a protected internal failure boundary.",
        )

    def _on_provider_diagnostics_finished(self, state):
        self._sync_provider_diagnostics_status(state)

        if not self._provider_diagnostics_close_pending:
            return

        self._provider_diagnostics_close_pending = False
        QTimer.singleShot(0, self.close)

    def _sync_provider_diagnostics_status(self, state):
        phase = getattr(getattr(state, "phase", None), "name", "IDLE")
        view_model = getattr(state, "view_model", None)

        if phase == "RUNNING":
            self._set_provider_status(
                "Running",
                "warn",
                "Checking KIE provider readiness and connectivity.",
            )
            return

        if phase == "COMPLETED":
            is_ready = bool(getattr(view_model, "is_ready", False))

            if is_ready:
                self._set_provider_status(
                    "Ready",
                    "good",
                    "KIE provider diagnostics completed successfully.",
                )
            else:
                status_text = getattr(view_model, "status_text", "Needs attention")
                self._set_provider_status(
                    status_text,
                    "warn",
                    "Diagnostics completed; review the result on the Diagnostics page.",
                )
            return

        if phase == "CANCELLED":
            self._set_provider_status(
                "Cancelled",
                "warn",
                "The last diagnostics run was cancelled.",
            )
            return

        if phase == "FAILED":
            self._set_provider_status(
                "Failed",
                "bad",
                "Provider diagnostics did not complete successfully.",
            )
            return

        self._set_provider_status(
            "Sẵn sàng chạy",
            "idle",
            "M100 diagnostics stack connected.",
        )

    def _set_provider_status(
        self,
        text: str,
        kind: str,
        detail: str,
    ):
        if hasattr(self, "dashboard_page"):
            self.dashboard_page.set_provider_diagnostics_status(
                text,
                kind,
                detail,
            )

        if hasattr(self, "diagnostics_page"):
            self.diagnostics_page.set_runtime_status(
                text,
                kind,
            )

        if hasattr(self, "provider_footer_status"):
            self.provider_footer_status.setText(
                f"Provider diagnostics: {text}"
            )

            object_name = {
                "good": "statusGood",
                "warn": "statusWarn",
                "bad": "statusBad",
            }.get(kind, "muted")

            self.provider_footer_status.setObjectName(object_name)
            self.provider_footer_status.style().unpolish(
                self.provider_footer_status
            )
            self.provider_footer_status.style().polish(
                self.provider_footer_status
            )

    def open_api_settings(self):
        if self.provider_diagnostics_binder.is_running:
            QMessageBox.information(
                self,
                "Provider Diagnostics đang chạy",
                (
                    "Hãy chờ Provider Diagnostics kết thúc "
                    "trước khi thay đổi API Key."
                ),
            )
            return

        dialog = APIKeysDialog(
            manager=self.api_manager,
            parent=self,
        )
        dialog.setStyleSheet(API_DIALOG_STYLE)
        _translate_button_texts(dialog)
        dialog.exec()

        self._set_provider_status(
            "Sẵn sàng chạy",
            "idle",
            "Cấu hình API đã được cập nhật. Hãy chạy chẩn đoán lại để kiểm tra.",
        )

    def closeEvent(self, event):
        try:
            self._save_ui_state()
        except Exception:
            pass

        if self.provider_diagnostics_binder.is_running:
            if self._provider_diagnostics_close_pending:
                event.ignore()
                return

            answer = QMessageBox.question(
                self,
                "Provider Diagnostics đang chạy",
                (
                    "Provider Diagnostics vẫn đang chạy.\n\n"
                    "Bạn có muốn hủy chẩn đoán và đóng chương trình?"
                ),
                (
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                ),
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

            self._provider_diagnostics_close_pending = True
            self.provider_diagnostics_binder.request_cancel()
            event.ignore()
            return

        event.accept()

    def navigate_to(self, key: str):
        if key not in self.page_indexes:
            return

        self.pages.setCurrentIndex(self.page_indexes[key])

        selected_label = key
        for item in NAV_ITEMS:
            button = self.nav_buttons[item.key]
            is_selected = item.key == key
            button.setProperty("selected", is_selected)
            button.style().unpolish(button)
            button.style().polish(button)

            if is_selected:
                selected_label = item.label

        self.top_title.setText(selected_label)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_STYLE)

    window = CreatorStudioWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
