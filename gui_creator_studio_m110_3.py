
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QPixmap
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
    QAbstractButton,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QProgressBar,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QRadioButton,
    QCheckBox,
    QDoubleSpinBox,
    QAbstractSpinBox,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QVBoxLayout,
    QWidget,
)

try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    QT_VIDEO_PREVIEW_AVAILABLE = True
except Exception:
    QAudioOutput = None
    QMediaPlayer = None
    QVideoWidget = None
    QT_VIDEO_PREVIEW_AVAILABLE = False

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

from creator_studio.manifest.models import (
    Content,
    InputKind,
    InputSource,
    ProjectManifest,
    Status,
    VoiceKind,
)
from creator_studio.content.models import IngestRequest
from creator_studio.content.ingest import ingest as ingest_content, apply_ingest
from creator_studio.manifest.persistence import (
    PersistenceError,
    load as load_project_manifest,
    save as save_project_manifest,
)
from creator_studio.tts import TTSProviderRegistry, TTSService
from creator_studio.tts.providers import PiperProcessProvider, VoiceStudioLocalProvider
from creator_studio.tts.voicestudio_runtime import VoiceStudioLocalRuntimeManager
from creator_studio.project_storage import (
    MediaAssetRecord,
    VoiceAssetRecord,
    create_project_root,
    create_voice_work_run,
    finalize_voice_asset,
    find_media_asset_by_path,
    find_voice_asset_by_path,
    import_media_asset,
    import_voice_asset,
    initialize_project_layout,
    media_assets_root,
    new_generated_voice_target,
    scan_media_assets,
    scan_voice_assets,
    safe_slug as storage_safe_slug,
    voice_assets_root,
    voice_work_root,
)
from creator_studio.scene_assets import (
    SceneAssetAssignmentState,
    assign_media_asset,
    latest_voice_scenes_path,
    load_scene_assignment_state,
    load_voice_scenes,
    remove_scene_assignment,
)
from creator_studio.automation_workflow import (
    AUTOMATION_STAGES,
    AutomationStageStatus,
    AutomationWorkflowState,
)
from creator_studio.automation_runner import (
    AutomationPipelineCoordinator,
    AutomationRunStatus,
)
from creator_studio.visual_query_planner import (
    QUERY_PLAN_FILENAME,
    VisualQueryPlanner,
    load_voice_scene_payload,
    save_query_plan,
)
from creator_studio.stock_acquisition import (
    StockAcquisitionService,
)
from creator_studio.youtube_reference import (
    YOUTUBE_REFERENCE_FILENAME,
    YouTubeReferenceService,
)


ROOT = Path(__file__).resolve().parent

WORKSPACES_ROOT = ROOT / "projects" / "workspaces"
UI_STATE_FILE = ROOT / "config" / "creator_studio_ui_state.json"
PROJECT_MANIFEST_FILENAME = "project_manifest.json"
VOICE_INPUT_ID = "creator_studio_voice_input"
SCRIPT_INPUT_ID = "creator_studio_script_input"
SCRIPT_CONTENT_ID = "creator_studio_script"
VOICE_WORKSPACE_DIRNAME = "voice_workspace"
SCRIPT_WORKSPACE_DIRNAME = "scripts"
SCRIPT_WORKSPACE_FILENAME = "script.txt"
VOICE_HISTORY_DIRNAME = "history"
VOICE_ACTIVE_HISTORY_FILENAME = ".active_voice_history.json"
VOICE_PIPELINE_RESULT_FILENAME = "voice_pipeline_result.json"
GENERATED_VOICE_FILENAME = "generated_voice.wav"
TTS_PREVIEW_FILENAME = "tts_preview.wav"
PIPER_RUNTIME_ROOT = ROOT / "runtime" / "piper"
PIPER_PYTHON = PIPER_RUNTIME_ROOT / ".venv" / "Scripts" / "python.exe"
PIPER_VOICES_ROOT = PIPER_RUNTIME_ROOT / "voices"
VOICESTUDIO_BASE_URL = "http://127.0.0.1:3900"

APP_NAME = "AI Video Editor"
APP_SUBTITLE = "Creator Studio"


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    short: str


PRIMARY_NAV_ITEMS = [
    NavItem("automation", "Tạo video", "▶"),
    NavItem("project", "Dự án", "P"),
    NavItem("settings", "Cài đặt", "ST"),
]

ADVANCED_NAV_ITEMS = [
    NavItem("voice", "Giọng đọc + Kịch bản", "V"),
    NavItem("scenes", "Cảnh", "S"),
    NavItem("media", "Tư liệu", "M"),
    NavItem("vision", "AI hình ảnh", "AI"),
    NavItem("timeline", "Dòng thời gian", "T"),
    NavItem("export", "Xuất video", "E"),
    NavItem("diagnostics", "Chẩn đoán", "DX"),
]

NAV_ITEMS = PRIMARY_NAV_ITEMS + ADVANCED_NAV_ITEMS




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
    background: #21466e;
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
    background: #174f9f;
    border: 2px solid #b9d8ff;
    padding-top: 11px;
    padding-bottom: 7px;
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
    background: #09121c;
    color: #ffffff;
    border: 2px solid #8fc4ff;
    padding-top: 10px;
    padding-bottom: 6px;
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
QTableWidget {
    background: #0b0f14;
    color: #dce6f2;
    border: 1px solid #2a3544;
    border-radius: 7px;
    gridline-color: #223043;
    selection-background-color: #1d3857;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background: #141c26;
    color: #aebed0;
    border: none;
    border-right: 1px solid #2a3544;
    border-bottom: 1px solid #2a3544;
    padding: 7px;
    font-weight: 600;
}




QLineEdit {
    background: #0b0f14;
    color: #eef4fb;
    border: 1px solid #33445a;
    border-radius: 7px;
    padding: 7px 10px;
    selection-background-color: #2d7ff9;
    selection-color: #ffffff;
}

QLineEdit:hover {
    background: #111b28;
    border-color: #5b7da5;
}

QLineEdit:focus {
    background: #0b0f14;
    color: #ffffff;
    border: 1px solid #5da9ff;
}

QLineEdit:disabled {
    background: #111821;
    color: #637287;
    border-color: #222d3a;
}

QLineEdit#cloneNameEdit {
    min-height: 20px;
    font-weight: 600;
}


QPlainTextEdit {
    background: #0b0f14;
    color: #eef4fb;
    border: 1px solid #33445a;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #2d7ff9;
    font-family: "Segoe UI";
    font-size: 13px;
}

QPlainTextEdit:focus {
    border: 1px solid #5da9ff;
}

QPlainTextEdit:disabled {
    background: #111821;
    color: #637287;
    border-color: #222d3a;
}

QComboBox {
    background: #0b0f14;
    color: #eef4fb;
    border: 1px solid #33445a;
    border-radius: 7px;
    padding: 7px 10px;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #5b7da5;
    background: #111b28;
}

QComboBox:focus {
    border: 1px solid #5da9ff;
}

QComboBox QAbstractItemView {
    background: #101720;
    color: #e8eef6;
    border: 1px solid #33445a;
    selection-background-color: #21466e;
    selection-color: #ffffff;
}

QAbstractSpinBox,
QDoubleSpinBox {
    background: #0b0f14;
    color: #eef4fb;
    border: 1px solid #33445a;
    border-radius: 7px;
    padding: 6px 8px;
    min-width: 82px;
    selection-background-color: #2d7ff9;
    selection-color: #ffffff;
}

QAbstractSpinBox:hover,
QDoubleSpinBox:hover {
    background: #111b28;
    border-color: #5b7da5;
}

QAbstractSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #5da9ff;
}

QAbstractSpinBox QLineEdit,
QDoubleSpinBox QLineEdit {
    background: transparent;
    color: #eef4fb;
    border: none;
    padding: 0;
}

QAbstractSpinBox::up-button,
QAbstractSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background: #172231;
    border-left: 1px solid #33445a;
    width: 18px;
}

QPushButton#spinStepButton {
    background: #172231;
    color: #ffffff;
    border: 1px solid #3b526d;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
    padding: 0px;
}

QPushButton#spinStepButton:hover {
    background: #21344b;
    border-color: #5da9ff;
}

QPushButton#spinStepButton:pressed {
    background: #2d7ff9;
}

QMessageBox {
    background: #121923;
    color: #eef4fb;
}

QMessageBox QLabel {
    background: transparent;
    color: #eef4fb;
    min-width: 360px;
}

QMessageBox QPushButton {
    background: #182332;
    color: #eef4fb;
    border: 1px solid #40526a;
    border-radius: 7px;
    padding: 7px 18px;
    min-width: 78px;
}

QMessageBox QPushButton:hover {
    background: #27415f;
    border-color: #6aa8e8;
}

QMessageBox QPushButton:pressed {
    background: #10233a;
    border-color: #8bc5ff;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
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

QFrame#automationStageRow {
    background: #0f151d;
    border: 1px solid #202b38;
    border-radius: 9px;
}

QFrame#automationStageRow[running="true"] {
    background: #142437;
    border: 1px solid #4f8fd1;
}

QFrame#automationStageRow[failed="true"] {
    background: #24171a;
    border: 1px solid #7c3c45;
}

QLabel#automationStepNumber {
    color: #8ea1b8;
    font-size: 11px;
    font-weight: 700;
}

QLabel#automationStepTitle {
    color: #eef4fb;
    font-size: 13px;
    font-weight: 700;
}

QLabel#automationStepIcon {
    color: #9fb0c5;
    font-size: 18px;
    font-weight: 800;
}

QFrame#automationHero {
    background: #101b29;
    border: 1px solid #274667;
    border-radius: 12px;
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


def _translate_known_ui_texts(root: QWidget) -> None:
    """Việt hóa các nhãn/nút legacy mà không thay đổi logic engine."""
    translations = {
        "Run Diagnostics": "Chạy chẩn đoán",
        "Cancel": "Hủy",
        "+ Add Provider": "+ Thêm nhà cung cấp",
        "Delete Provider": "Xóa nhà cung cấp",
        "SAVE PROVIDER": "LƯU NHÀ CUNG CẤP",
        "Save Provider": "Lưu nhà cung cấp",
        "Close": "Đóng",
        "Settings": "Cài đặt",
        "API KEY MANAGER": "QUẢN LÝ API KEY",
        "Providers": "Nhà cung cấp",
        "Enabled:": "Kích hoạt:",
        "Enabled": "Đã bật",
        "Provider name:": "Tên nhà cung cấp:",
        "Base URL:": "URL cơ sở:",
        "Model:": "Mô hình:",
        "Environment variable:": "Biến môi trường:",
        "API Key:": "API Key:",
        "Show API Key": "Hiện API Key",
        "Chẩn đoán nhà cung cấp": "Chẩn đoán nhà cung cấp",
        "Diagnostics ready": "Chẩn đoán sẵn sàng",
        "Run diagnostics to check provider readiness.": "Chạy chẩn đoán để kiểm tra trạng thái nhà cung cấp.",
        "Not run": "Chưa chạy",
        "Success": "Thành công",
        "Ready": "Sẵn sàng",
        "Running": "Đang chạy",
        "Cancelled": "Đã hủy",
        "Failed": "Thất bại",
    }

    for widget in root.findChildren(QWidget):
        if isinstance(widget, (QLabel, QAbstractButton)):
            try:
                current = widget.text()
            except Exception:
                current = ""
            translated = translations.get(current)
            if translated:
                widget.setText(translated)

        if isinstance(widget, QAbstractButton):
            widget.setCursor(Qt.CursorShape.PointingHandCursor)

        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText()
            if placeholder == "Optional API Base URL":
                widget.setPlaceholderText("URL cơ sở tùy chọn")


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




def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:
            pass
    data = getattr(value, "__dict__", None)
    if isinstance(data, dict):
        return _json_safe(data)
    return str(value)


def _format_duration(seconds):
    try:
        total = max(0, int(round(float(seconds))))
    except Exception:
        return "--:--"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class VoicePipelineWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, audio_path: Path, srt_path: Path, parent=None):
        super().__init__(parent)
        self.audio_path = Path(audio_path)
        self.srt_path = Path(srt_path)

    def run(self):
        try:
            from pipeline.voice_pipeline import VoicePipeline

            pipeline = VoicePipeline()
            result = pipeline.run(
                audio_path=self.audio_path,
                srt_output_path=self.srt_path,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class SceneQueryPlanningWorker(QThread):
    progress = pyqtSignal(int, int, str, str)
    activity = pyqtSignal(str, int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        scenes_path: Path,
        output_path: Path,
        *,
        language: str = "und",
        runtime_environment: dict | None = None,
        cache_dir: Path | None = None,
        batch_size: int = 8,
        parent=None,
    ):
        super().__init__(parent)
        self.scenes_path = Path(scenes_path)
        self.output_path = Path(output_path)
        self.language = str(language or "und")
        self.runtime_environment = dict(runtime_environment or {})
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.batch_size = max(1, int(batch_size or 8))

    def run(self):
        try:
            scenes = load_voice_scene_payload(self.scenes_path)
            planner = VisualQueryPlanner(
                language=self.language,
                runtime_environment=self.runtime_environment,
                cache_dir=self.cache_dir,
                batch_size=self.batch_size,
            )

            def on_batch(batch_no, batch_total, batch_scene_count):
                if batch_total <= 0:
                    return
                progress = max(1, min(24, int(round(((batch_no - 1) / batch_total) * 24)) + 1))
                self.activity.emit(
                    f"Đang phân tích nhóm cảnh {batch_no}/{batch_total} · {batch_scene_count} cảnh...",
                    progress,
                )

            def on_progress(index, total, plan):
                self.progress.emit(
                    index,
                    total,
                    plan.scene_id,
                    plan.primary_query,
                )

            report = planner.plan_scenes(
                scenes,
                progress_callback=on_progress,
                batch_callback=on_batch,
            )
            save_query_plan(
                self.output_path,
                report.plans,
                source_scenes=self.scenes_path,
            )
            search_count = sum(1 for plan in report.plans if plan.strategy != "reuse_previous")
            self.succeeded.emit({
                "scene_count": len(report.plans),
                "planned_count": search_count,
                "reused_gap_count": report.reused_gap_count,
                "ai_count": report.ai_count,
                "cache_hit_count": report.cache_hit_count,
                "fallback_count": report.fallback_count,
                "batch_request_count": report.batch_request_count,
                "output_path": str(self.output_path),
                "source_scenes_path": str(self.scenes_path),
            })
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class StockAcquisitionWorker(QThread):
    progress = pyqtSignal(int, int, str, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        project_root: Path,
        run_dir: Path,
        query_plan_path: Path,
        source_scenes_path: Path,
        voice_asset_id: str,
        runtime_environment: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project_root = Path(project_root)
        self.run_dir = Path(run_dir)
        self.query_plan_path = Path(query_plan_path)
        self.source_scenes_path = Path(source_scenes_path)
        self.voice_asset_id = str(voice_asset_id or "")
        self.runtime_environment = dict(runtime_environment or {})

    def run(self):
        try:
            service = StockAcquisitionService(
                project_root=self.project_root,
                run_dir=self.run_dir,
                query_plan_path=self.query_plan_path,
                source_scenes_path=self.source_scenes_path,
                voice_asset_id=self.voice_asset_id,
                runtime_environment=self.runtime_environment,
                progress_callback=lambda current, total, scene_id, phase: self.progress.emit(
                    int(current), int(total), str(scene_id), str(phase)
                ),
            )
            report = service.run()
            self.succeeded.emit(report.to_dict())
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class YouTubeReferenceWorker(QThread):
    progress = pyqtSignal(int, int, str, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        run_dir: Path,
        query_plan_path: Path,
        stock_manifest_path: Path,
        language: str,
        runtime_environment: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.run_dir = Path(run_dir)
        self.query_plan_path = Path(query_plan_path)
        self.stock_manifest_path = Path(stock_manifest_path)
        self.language = str(language or "")
        self.runtime_environment = dict(runtime_environment or {})

    def run(self):
        try:
            service = YouTubeReferenceService.from_runtime_environment(
                run_dir=self.run_dir,
                query_plan_path=self.query_plan_path,
                stock_manifest_path=self.stock_manifest_path,
                runtime_environment=self.runtime_environment,
                language=self.language,
                progress_callback=lambda current, total, scene_id, query: self.progress.emit(
                    int(current), int(total), str(scene_id), str(query)
                ),
            )
            report = service.run()
            self.succeeded.emit(report.to_dict())
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class TTSSynthesisWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: TTSService, request: dict, parent=None):
        super().__init__(parent)
        self.service = service
        self.request = dict(request)

    def run(self):
        try:
            result = self.service.synthesize(**self.request)
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class AudioPreviewController(QObject):
    """Preview WAV audio entirely inside Creator Studio.

    M104.4.8 avoids both Windows MCI and QMediaPlayer.

    Primary backend:
        QAudioSink + QBuffer with decoded PCM frames loaded from the WAV file.

    Fallback on Windows:
        winsound.PlaySound (play/stop only; pause/resume unavailable).
    """

    finished = pyqtSignal()
    failed = pyqtSignal(str)
    state_changed = pyqtSignal(bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wav_path: Path | None = None
        self._active = False
        self._paused = False
        self._cleaning_up = False
        self._backend = "none"
        self._backend_detail = ""

        self._audio_sink = None
        self._audio_buffer = None
        self._pcm_bytes = None
        self._QtAudio = None
        self._QAudioFormat = None
        self._QAudioSink = None
        self._QMediaDevices = None

        self._fallback_timer = QTimer(self)
        self._fallback_timer.setSingleShot(True)
        self._fallback_timer.timeout.connect(self._on_fallback_finished)

        try:
            from PyQt6.QtMultimedia import (
                QAudioFormat,
                QAudioSink,
                QMediaDevices,
                QtAudio,
            )

            self._QAudioFormat = QAudioFormat
            self._QAudioSink = QAudioSink
            self._QMediaDevices = QMediaDevices
            self._QtAudio = QtAudio
            self._backend = "qaudiosink"
            self._backend_detail = "PyQt6.QtMultimedia.QAudioSink"
        except Exception as exc:
            if sys.platform == "win32":
                try:
                    import winsound  # noqa: F401

                    self._backend = "winsound"
                    self._backend_detail = (
                        "winsound fallback; pause/resume unavailable because "
                        f"QAudioSink could not load: {type(exc).__name__}: {exc}"
                    )
                except Exception as fallback_exc:
                    self._backend = "none"
                    self._backend_detail = (
                        f"QAudioSink unavailable: {type(exc).__name__}: {exc}; "
                        f"winsound unavailable: {type(fallback_exc).__name__}: {fallback_exc}"
                    )
            else:
                self._backend = "none"
                self._backend_detail = (
                    f"QAudioSink unavailable: {type(exc).__name__}: {exc}"
                )

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def backend_name(self) -> str:
        return self._backend

    @property
    def backend_detail(self) -> str:
        return self._backend_detail

    def play(self, wav_path: Path):
        path = Path(wav_path).resolve()
        if not path.is_file() or path.stat().st_size <= 44:
            raise RuntimeError("Tệp nghe thử WAV không hợp lệ.")

        self.stop(delete_temp=True, emit_state=False)

        if self._backend == "qaudiosink":
            self._play_qaudiosink(path)
            return
        if self._backend == "winsound":
            self._play_winsound(path)
            return
        raise RuntimeError(
            "Không có backend phát âm thanh trực tiếp khả dụng. "
            + self._backend_detail
        )

    def _read_pcm_wave(self, path: Path):
        import wave

        with wave.open(str(path), "rb") as wav_file:
            if wav_file.getcomptype() != "NONE":
                raise RuntimeError(
                    f"WAV preview không phải PCM thuần: {wav_file.getcomptype()}."
                )
            channels = int(wav_file.getnchannels())
            sample_rate = int(wav_file.getframerate())
            sample_width = int(wav_file.getsampwidth())
            frame_count = int(wav_file.getnframes())
            pcm = wav_file.readframes(frame_count)

        if channels <= 0 or sample_rate <= 0 or not pcm:
            raise RuntimeError("WAV preview không có dữ liệu PCM hợp lệ.")

        if sample_width == 3:
            converted = bytearray()
            for offset in range(0, len(pcm) - 2, 3):
                value = int.from_bytes(
                    pcm[offset : offset + 3],
                    byteorder="little",
                    signed=True,
                )
                value >>= 8
                converted.extend(
                    int(value).to_bytes(2, byteorder="little", signed=True)
                )
            pcm = bytes(converted)
            sample_width = 2

        duration_ms = max(
            1,
            int(
                (len(pcm) / float(sample_width * channels * sample_rate))
                * 1000.0
            ),
        )
        return pcm, channels, sample_rate, sample_width, duration_ms

    def _play_qaudiosink(self, path: Path):
        assert self._QAudioFormat is not None
        assert self._QAudioSink is not None
        assert self._QMediaDevices is not None
        assert self._QtAudio is not None

        pcm, channels, sample_rate, sample_width, _duration_ms = (
            self._read_pcm_wave(path)
        )

        fmt = self._QAudioFormat()
        fmt.setSampleRate(sample_rate)
        fmt.setChannelCount(channels)

        if sample_width == 1:
            sample_format = self._QAudioFormat.SampleFormat.UInt8
        elif sample_width == 2:
            sample_format = self._QAudioFormat.SampleFormat.Int16
        elif sample_width == 4:
            sample_format = self._QAudioFormat.SampleFormat.Int32
        else:
            raise RuntimeError(
                f"Độ sâu mẫu WAV chưa được hỗ trợ: {sample_width * 8}-bit."
            )
        fmt.setSampleFormat(sample_format)

        device = self._QMediaDevices.defaultAudioOutput()
        if hasattr(device, "isNull") and device.isNull():
            raise RuntimeError("Windows không có thiết bị phát âm thanh mặc định.")

        if hasattr(device, "isFormatSupported") and not device.isFormatSupported(fmt):
            raise RuntimeError(
                "Thiết bị âm thanh mặc định không hỗ trợ định dạng WAV preview "
                f"{sample_rate} Hz / {channels} kênh / {sample_width * 8}-bit."
            )

        self._pcm_bytes = QByteArray(pcm)
        self._audio_buffer = QBuffer(self)
        self._audio_buffer.setData(self._pcm_bytes)
        if not self._audio_buffer.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError("Không thể mở bộ đệm PCM để phát nghe thử.")

        self._audio_sink = self._QAudioSink(device, fmt, self)
        self._audio_sink.setVolume(1.0)
        self._audio_sink.stateChanged.connect(self._on_audio_sink_state_changed)

        self._wav_path = path
        self._active = True
        self._paused = False
        self._cleaning_up = False

        self._audio_sink.start(self._audio_buffer)

        self._delete_path_with_retry(path)
        self._wav_path = None
        self.state_changed.emit(True, False)

    def _play_winsound(self, path: Path):
        import wave
        import winsound

        try:
            with wave.open(str(path), "rb") as wav_file:
                rate = wav_file.getframerate()
                frames = wav_file.getnframes()
                duration_ms = (
                    max(1, int((frames / float(rate)) * 1000.0))
                    if rate > 0
                    else 60_000
                )
        except Exception:
            duration_ms = 60_000

        self._wav_path = path
        self._active = True
        self._paused = False
        self._cleaning_up = False

        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME
            | winsound.SND_ASYNC
            | winsound.SND_NODEFAULT,
        )
        self._fallback_timer.start(duration_ms + 250)
        self.state_changed.emit(True, False)

    def toggle_pause(self):
        if not self._active:
            return

        if self._backend == "qaudiosink" and self._audio_sink is not None:
            if self._paused:
                self._audio_sink.resume()
            else:
                self._audio_sink.suspend()
            return

        if self._backend == "winsound":
            self.failed.emit(
                "Backend âm thanh dự phòng của Windows không hỗ trợ "
                "Tạm dừng/Tiếp tục. Nút Dừng và chống phát chồng vẫn hoạt động."
            )

    def stop(self, *, delete_temp: bool = True, emit_state: bool = True):
        path = self._wav_path
        self._cleaning_up = True
        self._fallback_timer.stop()

        if self._backend == "qaudiosink":
            self._release_audio_sink()
        elif self._backend == "winsound" and sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass

        self._wav_path = None
        self._active = False
        self._paused = False

        if delete_temp and path is not None:
            self._delete_path_with_retry(path)

        self._cleaning_up = False
        if emit_state:
            self.state_changed.emit(False, False)

    def _release_audio_sink(self):
        sink = self._audio_sink
        buffer = self._audio_buffer

        self._audio_sink = None
        self._audio_buffer = None
        self._pcm_bytes = None

        if sink is not None:
            try:
                sink.stop()
            except Exception:
                pass
            try:
                sink.deleteLater()
            except Exception:
                pass

        if buffer is not None:
            try:
                buffer.close()
            except Exception:
                pass
            try:
                buffer.deleteLater()
            except Exception:
                pass

    def _on_audio_sink_state_changed(self, state):
        if self._cleaning_up or not self._active or self._QtAudio is None:
            return

        if state == self._QtAudio.State.ActiveState:
            self._paused = False
            self.state_changed.emit(True, False)
            return

        if state == self._QtAudio.State.SuspendedState:
            self._paused = True
            self.state_changed.emit(True, True)
            return

        if state == self._QtAudio.State.IdleState:
            self._finish_successfully()
            return

        if state == self._QtAudio.State.StoppedState:
            error = None
            if self._audio_sink is not None:
                try:
                    error = self._audio_sink.error()
                except Exception:
                    error = None
            no_error = getattr(self._QtAudio.Error, "NoError", None)
            if error is not None and error != no_error:
                self._finish_with_error(
                    f"QAudioSink playback error: {error}"
                )

    def _on_fallback_finished(self):
        if self._backend != "winsound" or not self._active:
            return
        self._finish_successfully()

    def _finish_successfully(self):
        path = self._wav_path
        self._cleaning_up = True

        if self._backend == "qaudiosink":
            self._release_audio_sink()
        elif self._backend == "winsound" and sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass

        self._fallback_timer.stop()
        self._wav_path = None
        self._active = False
        self._paused = False

        if path is not None:
            self._delete_path_with_retry(path)

        self._cleaning_up = False
        self.state_changed.emit(False, False)
        self.finished.emit()

    def _finish_with_error(self, message: str):
        path = self._wav_path
        self._cleaning_up = True

        if self._backend == "qaudiosink":
            self._release_audio_sink()
        elif self._backend == "winsound" and sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass

        self._fallback_timer.stop()
        self._wav_path = None
        self._active = False
        self._paused = False

        if path is not None:
            self._delete_path_with_retry(path)

        self._cleaning_up = False
        self.state_changed.emit(False, False)
        self.failed.emit(message)

    @staticmethod
    def _delete_path_with_retry(path: Path):
        path = Path(path)
        for delay_ms in (0, 60, 180, 500):
            if delay_ms:
                time.sleep(delay_ms / 1000.0)
            try:
                path.unlink(missing_ok=True)
                return
            except PermissionError:
                continue
            except Exception:
                return

class VoiceCloneWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: TTSService, request: dict, parent=None):
        super().__init__(parent)
        self.service = service
        self.request = dict(request)

    def run(self):
        try:
            result = self.service.clone_voice(**self.request)
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


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
            "GIỌNG ĐỌC",
            "Chưa thiết lập",
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
            "TƯ LIỆU",
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

        workflow_sub = QLabel("Các chức năng sẽ lần lượt được kết nối với engine hiện có trong các bước tiếp theo.")
        workflow_sub.setObjectName("muted")
        workflow_sub.setWordWrap(True)

        workflow_layout.addWidget(workflow_title)
        workflow_layout.addWidget(workflow_sub)
        workflow_layout.addSpacing(6)

        rows = [
            ("Dự án", "Tạo hoặc mở dự án sản xuất video", "Chưa bắt đầu", "idle"),
            ("Giọng đọc & Kịch bản", "Nhập giọng đọc, bản chép lời và kịch bản", "Đang chờ", "idle"),
            ("Cảnh", "Tạo và kiểm tra danh sách cảnh", "Đang chờ", "idle"),
            ("Tìm tư liệu", "Tìm và gán video/ảnh cho từng cảnh", "Đang chờ", "idle"),
            ("Dòng thời gian", "Đồng bộ tư liệu với giọng đọc", "Đang chờ", "idle"),
            ("Xuất video", "Kết xuất video hoàn chỉnh", "Đang chờ", "idle"),
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
            "Creator Studio đang sử dụng hệ thống chẩn đoán M100 hiện có mà không thay thế engine đã được kiểm thử."
        )
        system_sub.setObjectName("muted")
        system_sub.setWordWrap(True)

        system_layout.addWidget(system_title)
        system_layout.addWidget(system_sub)
        system_layout.addSpacing(6)

        system_layout.addWidget(
            WorkflowRow("Giao diện ứng dụng", "Giao diện Creator Studio", "Sẵn sàng", "good")
        )

        self.provider_diagnostics_row = WorkflowRow(
            "Chẩn đoán nhà cung cấp",
            "Hệ thống chẩn đoán M100 / M99 / M98",
            "Sẵn sàng chạy",
            "idle",
        )
        system_layout.addWidget(self.provider_diagnostics_row)

        system_layout.addWidget(
            WorkflowRow("Pipeline xử lý", "Engine sản xuất hiện có", "Giữ nguyên", "good")
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
            self.continue_button.setText("Tạo hoặc mở dự án")
            self.voice_metric.set_metric("Chưa thiết lập", "Chưa mở dự án", "idle")
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
                    "Tạo hoặc mở dự án sản xuất video",
                )
            return

        self.continue_button.setText("Tiếp tục dự án")

        voice_input = next(
            (
                item
                for item in (getattr(manifest, "inputs", []) or [])
                if getattr(item, "id", None) == VOICE_INPUT_ID
                or getattr(item, "kind", None) == InputKind.VOICE
            ),
            None,
        )
        voice_ready = bool(getattr(voice_input, "reference", ""))
        script_ready = bool(str(getattr(getattr(manifest, "content", None), "script", "") or "").strip())
        scenes_count = len(getattr(manifest, "scenes", []) or [])
        media_count = len(getattr(manifest, "media", []) or [])
        timeline_count = len(getattr(manifest, "timeline", []) or [])
        render_ready = _object_has_non_default_state(
            getattr(manifest, "render_preparation", None)
        )

        voice_hint = (
            Path(str(getattr(voice_input, "reference", ""))).name
            if voice_ready
            else "Chưa chọn tệp giọng đọc"
        )
        self.voice_metric.set_metric(
            "Đã chọn" if voice_ready else "Chưa thiết lập",
            voice_hint,
            "good" if voice_ready else "idle",
        )
        self.scenes_metric.set_metric(
            str(scenes_count),
            "Số cảnh trong dữ liệu dự án",
            "good" if scenes_count else "idle",
        )
        self.media_metric.set_metric(
            str(media_count),
            "Số tư liệu trong dữ liệu dự án",
            "good" if media_count else "idle",
        )

        if render_ready:
            export_text = "Sẵn sàng"
            export_hint = "Dự án đã có trạng thái chuẩn bị kết xuất"
            export_kind = "good"
        elif timeline_count:
            export_text = "Dòng thời gian sẵn sàng"
            export_hint = f"Có {timeline_count} mục trong dòng thời gian"
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
                "Đã tải",
                "good",
                manifest.project_name,
            )

        voice_row = self.workflow_rows.get("Giọng đọc & Kịch bản")
        if voice_row is not None:
            if voice_ready and script_ready:
                voice_row.set_status("Đã có đầu vào", "good", "Giọng đọc và kịch bản đã sẵn sàng")
            elif voice_ready or script_ready:
                voice_row.set_status("Chưa đầy đủ", "warn", "Cần bổ sung giọng đọc hoặc kịch bản")
            else:
                voice_row.set_status("Đang chờ", "idle", "Nhập giọng đọc và kịch bản")



class AutomationStageRow(QFrame):
    STATUS_META = {
        AutomationStageStatus.PENDING: ("○", "Đang chờ", "idle"),
        AutomationStageStatus.RUNNING: ("●", "Đang thực hiện", "warn"),
        AutomationStageStatus.COMPLETED: ("✓", "Hoàn thành", "good"),
        AutomationStageStatus.FAILED: ("!", "Lỗi", "bad"),
        AutomationStageStatus.CANCELLED: ("×", "Đã hủy", "warn"),
        AutomationStageStatus.SKIPPED: ("–", "Bỏ qua", "idle"),
    }

    def __init__(self, index: int, title: str, default_detail: str, parent=None):
        super().__init__(parent)
        self.setObjectName("automationStageRow")
        self.setProperty("running", False)
        self.setProperty("failed", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        self.icon_label = QLabel("○")
        self.icon_label.setObjectName("automationStepIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedWidth(28)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        number = QLabel(f"BƯỚC {index:02d}")
        number.setObjectName("automationStepNumber")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("automationStepTitle")

        self.detail_label = QLabel(default_detail)
        self.detail_label.setObjectName("muted")
        self.detail_label.setWordWrap(True)
        self.detail_label.setVisible(False)

        text_box.addWidget(number)
        text_box.addWidget(self.title_label)
        text_box.addWidget(self.detail_label)

        self.status_label = QLabel("Đang chờ")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setMinimumWidth(110)

        layout.addWidget(self.icon_label)
        layout.addLayout(text_box, 1)
        layout.addWidget(self.status_label)

    def set_stage_state(self, status: AutomationStageStatus | str, detail: str, *, active: bool = False):
        status = AutomationStageStatus(status)
        icon, text, kind = self.STATUS_META[status]
        self.icon_label.setText(icon)
        self.status_label.setText(text)

        object_name = {
            "good": "statusGood",
            "warn": "statusWarn",
            "bad": "statusBad",
        }.get(kind, "statusIdle")
        self.status_label.setObjectName(object_name)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(active or status in (AutomationStageStatus.RUNNING, AutomationStageStatus.FAILED)))

        self.setProperty("running", status == AutomationStageStatus.RUNNING)
        self.setProperty("failed", status == AutomationStageStatus.FAILED)
        self.style().unpolish(self)
        self.style().polish(self)


class AutomationPage(QWidget):
    """Simple end-user surface for the one-click automation workflow."""

    PRESETS = (
        "YouTube Documentary",
        "YouTube News",
        "Senior Story",
        "Horror",
        "Daily Life",
        "Shorts",
    )

    def __init__(
        self,
        on_create_project,
        on_open_project,
        on_prepare_workflow,
        on_open_voice_settings,
        on_cancel_workflow,
        parent=None,
    ):
        super().__init__(parent)
        self.on_create_project = on_create_project
        self.on_open_project = on_open_project
        self.on_prepare_workflow = on_prepare_workflow
        self.on_open_voice_settings = on_open_voice_settings
        self.on_cancel_workflow = on_cancel_workflow
        self._manifest = None
        self._manifest_path: Path | None = None
        self._last_project_path: Path | None = None
        self._workflow_state = AutomationWorkflowState()
        self.stage_rows: dict[str, AutomationStageRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.view_stack = QStackedWidget()
        self.setup_view = self._build_setup_view()
        self.progress_view = self._build_progress_view()
        self.view_stack.addWidget(self.setup_view)
        self.view_stack.addWidget(self.progress_view)
        root.addWidget(self.view_stack)

    def _scroll_host(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)
        scroll.setWidget(content)
        return scroll, layout

    def _build_setup_view(self) -> QWidget:
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        scroll, layout = self._scroll_host()
        root.addWidget(scroll)

        hero = QFrame()
        hero.setObjectName("automationHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(5)

        hero_title = QLabel("Tạo video tự động")
        hero_title.setObjectName("pageTitle")
        hero_text = QLabel(
            "Dán kịch bản, chọn preset và để Creator Studio tự thực hiện các bước còn lại. "
            "Các công cụ kỹ thuật được đưa xuống khu vực Nâng cao."
        )
        hero_text.setObjectName("pageSubtitle")
        hero_text.setWordWrap(True)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_text)
        layout.addWidget(hero)

        project_card = Card()
        project_layout = QHBoxLayout(project_card)
        project_layout.setContentsMargins(18, 14, 18, 14)
        project_layout.setSpacing(12)

        project_text = QVBoxLayout()
        project_text.setSpacing(2)
        project_title = QLabel("DỰ ÁN")
        project_title.setObjectName("cardTitle")
        self.project_name_label = QLabel("Chưa mở dự án")
        self.project_name_label.setObjectName("projectValue")
        self.project_path_label = QLabel("Tạo dự án mới hoặc mở dự án hiện có để bắt đầu.")
        self.project_path_label.setObjectName("projectPath")
        self.project_path_label.setWordWrap(True)
        project_text.addWidget(project_title)
        project_text.addWidget(self.project_name_label)
        project_text.addWidget(self.project_path_label)

        create_button = QPushButton("Tạo dự án")
        create_button.setProperty("class", "primaryButton")
        create_button.setMinimumHeight(36)
        create_button.clicked.connect(self.on_create_project)

        open_button = QPushButton("Mở dự án")
        open_button.setProperty("class", "secondaryButton")
        open_button.setMinimumHeight(36)
        open_button.clicked.connect(self.on_open_project)

        project_layout.addLayout(project_text, 1)
        project_layout.addWidget(create_button)
        project_layout.addWidget(open_button)
        layout.addWidget(project_card)

        script_card = Card()
        script_layout = QVBoxLayout(script_card)
        script_layout.setContentsMargins(18, 16, 18, 18)
        script_layout.setSpacing(10)

        script_head = QHBoxLayout()
        script_title_box = QVBoxLayout()
        script_title_box.setSpacing(2)
        script_title = QLabel("Kịch bản")
        script_title.setObjectName("sectionTitle")
        script_hint = QLabel("Đây là đầu vào chính của quy trình tự động.")
        script_hint.setObjectName("muted")
        script_title_box.addWidget(script_title)
        script_title_box.addWidget(script_hint)

        self.language_combo = QComboBox()
        self.language_combo.addItem("Tiếng Việt", "vi")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Tự nhận diện", "und")
        self.language_combo.setFixedWidth(150)

        script_head.addLayout(script_title_box, 1)
        script_head.addWidget(self.language_combo, 0, Qt.AlignmentFlag.AlignTop)

        self.script_editor = QPlainTextEdit()
        self.script_editor.setPlaceholderText("Dán toàn bộ kịch bản video vào đây...")
        self.script_editor.setMinimumHeight(230)

        self.script_counter = QLabel("0 ký tự")
        self.script_counter.setObjectName("muted")
        self.script_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.script_editor.textChanged.connect(self._update_script_counter)

        script_layout.addLayout(script_head)
        script_layout.addWidget(self.script_editor)
        script_layout.addWidget(self.script_counter)
        layout.addWidget(script_card)

        config_card = Card()
        config_layout = QGridLayout(config_card)
        config_layout.setContentsMargins(18, 16, 18, 18)
        config_layout.setHorizontalSpacing(14)
        config_layout.setVerticalSpacing(8)

        config_title = QLabel("Thiết lập nhanh")
        config_title.setObjectName("sectionTitle")
        config_layout.addWidget(config_title, 0, 0, 1, 4)

        config_layout.addWidget(QLabel("Preset"), 1, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.PRESETS)
        config_layout.addWidget(self.preset_combo, 2, 0)

        config_layout.addWidget(QLabel("Chế độ"), 1, 1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Tự động hoàn toàn", "auto")
        self.mode_combo.addItem("Kiểm tra trước khi render", "review_before_render")
        self.mode_combo.addItem("Thủ công", "manual")
        config_layout.addWidget(self.mode_combo, 2, 1)

        config_layout.addWidget(QLabel("Tỷ lệ"), 1, 2)
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItem("16:9", "16:9")
        self.aspect_combo.addItem("9:16", "9:16")
        self.aspect_combo.addItem("1:1", "1:1")
        config_layout.addWidget(self.aspect_combo, 2, 2)

        config_layout.addWidget(QLabel("Chất lượng"), 1, 3)
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("1080p", "1080p")
        self.quality_combo.addItem("720p", "720p")
        config_layout.addWidget(self.quality_combo, 2, 3)

        for column in range(4):
            config_layout.setColumnStretch(column, 1)
        layout.addWidget(config_card)

        voice_card = Card()
        voice_layout = QHBoxLayout(voice_card)
        voice_layout.setContentsMargins(18, 14, 18, 14)
        voice_layout.setSpacing(12)
        voice_text = QVBoxLayout()
        voice_text.setSpacing(2)
        voice_title = QLabel("Giọng đọc")
        voice_title.setObjectName("sectionTitle")
        self.voice_summary = QLabel("Dùng cấu hình giọng đọc hiện tại của dự án")
        self.voice_summary.setObjectName("muted")
        self.voice_summary.setWordWrap(True)
        voice_text.addWidget(voice_title)
        voice_text.addWidget(self.voice_summary)
        voice_button = QPushButton("Thiết lập giọng đọc")
        voice_button.setProperty("class", "secondaryButton")
        voice_button.setMinimumHeight(36)
        voice_button.clicked.connect(self.on_open_voice_settings)
        voice_layout.addLayout(voice_text, 1)
        voice_layout.addWidget(voice_button)
        layout.addWidget(voice_card)

        advanced_toggle = QPushButton("▸ Tùy chọn nâng cao")
        advanced_toggle.setProperty("class", "secondaryButton")
        advanced_toggle.setCheckable(True)
        advanced_toggle.setMinimumHeight(36)
        advanced_toggle.toggled.connect(self._toggle_advanced_options)
        advanced_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.advanced_toggle = advanced_toggle
        layout.addWidget(advanced_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.advanced_options = Card()
        advanced_layout = QVBoxLayout(self.advanced_options)
        advanced_layout.setContentsMargins(18, 14, 18, 14)
        advanced_layout.setSpacing(9)
        self.stock_checkbox = QCheckBox("Tự động tìm video/ảnh stock")
        self.stock_checkbox.setChecked(True)
        self.ai_fallback_checkbox = QCheckBox("Dùng AI image khi không tìm được stock phù hợp")
        self.ai_fallback_checkbox.setChecked(True)
        self.music_checkbox = QCheckBox("Tự động thêm nhạc nền")
        self.music_checkbox.setChecked(True)
        advanced_layout.addWidget(self.stock_checkbox)
        advanced_layout.addWidget(self.ai_fallback_checkbox)
        advanced_layout.addWidget(self.music_checkbox)
        self.advanced_options.setVisible(False)
        layout.addWidget(self.advanced_options)

        action_card = Card()
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(18, 16, 18, 18)
        action_layout.setSpacing(9)
        self.start_button = QPushButton("TẠO VIDEO")
        self.start_button.setProperty("class", "primaryButton")
        self.start_button.setMinimumHeight(48)
        self.start_button.clicked.connect(self._start_requested)
        action_hint = QLabel(
            "Creator Studio sẽ tự tạo giọng đọc, chia cảnh và tạo truy vấn tìm tư liệu cho từng cảnh."
        )
        action_hint.setObjectName("muted")
        action_hint.setWordWrap(True)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(action_hint)
        layout.addWidget(action_card)
        layout.addStretch(1)
        return host

    def _build_progress_view(self) -> QWidget:
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        scroll, layout = self._scroll_host()
        root.addWidget(scroll)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Tiến trình tạo video")
        title.setObjectName("pageTitle")
        self.progress_project_label = QLabel("Chưa có dự án")
        self.progress_project_label.setObjectName("pageSubtitle")
        header_text.addWidget(title)
        header_text.addWidget(self.progress_project_label)
        back_button = QPushButton("← Quay lại thiết lập")
        back_button.setProperty("class", "secondaryButton")
        back_button.setMinimumHeight(36)
        back_button.clicked.connect(self.show_setup)
        header.addLayout(header_text, 1)
        header.addWidget(back_button)
        layout.addLayout(header)

        progress_card = Card()
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(18, 16, 18, 18)
        progress_layout.setSpacing(8)
        progress_head = QHBoxLayout()
        progress_title = QLabel("Tổng tiến trình")
        progress_title.setObjectName("sectionTitle")
        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName("statusIdle")
        progress_head.addWidget(progress_title)
        progress_head.addStretch(1)
        progress_head.addWidget(self.progress_percent_label)
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(False)
        self.overall_progress.setMinimumHeight(12)
        self.current_activity_label = QLabel("Sẵn sàng")
        self.current_activity_label.setStyleSheet("font-weight: 700; color: #eef4fb;")
        self.current_detail_label = QLabel("Chưa có bước nào đang chạy.")
        self.current_detail_label.setObjectName("muted")
        self.current_detail_label.setWordWrap(True)
        progress_layout.addLayout(progress_head)
        progress_layout.addWidget(self.overall_progress)
        progress_layout.addWidget(self.current_activity_label)
        progress_layout.addWidget(self.current_detail_label)
        layout.addWidget(progress_card)

        stages_card = Card()
        stages_layout = QVBoxLayout(stages_card)
        stages_layout.setContentsMargins(14, 14, 14, 14)
        stages_layout.setSpacing(8)
        stages_title = QLabel("Các bước tự động")
        stages_title.setObjectName("sectionTitle")
        stages_layout.addWidget(stages_title)
        for index, definition in enumerate(AUTOMATION_STAGES, start=1):
            row = AutomationStageRow(index, definition.label, definition.idle_detail)
            self.stage_rows[definition.key] = row
            stages_layout.addWidget(row)
        layout.addWidget(stages_card)

        control_card = Card()
        controls = QHBoxLayout(control_card)
        controls.setContentsMargins(18, 14, 18, 14)
        controls.setSpacing(10)
        self.runner_notice = QLabel(
            "Creator Studio đang điều phối quy trình. Bạn có thể theo dõi từng bước tại đây."
        )
        self.runner_notice.setObjectName("muted")
        self.runner_notice.setWordWrap(True)
        self.pause_button = QPushButton("Tạm dừng")
        self.pause_button.setProperty("class", "secondaryButton")
        self.pause_button.setEnabled(False)
        self.pause_button.setToolTip("Tạm dừng worker sẽ được bổ sung khi từng engine hỗ trợ pause an toàn.")
        self.cancel_button = QPushButton("Hủy")
        self.cancel_button.setProperty("class", "secondaryButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.on_cancel_workflow)
        controls.addWidget(self.runner_notice, 1)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.cancel_button)
        layout.addWidget(control_card)
        layout.addStretch(1)
        return host

    def _update_script_counter(self):
        text = self.script_editor.toPlainText()
        self.script_counter.setText(f"{len(text):,} ký tự")

    def _toggle_advanced_options(self, checked: bool):
        self.advanced_options.setVisible(bool(checked))
        self.advanced_toggle.setText("▾ Tùy chọn nâng cao" if checked else "▸ Tùy chọn nâng cao")

    def set_project(self, manifest: ProjectManifest | None, manifest_path: Path | None):
        self._manifest = manifest
        self._manifest_path = Path(manifest_path).resolve() if manifest_path is not None else None
        if manifest is None:
            self.project_name_label.setText("Chưa mở dự án")
            self.project_path_label.setText("Tạo dự án mới hoặc mở dự án hiện có để bắt đầu.")
            self.progress_project_label.setText("Chưa có dự án")
            if self._last_project_path is not None:
                self.script_editor.clear()
                self.script_editor.document().setModified(False)
            self._last_project_path = None
            return

        self.project_name_label.setText(str(getattr(manifest, "project_name", "Dự án")))
        self.project_path_label.setText(str(self._manifest_path.parent if self._manifest_path else ""))
        self.progress_project_label.setText(f"Dự án: {getattr(manifest, 'project_name', 'Dự án')}")

        project_changed = self._last_project_path != self._manifest_path
        content = getattr(manifest, "content", None)
        script = str(getattr(content, "script", "") or "")
        language = str(getattr(content, "source_language", "") or "und")
        if project_changed or not self.script_editor.document().isModified():
            self.script_editor.setPlainText(script)
            self.script_editor.document().setModified(False)
            matched = False
            for index in range(self.language_combo.count()):
                if self.language_combo.itemData(index) == language:
                    self.language_combo.setCurrentIndex(index)
                    matched = True
                    break
            if not matched and language:
                self.language_combo.addItem(language, language)
                self.language_combo.setCurrentIndex(self.language_combo.count() - 1)
        self._last_project_path = self._manifest_path

    def set_voice_summary(self, text: str):
        self.voice_summary.setText(str(text or "Dùng cấu hình giọng đọc hiện tại của dự án"))

    def workflow_config(self) -> dict:
        return {
            "preset": self.preset_combo.currentText(),
            "mode": self.mode_combo.currentData(),
            "aspect_ratio": self.aspect_combo.currentData(),
            "quality": self.quality_combo.currentData(),
            "use_stock": self.stock_checkbox.isChecked(),
            "use_ai_fallback": self.ai_fallback_checkbox.isChecked(),
            "use_music": self.music_checkbox.isChecked(),
        }

    def selected_language(self) -> str:
        return str(self.language_combo.currentData() or "und")

    def _start_requested(self):
        if self._manifest is None or self._manifest_path is None:
            QMessageBox.information(self, "Tạo video", "Hãy tạo hoặc mở dự án trước.")
            return
        script = self.script_editor.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "Tạo video", "Kịch bản không được để trống.")
            return
        state = self.on_prepare_workflow(
            script,
            self.selected_language(),
            self.workflow_config(),
        )
        if isinstance(state, AutomationWorkflowState):
            self.script_editor.document().setModified(False)
            self.show_progress(state)

    def show_setup(self):
        self.view_stack.setCurrentWidget(self.setup_view)

    def show_progress(self, state: AutomationWorkflowState | None = None):
        if state is not None:
            self._workflow_state = state
        self.apply_workflow_state(self._workflow_state)
        self.view_stack.setCurrentWidget(self.progress_view)

    def apply_workflow_state(self, state: AutomationWorkflowState):
        self._workflow_state = state
        active_key = state.current_stage_key()
        stage_by_key = {item.key: item for item in state.stages}

        for definition in AUTOMATION_STAGES:
            stage = stage_by_key.get(definition.key)
            if stage is None:
                continue
            self.stage_rows[definition.key].set_stage_state(
                stage.status,
                stage.detail or definition.idle_detail,
                active=definition.key == active_key,
            )

        progress = state.overall_progress()
        self.overall_progress.setValue(progress)
        self.progress_percent_label.setText(f"{progress}%")

        if active_key is None:
            self.current_activity_label.setText("✓ Quy trình đã hoàn tất")
            self.current_detail_label.setText(state.message or "Tất cả bước đã hoàn thành.")
            return

        definition = next((item for item in AUTOMATION_STAGES if item.key == active_key), None)
        active = stage_by_key.get(active_key)
        if definition is None or active is None:
            self.current_activity_label.setText("Sẵn sàng")
            self.current_detail_label.setText(state.message)
            return

        if active.status == AutomationStageStatus.RUNNING:
            self.current_activity_label.setText(f"● {definition.label}")
        elif active.status == AutomationStageStatus.FAILED:
            self.current_activity_label.setText(f"! {definition.label}")
        else:
            self.current_activity_label.setText(f"Bước tiếp theo: {definition.label}")
        self.current_detail_label.setText(active.detail or definition.idle_detail)

    def set_runner_controls_enabled(self, enabled: bool):
        # M109.2 supports cooperative cancel.  Pause stays disabled until the
        # active provider/worker can be paused without corrupting output.
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(bool(enabled))


class ProjectCreationDialog(QDialog):
    """Create a project at a user-selected parent directory."""

    def __init__(self, default_parent: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tạo dự án mới")
        self.setMinimumWidth(720)
        self.setStyleSheet(API_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Tạo dự án Creator Studio")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        help_text = QLabel(
            "Dự án sẽ được lưu độc lập với thư mục cài AI Video Editor. "
            "Hãy chọn ổ đĩa hoặc thư mục mà bạn muốn dùng lâu dài để quản lý dự án."
        )
        help_text.setObjectName("muted")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        name_label = QLabel("Tên dự án")
        name_label.setObjectName("muted")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ví dụ: Rural Vietnam 001")

        location_label = QLabel("Nơi lưu")
        location_label.setObjectName("muted")
        self.location_edit = QLineEdit(str(Path(default_parent).expanduser()))
        self.location_edit.setReadOnly(True)
        self.location_button = QPushButton("Chọn thư mục")
        self.location_button.setProperty("class", "secondaryButton")
        self.location_button.clicked.connect(self._choose_location)

        preview_label = QLabel("Dự án sẽ được tạo tại")
        preview_label.setObjectName("muted")
        self.preview_value = QLabel("-")
        self.preview_value.setObjectName("projectPath")
        self.preview_value.setWordWrap(True)
        self.preview_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_edit, 0, 1, 1, 2)
        grid.addWidget(location_label, 1, 0)
        grid.addWidget(self.location_edit, 1, 1)
        grid.addWidget(self.location_button, 1, 2)
        grid.addWidget(preview_label, 2, 0)
        grid.addWidget(self.preview_value, 2, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Tạo dự án")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        buttons.accepted.connect(self._accept_checked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_edit.textChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def _choose_location(self):
        start = self.location_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn nơi lưu dự án",
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self.location_edit.setText(selected)
            self._refresh_preview()

    def _refresh_preview(self):
        name = self.name_edit.text().strip()
        parent = self.location_edit.text().strip()
        if not name or not parent:
            self.preview_value.setText("-")
            return
        self.preview_value.setText(str(Path(parent) / storage_safe_slug(name, "project")))

    def _accept_checked(self):
        name = self.name_edit.text().strip()
        parent = Path(self.location_edit.text().strip()).expanduser()
        if not name:
            QMessageBox.warning(self, "Tạo dự án", "Tên dự án không được để trống.")
            return
        if not parent.is_dir():
            QMessageBox.warning(self, "Tạo dự án", "Nơi lưu dự án không tồn tại hoặc không phải thư mục.")
            return
        target = parent / storage_safe_slug(name, "project")
        if target.exists():
            QMessageBox.warning(
                self,
                "Tạo dự án",
                "Thư mục dự án đã tồn tại. Hãy đổi tên dự án hoặc chọn nơi lưu khác.\n\n"
                f"{target}",
            )
            return
        self.accept()

    def project_name(self) -> str:
        return self.name_edit.text().strip()

    def parent_directory(self) -> Path:
        return Path(self.location_edit.text().strip()).expanduser().resolve()

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
            "Tạo, mở và quản lý dự án Creator Studio. Dự án mới có thể lưu ở bất kỳ thư mục nào bạn chọn; ProjectManifest vẫn là dữ liệu chính."
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

        self.notice = QLabel("Chưa mở dự án nào.")
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
        self.project_folder_value = self._make_value("-", path=True)
        self.project_folder_value.setWordWrap(True)
        self.project_folder_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.project_path_value = self._make_value("-", path=True)
        self.project_path_value.setWordWrap(True)
        self.project_path_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        rows = [
            ("Tên dự án", self.project_name_value),
            ("Trạng thái", self.project_status_value),
            ("Mã dự án", self.project_id_value),
            ("Phiên bản dữ liệu", self.project_schema_value),
            ("Thư mục dự án", self.project_folder_value),
            ("Tệp dữ liệu dự án", self.project_path_value),
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
        self.media_value = self._summary_metric("Tư liệu", "0")
        self.timeline_value = self._summary_metric("Dòng thời gian", "0")
        self.inputs_value = self._summary_metric("Đầu vào", "0")

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
            "M106 tiếp tục mô hình lưu trữ theo dự án: voice, ảnh và video là các asset riêng, không ghi đè. Image/Video Asset Library chỉ quản lý tệp dự án; việc gán asset vào cảnh sẽ được thực hiện ở milestone tiếp theo."
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
            self.project_folder_value.setText("-")
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
        status_text = {
            "pending": "Đang chờ",
            "running": "Đang xử lý",
            "completed": "Hoàn tất",
            "failed": "Thất bại",
            "cancelled": "Đã hủy",
        }.get(str(status_text).lower(), str(status_text))

        self.project_name_value.setText(manifest.project_name)
        self.project_status_value.setText(status_text)
        self.project_id_value.setText(str(manifest.project_id))
        self.project_schema_value.setText(str(manifest.schema_version))
        self.project_folder_value.setText(str(Path(manifest_path).parent))
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



class VoiceScriptPage(QWidget):
    def __init__(
        self,
        select_voice_callback,
        preview_voice_callback,
        clear_voice_callback,
        import_script_callback,
        save_script_callback,
        clear_script_callback,
        run_voice_pipeline_callback,
        open_output_folder_callback,
        open_history_folder_callback,
        tts_provider_changed_callback,
        tts_engine_changed_callback,
        tts_preview_callback,
        tts_pause_preview_callback,
        tts_stop_preview_callback,
        tts_generate_callback,
        open_script_folder_callback,
        clone_select_audio_callback,
        clone_create_callback,
        voice_asset_refresh_callback,
        voice_asset_preview_callback,
        voice_asset_use_callback,
        voice_asset_open_folder_callback,
    ):
        super().__init__()

        self._loading_project = False
        self._script_dirty = False
        self._voice_path: Path | None = None
        self._manifest_path: Path | None = None
        self._tts_busy = False
        self._clone_busy = False
        self._clone_available = False
        self._clone_reference_path: Path | None = None
        self._pipeline_busy = False
        self._preview_active = False
        self._preview_paused = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Giọng đọc + Kịch bản")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Quản lý file giọng đọc hoặc tạo giọng đọc trực tiếp từ kịch bản. "
            "Có thể dùng Piper Local hoặc VoiceStudio Local qua cùng TTSService; provider cloud/VPS có thể bổ sung sau."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.project_notice = QLabel("Hãy tạo hoặc mở một dự án trước khi làm việc với giọng đọc và kịch bản.")
        self.project_notice.setObjectName("statusWarn")
        self.project_notice.setWordWrap(True)
        layout.addWidget(self.project_notice)

        voice_card = Card()
        voice_layout = QVBoxLayout(voice_card)
        voice_layout.setContentsMargins(20, 18, 20, 20)
        voice_layout.setSpacing(12)

        voice_title = QLabel("Giọng đọc")
        voice_title.setObjectName("sectionTitle")
        voice_layout.addWidget(voice_title)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(22)
        mode_label = QLabel("Nguồn giọng đọc:")
        mode_label.setObjectName("muted")
        self.imported_mode_radio = QRadioButton("Dùng tệp có sẵn")
        self.generated_mode_radio = QRadioButton("Tạo từ kịch bản (TTS)")
        self.voice_mode_group = QButtonGroup(self)
        self.voice_mode_group.addButton(self.imported_mode_radio)
        self.voice_mode_group.addButton(self.generated_mode_radio)
        self.imported_mode_radio.setChecked(True)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.imported_mode_radio)
        mode_row.addWidget(self.generated_mode_radio)
        mode_row.addStretch(1)
        voice_layout.addLayout(mode_row)

        self.imported_voice_panel = QFrame()
        imported_layout = QVBoxLayout(self.imported_voice_panel)
        imported_layout.setContentsMargins(0, 4, 0, 0)
        imported_layout.setSpacing(10)

        voice_info = QGridLayout()
        voice_info.setHorizontalSpacing(18)
        voice_info.setVerticalSpacing(8)

        self.voice_name_value = QLabel("Chưa chọn tệp")
        self.voice_name_value.setObjectName("projectValue")
        self.voice_path_value = QLabel("-")
        self.voice_path_value.setObjectName("projectPath")
        self.voice_path_value.setWordWrap(True)
        self.voice_path_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        label_name = QLabel("Tệp giọng đọc hiện tại")
        label_name.setObjectName("muted")
        label_path = QLabel("Đường dẫn")
        label_path.setObjectName("muted")

        voice_info.addWidget(label_name, 0, 0)
        voice_info.addWidget(self.voice_name_value, 0, 1)
        voice_info.addWidget(label_path, 1, 0)
        voice_info.addWidget(self.voice_path_value, 1, 1)
        voice_info.setColumnStretch(1, 1)
        imported_layout.addLayout(voice_info)

        voice_actions = QHBoxLayout()
        voice_actions.setSpacing(10)

        self.select_voice_button = QPushButton("Chọn tệp giọng đọc")
        self.select_voice_button.setProperty("class", "primaryButton")
        self.select_voice_button.clicked.connect(select_voice_callback)

        self.preview_voice_button = QPushButton("Nghe tệp hiện tại")
        self.preview_voice_button.setProperty("class", "secondaryButton")
        self.preview_voice_button.clicked.connect(preview_voice_callback)

        self.clear_voice_button = QPushButton("Bỏ giọng đọc")
        self.clear_voice_button.setProperty("class", "secondaryButton")
        self.clear_voice_button.clicked.connect(clear_voice_callback)

        for button in (
            self.select_voice_button,
            self.preview_voice_button,
            self.clear_voice_button,
        ):
            button.setMinimumHeight(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            voice_actions.addWidget(button)
        voice_actions.addStretch(1)
        imported_layout.addLayout(voice_actions)
        voice_layout.addWidget(self.imported_voice_panel)

        self.tts_panel = QFrame()
        tts_layout = QVBoxLayout(self.tts_panel)
        tts_layout.setContentsMargins(0, 8, 0, 0)
        tts_layout.setSpacing(10)

        tts_grid = QGridLayout()
        tts_grid.setHorizontalSpacing(14)
        tts_grid.setVerticalSpacing(10)

        provider_label = QLabel("Nhà cung cấp")
        provider_label.setObjectName("muted")
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.setMinimumWidth(300)
        self.tts_provider_combo.currentIndexChanged.connect(tts_provider_changed_callback)

        self.tts_engine_label = QLabel("Engine / Model")
        self.tts_engine_label.setObjectName("muted")
        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.setMinimumWidth(420)
        self.tts_engine_combo.setToolTip("Chọn engine TTS chạy bên trong VoiceStudio Local.")
        self.tts_engine_combo.currentIndexChanged.connect(tts_engine_changed_callback)

        tts_voice_label = QLabel("Giọng đọc")
        tts_voice_label.setObjectName("muted")
        self.tts_voice_combo = QComboBox()
        self.tts_voice_combo.setMinimumWidth(420)
        self.tts_voice_combo.setToolTip("Giọng preset hoặc voice profile đã lưu trong VoiceStudio.")

        speed_label = QLabel("Tốc độ")
        speed_label.setObjectName("muted")
        self.tts_speed_spin = QDoubleSpinBox()
        self.tts_speed_spin.setRange(0.50, 2.00)
        self.tts_speed_spin.setSingleStep(0.05)
        self.tts_speed_spin.setDecimals(2)
        self.tts_speed_spin.setValue(1.00)
        self.tts_speed_spin.setMinimumWidth(92)
        self.tts_speed_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.tts_speed_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tts_speed_spin.setToolTip("1.00 = tốc độ gốc; nhỏ hơn đọc chậm, lớn hơn đọc nhanh.")

        speed_control = QWidget()
        speed_control_layout = QHBoxLayout(speed_control)
        speed_control_layout.setContentsMargins(0, 0, 0, 0)
        speed_control_layout.setSpacing(4)
        speed_control_layout.addWidget(self.tts_speed_spin)
        self.tts_speed_down_button = QPushButton("▼")
        self.tts_speed_up_button = QPushButton("▲")
        for button in (self.tts_speed_down_button, self.tts_speed_up_button):
            button.setObjectName("spinStepButton")
            button.setFixedSize(30, 30)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tts_speed_down_button.setToolTip("Giảm tốc độ 0.05")
        self.tts_speed_up_button.setToolTip("Tăng tốc độ 0.05")
        self.tts_speed_down_button.clicked.connect(self.tts_speed_spin.stepDown)
        self.tts_speed_up_button.clicked.connect(self.tts_speed_spin.stepUp)
        speed_control_layout.addWidget(self.tts_speed_down_button)
        speed_control_layout.addWidget(self.tts_speed_up_button)

        self.tts_refresh_button = QPushButton("Làm mới giọng")
        self.tts_refresh_button.setProperty("class", "projectButton")
        self.tts_refresh_button.setMinimumHeight(34)
        self.tts_refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tts_refresh_button.setToolTip("Kiểm tra lại VoiceStudio/Piper và làm mới engine + danh sách giọng.")
        self.tts_refresh_button.clicked.connect(tts_provider_changed_callback)

        tts_grid.addWidget(provider_label, 0, 0)
        tts_grid.addWidget(self.tts_provider_combo, 0, 1)
        tts_grid.addWidget(speed_label, 0, 2)
        tts_grid.addWidget(speed_control, 0, 3)
        tts_grid.addWidget(self.tts_engine_label, 1, 0)
        tts_grid.addWidget(self.tts_engine_combo, 1, 1, 1, 3)
        tts_grid.addWidget(tts_voice_label, 2, 0)
        tts_grid.addWidget(self.tts_voice_combo, 2, 1)
        tts_grid.addWidget(self.tts_refresh_button, 2, 2, 1, 2)
        tts_grid.setColumnStretch(1, 1)
        tts_layout.addLayout(tts_grid)

        self.tts_health_label = QLabel("Đang kiểm tra nhà cung cấp TTS...")
        self.tts_health_label.setObjectName("muted")
        self.tts_health_label.setWordWrap(True)
        tts_layout.addWidget(self.tts_health_label)

        tts_actions = QHBoxLayout()
        tts_actions.setSpacing(10)
        self.tts_preview_button = QPushButton("Nghe thử giọng")
        self.tts_preview_button.setProperty("class", "secondaryButton")
        self.tts_preview_button.clicked.connect(tts_preview_callback)

        self.tts_pause_preview_button = QPushButton("Tạm dừng")
        self.tts_pause_preview_button.setProperty("class", "secondaryButton")
        self.tts_pause_preview_button.clicked.connect(tts_pause_preview_callback)
        self.tts_pause_preview_button.setToolTip("Tạm dừng hoặc tiếp tục đoạn nghe thử hiện tại.")

        self.tts_stop_preview_button = QPushButton("Dừng")
        self.tts_stop_preview_button.setProperty("class", "secondaryButton")
        self.tts_stop_preview_button.clicked.connect(tts_stop_preview_callback)
        self.tts_stop_preview_button.setToolTip("Dừng ngay đoạn nghe thử hiện tại.")

        self.tts_generate_button = QPushButton("Tạo giọng đọc từ kịch bản")
        self.tts_generate_button.setProperty("class", "primaryButton")
        self.tts_generate_button.clicked.connect(tts_generate_callback)

        self.saved_scripts_button = QPushButton("Kịch bản đã lưu")
        self.saved_scripts_button.setProperty("class", "secondaryButton")
        self.saved_scripts_button.setToolTip(
            "Mở thư mục chứa kịch bản đã lưu của dự án hiện tại."
        )
        self.saved_scripts_button.clicked.connect(open_script_folder_callback)

        for button in (
            self.tts_preview_button,
            self.tts_pause_preview_button,
            self.tts_stop_preview_button,
            self.tts_generate_button,
            self.saved_scripts_button,
        ):
            button.setMinimumHeight(40)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            tts_actions.addWidget(button)
        tts_actions.addStretch(1)
        tts_layout.addLayout(tts_actions)

        self.voice_clone_panel = QFrame()
        self.voice_clone_panel.setObjectName("subtlePanel")
        clone_layout = QVBoxLayout(self.voice_clone_panel)
        clone_layout.setContentsMargins(14, 14, 14, 14)
        clone_layout.setSpacing(10)

        clone_title = QLabel("Clone giọng · VoiceStudio Local")
        clone_title.setObjectName("sectionTitle")
        clone_layout.addWidget(clone_title)

        clone_help = QLabel(
            "Tạo voice profile cục bộ từ audio mẫu. Khuyến nghị dùng đoạn nói rõ, một người, khoảng 3–10 giây. "
            "Transcript là tùy chọn; nếu để trống VoiceStudio có thể dùng ASR cục bộ đã cài để nhận dạng."
        )
        clone_help.setObjectName("muted")
        clone_help.setWordWrap(True)
        clone_layout.addWidget(clone_help)

        clone_grid = QGridLayout()
        clone_grid.setHorizontalSpacing(12)
        clone_grid.setVerticalSpacing(9)

        clone_name_label = QLabel("Tên giọng")
        clone_name_label.setObjectName("muted")
        self.clone_name_edit = QLineEdit()
        self.clone_name_edit.setObjectName("cloneNameEdit")
        self.clone_name_edit.setPlaceholderText("Ví dụ: Giọng của tôi")
        self.clone_name_edit.textChanged.connect(self._refresh_action_states)

        clone_language_label = QLabel("Ngôn ngữ mẫu")
        clone_language_label.setObjectName("muted")
        self.clone_language_combo = QComboBox()
        for label, value in (
            ("Tự động", "Auto"),
            ("English", "English"),
            ("Vietnamese", "Vietnamese"),
            ("Chinese", "Chinese"),
            ("Japanese", "Japanese"),
            ("Korean", "Korean"),
            ("Spanish", "Spanish"),
        ):
            self.clone_language_combo.addItem(label, value)

        clone_audio_label = QLabel("Audio mẫu")
        clone_audio_label.setObjectName("muted")
        self.clone_audio_value = QLabel("Chưa chọn audio mẫu")
        self.clone_audio_value.setObjectName("projectPath")
        self.clone_audio_value.setWordWrap(True)
        self.clone_audio_button = QPushButton("Chọn audio mẫu")
        self.clone_audio_button.setProperty("class", "secondaryButton")
        self.clone_audio_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clone_audio_button.clicked.connect(clone_select_audio_callback)

        clone_grid.addWidget(clone_name_label, 0, 0)
        clone_grid.addWidget(self.clone_name_edit, 0, 1)
        clone_grid.addWidget(clone_language_label, 0, 2)
        clone_grid.addWidget(self.clone_language_combo, 0, 3)
        clone_grid.addWidget(clone_audio_label, 1, 0)
        clone_grid.addWidget(self.clone_audio_value, 1, 1, 1, 2)
        clone_grid.addWidget(self.clone_audio_button, 1, 3)
        clone_grid.setColumnStretch(1, 1)
        clone_grid.setColumnStretch(2, 0)
        clone_layout.addLayout(clone_grid)

        clone_transcript_label = QLabel("Transcript của audio mẫu (tùy chọn)")
        clone_transcript_label.setObjectName("muted")
        clone_layout.addWidget(clone_transcript_label)
        self.clone_transcript_edit = QPlainTextEdit()
        self.clone_transcript_edit.setPlaceholderText(
            "Nếu biết chính xác audio mẫu đang nói gì, nhập nguyên văn tại đây để clone ổn định hơn."
        )
        self.clone_transcript_edit.setMaximumHeight(90)
        clone_layout.addWidget(self.clone_transcript_edit)

        self.clone_permission_check = QCheckBox(
            "Tôi xác nhận mình sở hữu giọng này hoặc đã được người sở hữu cho phép clone và sử dụng."
        )
        self.clone_permission_check.toggled.connect(self._refresh_action_states)
        clone_layout.addWidget(self.clone_permission_check)

        clone_action_row = QHBoxLayout()
        self.clone_create_button = QPushButton("Tạo giọng clone")
        self.clone_create_button.setProperty("class", "primaryButton")
        self.clone_create_button.setMinimumHeight(38)
        self.clone_create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clone_create_button.clicked.connect(clone_create_callback)
        clone_action_row.addWidget(self.clone_create_button)
        clone_action_row.addStretch(1)
        clone_layout.addLayout(clone_action_row)

        self.clone_status_label = QLabel("Voice clone được lưu cục bộ trong VoiceStudio và sẽ xuất hiện trong danh sách Giọng đọc.")
        self.clone_status_label.setObjectName("muted")
        self.clone_status_label.setWordWrap(True)
        clone_layout.addWidget(self.clone_status_label)

        self.voice_clone_panel.setVisible(False)
        tts_layout.addWidget(self.voice_clone_panel)

        tts_note = QLabel(
            "Piper chạy trong runtime riêng; VoiceStudio dùng API loopback cục bộ. Nghe thử dùng WAV tạm và tự xóa. Mỗi lần tạo giọng chính thức sẽ sinh một Voice Asset riêng trong assets/voice/generated và không ghi đè file cũ."
        )
        tts_note.setObjectName("muted")
        tts_note.setWordWrap(True)
        tts_layout.addWidget(tts_note)
        voice_layout.addWidget(self.tts_panel)

        # Common workspace location, visible in both imported and generated modes.
        # This removes ambiguity about where generated_voice.wav and VoicePipeline
        # artifacts are stored.
        self.voice_workspace_panel = QFrame()
        self.voice_workspace_panel.setObjectName("subtlePanel")
        workspace_layout = QGridLayout(self.voice_workspace_panel)
        workspace_layout.setContentsMargins(14, 12, 14, 12)
        workspace_layout.setHorizontalSpacing(12)
        workspace_layout.setVerticalSpacing(8)

        workspace_title = QLabel("Thư mục làm việc giọng đọc")
        workspace_title.setObjectName("sectionTitle")
        workspace_layout.addWidget(workspace_title, 0, 0, 1, 3)

        workspace_path_label = QLabel("Thư mục")
        workspace_path_label.setObjectName("muted")
        self.voice_workspace_path_value = QLabel("-")
        self.voice_workspace_path_value.setObjectName("projectPath")
        self.voice_workspace_path_value.setWordWrap(True)
        self.voice_workspace_path_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.voice_workspace_open_button = QPushButton("Mở thư mục")
        self.voice_workspace_open_button.setProperty("class", "secondaryButton")
        self.voice_workspace_open_button.setMinimumHeight(34)
        self.voice_workspace_open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_workspace_open_button.clicked.connect(open_output_folder_callback)

        current_voice_label = QLabel("Tệp giọng hiện tại")
        current_voice_label.setObjectName("muted")
        self.workspace_voice_value = QLabel("Chưa có")
        self.workspace_voice_value.setObjectName("projectPath")
        self.workspace_voice_value.setWordWrap(True)
        self.workspace_voice_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        assets_label = QLabel("Tệp xử lý")
        assets_label.setObjectName("muted")
        self.workspace_assets_value = QLabel("Chưa có")
        self.workspace_assets_value.setObjectName("muted")
        self.workspace_assets_value.setWordWrap(True)

        history_label = QLabel("Lịch sử")
        history_label.setObjectName("muted")
        self.workspace_history_value = QLabel("Chưa có bản lưu lịch sử.")
        self.workspace_history_value.setObjectName("muted")
        self.workspace_history_value.setWordWrap(True)
        self.voice_history_open_button = QPushButton("Mở lịch sử")
        self.voice_history_open_button.setProperty("class", "secondaryButton")
        self.voice_history_open_button.setMinimumHeight(34)
        self.voice_history_open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_history_open_button.clicked.connect(open_history_folder_callback)

        workspace_layout.addWidget(workspace_path_label, 1, 0)
        workspace_layout.addWidget(self.voice_workspace_path_value, 1, 1)
        workspace_layout.addWidget(self.voice_workspace_open_button, 1, 2)
        workspace_layout.addWidget(current_voice_label, 2, 0)
        workspace_layout.addWidget(self.workspace_voice_value, 2, 1, 1, 2)
        workspace_layout.addWidget(assets_label, 3, 0)
        workspace_layout.addWidget(self.workspace_assets_value, 3, 1, 1, 2)
        workspace_layout.addWidget(history_label, 4, 0)
        workspace_layout.addWidget(self.workspace_history_value, 4, 1)
        workspace_layout.addWidget(self.voice_history_open_button, 4, 2)
        workspace_layout.setColumnStretch(1, 1)

        # M105: do not show the technical voice_workspace panel in the UI.
        # The internal objects remain available for compatibility with existing
        # status/history logic.
        self.voice_workspace_panel.setVisible(False)

        self.voice_notice = QLabel("Chưa có giọng đọc trong dự án.")
        self.voice_notice.setObjectName("muted")
        self.voice_notice.setWordWrap(True)
        voice_layout.addWidget(self.voice_notice)
        layout.addWidget(voice_card)

        self.imported_mode_radio.toggled.connect(self._sync_voice_mode_ui)
        self.generated_mode_radio.toggled.connect(self._sync_voice_mode_ui)

        asset_card = Card()
        asset_layout = QVBoxLayout(asset_card)
        asset_layout.setContentsMargins(20, 18, 20, 20)
        asset_layout.setSpacing(10)

        asset_header = QHBoxLayout()
        asset_title = QLabel("Thư viện giọng của dự án")
        asset_title.setObjectName("sectionTitle")
        asset_header.addWidget(asset_title)
        asset_header.addStretch(1)
        self.voice_asset_count = QLabel("0 tệp")
        self.voice_asset_count.setObjectName("muted")
        asset_header.addWidget(self.voice_asset_count)
        asset_layout.addLayout(asset_header)

        asset_help = QLabel(
            "Mỗi giọng được tạo hoặc nhập vào dự án là một asset riêng. "
            "Tạo giọng mới không ghi đè asset cũ; ProjectManifest chỉ trỏ tới giọng đang được dùng."
        )
        asset_help.setObjectName("muted")
        asset_help.setWordWrap(True)
        asset_layout.addWidget(asset_help)

        self.voice_asset_table = QTableWidget(0, 6)
        self.voice_asset_table.setHorizontalHeaderLabels(
            ["Tên", "Loại", "Provider / Engine", "Giọng", "Thời lượng", "Ngày tạo"]
        )
        self.voice_asset_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.voice_asset_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.voice_asset_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.voice_asset_table.setAlternatingRowColors(False)
        self.voice_asset_table.verticalHeader().setVisible(False)
        self.voice_asset_table.setMinimumHeight(185)
        header = self.voice_asset_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.voice_asset_table.itemSelectionChanged.connect(self._refresh_voice_asset_buttons)
        asset_layout.addWidget(self.voice_asset_table)

        asset_actions = QHBoxLayout()
        asset_actions.setSpacing(10)
        self.voice_asset_refresh_button = QPushButton("Làm mới thư viện")
        self.voice_asset_preview_button = QPushButton("Nghe tệp")
        self.voice_asset_use_button = QPushButton("Dùng làm giọng hiện tại")
        self.voice_asset_open_button = QPushButton("Mở thư mục asset")
        self.voice_asset_use_button.setProperty("class", "primaryButton")
        for button in (
            self.voice_asset_refresh_button,
            self.voice_asset_preview_button,
            self.voice_asset_use_button,
            self.voice_asset_open_button,
        ):
            if button is not self.voice_asset_use_button:
                button.setProperty("class", "secondaryButton")
            button.setMinimumHeight(36)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            asset_actions.addWidget(button)
        asset_actions.addStretch(1)
        asset_layout.addLayout(asset_actions)

        self.voice_asset_refresh_button.clicked.connect(voice_asset_refresh_callback)
        self.voice_asset_preview_button.clicked.connect(voice_asset_preview_callback)
        self.voice_asset_use_button.clicked.connect(voice_asset_use_callback)
        self.voice_asset_open_button.clicked.connect(voice_asset_open_folder_callback)
        self._refresh_voice_asset_buttons()
        layout.addWidget(asset_card)

        script_card = Card()
        script_layout = QVBoxLayout(script_card)
        script_layout.setContentsMargins(20, 18, 20, 20)
        script_layout.setSpacing(12)

        script_header = QHBoxLayout()
        script_header.setSpacing(10)
        script_title = QLabel("Kịch bản")
        script_title.setObjectName("sectionTitle")
        script_header.addWidget(script_title)
        script_header.addStretch(1)

        language_label = QLabel("Ngôn ngữ:")
        language_label.setObjectName("muted")
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Tiếng Việt", "vi")
        self.language_combo.addItem("Không xác định", "und")
        script_header.addWidget(language_label)
        script_header.addWidget(self.language_combo)
        script_layout.addLayout(script_header)

        script_actions = QHBoxLayout()
        script_actions.setSpacing(10)

        self.import_script_button = QPushButton("Nhập từ TXT")
        self.import_script_button.setProperty("class", "secondaryButton")
        self.import_script_button.clicked.connect(import_script_callback)

        self.save_script_button = QPushButton("Lưu kịch bản")
        self.save_script_button.setProperty("class", "primaryButton")
        self.save_script_button.clicked.connect(save_script_callback)

        self.clear_script_button = QPushButton("Xóa kịch bản")
        self.clear_script_button.setProperty("class", "secondaryButton")
        self.clear_script_button.clicked.connect(clear_script_callback)

        for button in (
            self.import_script_button,
            self.save_script_button,
            self.clear_script_button,
        ):
            button.setMinimumHeight(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            script_actions.addWidget(button)
        script_actions.addStretch(1)
        script_layout.addLayout(script_actions)

        self.script_editor = QPlainTextEdit()
        self.script_editor.setPlaceholderText("Nhập hoặc dán nội dung kịch bản tại đây...")
        self.script_editor.setMinimumHeight(250)
        self.script_editor.textChanged.connect(self._on_script_changed)
        script_layout.addWidget(self.script_editor)

        script_footer = QHBoxLayout()
        self.script_status = QLabel("Chưa có kịch bản.")
        self.script_status.setObjectName("muted")
        self.script_stats = QLabel("Từ: 0   ·   Ký tự: 0")
        self.script_stats.setObjectName("muted")
        script_footer.addWidget(self.script_status)
        script_footer.addStretch(1)
        script_footer.addWidget(self.script_stats)
        script_layout.addLayout(script_footer)
        layout.addWidget(script_card)

        process_card = Card()
        process_layout = QVBoxLayout(process_card)
        process_layout.setContentsMargins(20, 18, 20, 20)
        process_layout.setSpacing(12)

        process_title = QLabel("Xử lý giọng đọc")
        process_title.setObjectName("sectionTitle")
        process_layout.addWidget(process_title)

        process_text = QLabel(
            "Sau khi có file giọng đọc (nhập từ máy hoặc tạo bằng TTS), sử dụng VoicePipeline hiện có: "
            "Whisper → làm sạch bản chép lời → SRT → tạo cảnh speech/gap."
        )
        process_text.setObjectName("muted")
        process_text.setWordWrap(True)
        process_layout.addWidget(process_text)

        process_actions = QHBoxLayout()
        process_actions.setSpacing(10)

        self.run_pipeline_button = QPushButton("Chép lời + Tạo phụ đề + Cảnh")
        self.run_pipeline_button.setProperty("class", "primaryButton")
        self.run_pipeline_button.setMinimumHeight(40)
        self.run_pipeline_button.clicked.connect(run_voice_pipeline_callback)

        self.open_output_button = QPushButton("Mở thư mục giọng đọc")
        self.open_output_button.setProperty("class", "secondaryButton")
        self.open_output_button.setMinimumHeight(40)
        self.open_output_button.clicked.connect(open_output_folder_callback)

        process_actions.addWidget(self.run_pipeline_button)
        process_actions.addWidget(self.open_output_button)
        process_actions.addStretch(1)
        process_layout.addLayout(process_actions)

        self.process_status = QLabel("Chưa xử lý.")
        self.process_status.setObjectName("muted")
        self.process_status.setWordWrap(True)
        process_layout.addWidget(self.process_status)

        self.process_log = QPlainTextEdit()
        self.process_log.setReadOnly(True)
        self.process_log.setMaximumBlockCount(400)
        self.process_log.setMinimumHeight(105)
        self.process_log.setPlaceholderText("Nhật ký xử lý sẽ hiển thị tại đây.")
        process_layout.addWidget(self.process_log)

        layout.addWidget(process_card)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)

        self._sync_voice_mode_ui()
        self.set_project(None, None)

    def set_voice_assets(self, records, current_path: Path | None = None):
        selected_path = self.selected_voice_asset_path()
        current_resolved = None
        if current_path is not None:
            try:
                current_resolved = Path(current_path).resolve()
            except Exception:
                current_resolved = None

        self.voice_asset_table.setRowCount(0)
        selected_row = None
        current_row = None

        for record in records:
            row = self.voice_asset_table.rowCount()
            self.voice_asset_table.insertRow(row)
            audio_path = Path(record.path)
            try:
                is_current = current_resolved is not None and audio_path.resolve() == current_resolved
            except Exception:
                is_current = False

            name = record.display_name or audio_path.stem
            if is_current:
                name = f"● {name}"

            provider_engine = record.provider_id or "-"
            if record.model_id:
                provider_engine = f"{provider_engine} / {record.model_id}"
            duration = _format_duration(record.duration_seconds) if record.duration_seconds else "-"
            created = str(record.created_at or "-")
            if "T" in created:
                created = created.replace("T", " ")[:19]

            values = [
                name,
                {"generated": "TTS", "imported": "Nhập", "unindexed": "Chưa lập chỉ mục"}.get(record.kind, record.kind),
                provider_engine,
                record.voice_id or "-",
                duration,
                created,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, str(audio_path))
                item.setData(Qt.ItemDataRole.UserRole + 1, record.asset_id)
                self.voice_asset_table.setItem(row, column, item)

            if selected_path is not None:
                try:
                    if audio_path.resolve() == selected_path.resolve():
                        selected_row = row
                except Exception:
                    pass
            if is_current:
                current_row = row

        self.voice_asset_count.setText(f"{len(records)} tệp")
        row_to_select = selected_row if selected_row is not None else current_row
        if row_to_select is not None:
            self.voice_asset_table.selectRow(row_to_select)
        self._refresh_voice_asset_buttons()

    def selected_voice_asset_path(self) -> Path | None:
        row = self.voice_asset_table.currentRow()
        if row < 0:
            return None
        item = self.voice_asset_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(value)) if value else None

    def selected_voice_asset_id(self) -> str | None:
        row = self.voice_asset_table.currentRow()
        if row < 0:
            return None
        item = self.voice_asset_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole + 1)
        return str(value) if value else None

    def _refresh_voice_asset_buttons(self):
        has_project = self._manifest_path is not None
        has_selection = self.voice_asset_table.currentRow() >= 0 if hasattr(self, "voice_asset_table") else False
        if hasattr(self, "voice_asset_refresh_button"):
            self.voice_asset_refresh_button.setEnabled(has_project)
            self.voice_asset_preview_button.setEnabled(has_project and has_selection)
            self.voice_asset_use_button.setEnabled(has_project and has_selection)
            self.voice_asset_open_button.setEnabled(has_project)

    def _sync_voice_mode_ui(self):
        imported = self.imported_mode_radio.isChecked()
        self.imported_voice_panel.setVisible(imported)
        self.tts_panel.setVisible(not imported)
        if hasattr(self, "voice_clone_panel"):
            self.voice_clone_panel.setVisible((not imported) and bool(self._clone_available))
        self._refresh_action_states()

    def voice_mode(self) -> str:
        return "generated" if self.generated_mode_radio.isChecked() else "imported"

    def selected_tts_provider_id(self) -> str:
        return str(self.tts_provider_combo.currentData() or "")

    def selected_tts_engine_id(self) -> str:
        return str(self.tts_engine_combo.currentData() or "")

    def selected_tts_voice_id(self) -> str:
        return str(self.tts_voice_combo.currentData() or "")

    def selected_tts_speed(self) -> float:
        return float(self.tts_speed_spin.value())

    def set_tts_speed(self, value: float):
        self.tts_speed_spin.setValue(float(value))

    def set_tts_providers(self, providers):
        current = self.selected_tts_provider_id()
        self.tts_provider_combo.blockSignals(True)
        try:
            self.tts_provider_combo.clear()
            for provider in providers:
                self.tts_provider_combo.addItem(
                    str(getattr(provider, "display_name", getattr(provider, "provider_id", "TTS"))),
                    str(getattr(provider, "provider_id", "")),
                )
            index = self.tts_provider_combo.findData(current)
            if index < 0 and self.tts_provider_combo.count() > 0:
                index = 0
            if index >= 0:
                self.tts_provider_combo.setCurrentIndex(index)
        finally:
            self.tts_provider_combo.blockSignals(False)
        self._refresh_action_states()

    def set_tts_engines(self, engines, selected_engine_id: str | None = None):
        previous = selected_engine_id or self.selected_tts_engine_id()
        self.tts_engine_combo.blockSignals(True)
        try:
            self.tts_engine_combo.clear()
            for engine in engines:
                engine_id = str(getattr(engine, "engine_id", "") or "")
                name = str(getattr(engine, "display_name", engine_id or "Engine"))
                self.tts_engine_combo.addItem(name, engine_id)
            index = self.tts_engine_combo.findData(previous) if previous else -1
            if index < 0:
                # Prefer explicit OmniVoice over the generic active-engine alias.
                index = self.tts_engine_combo.findData("omnivoice")
            if index < 0 and self.tts_engine_combo.count() > 0:
                index = 0
            if index >= 0:
                self.tts_engine_combo.setCurrentIndex(index)
        finally:
            self.tts_engine_combo.blockSignals(False)
        visible = self.tts_engine_combo.count() > 0
        self.tts_engine_label.setVisible(visible)
        self.tts_engine_combo.setVisible(visible)
        self._refresh_action_states()

    def set_tts_engine_visible(self, visible: bool):
        self.tts_engine_label.setVisible(bool(visible))
        self.tts_engine_combo.setVisible(bool(visible))

    def set_tts_voices(self, voices, selected_voice_id: str | None = None):
        previous = selected_voice_id or self.selected_tts_voice_id()
        self.tts_voice_combo.clear()
        for voice in voices:
            details = []
            language = getattr(voice, "language", None)
            quality = getattr(voice, "quality", None)
            if language:
                details.append(str(language))
            if quality:
                details.append(str(quality))
            name = str(getattr(voice, "display_name", getattr(voice, "voice_id", "Voice")))
            if details:
                name += "  ·  " + " · ".join(details)
            self.tts_voice_combo.addItem(name, str(getattr(voice, "voice_id", "")))
            item_index = self.tts_voice_combo.count() - 1
            self.tts_voice_combo.setItemData(item_index, name, Qt.ItemDataRole.ToolTipRole)
        index = self.tts_voice_combo.findData(previous)
        if index < 0 and self.tts_voice_combo.count() > 0:
            index = 0
        if index >= 0:
            self.tts_voice_combo.setCurrentIndex(index)
        self._refresh_action_states()

    def set_tts_health(self, text: str, kind: str = "idle"):
        self.tts_health_label.setText(text)
        name = {"good": "statusGood", "warn": "statusWarn", "bad": "statusBad"}.get(kind, "muted")
        self.tts_health_label.setObjectName(name)
        self.tts_health_label.style().unpolish(self.tts_health_label)
        self.tts_health_label.style().polish(self.tts_health_label)

    def set_voice_clone_available(self, available: bool):
        self._clone_available = bool(available)
        self.voice_clone_panel.setVisible(self._clone_available and self.generated_mode_radio.isChecked())
        if not available:
            self._clone_reference_path = None
            self.clone_audio_value.setText("Chưa chọn audio mẫu")
            self.clone_permission_check.setChecked(False)
        self._refresh_action_states()

    def set_clone_reference_path(self, path: Path | None):
        self._clone_reference_path = Path(path) if path is not None else None
        if self._clone_reference_path is None:
            self.clone_audio_value.setText("Chưa chọn audio mẫu")
        else:
            self.clone_audio_value.setText(str(self._clone_reference_path))
        self._refresh_action_states()

    def clone_reference_path(self) -> Path | None:
        return self._clone_reference_path

    def clone_name(self) -> str:
        return self.clone_name_edit.text().strip()

    def clone_language(self) -> str:
        return str(self.clone_language_combo.currentData() or "Auto")

    def clone_transcript(self) -> str:
        return self.clone_transcript_edit.toPlainText().strip()

    def clone_permission_confirmed(self) -> bool:
        return bool(self.clone_permission_check.isChecked())

    def set_clone_status(self, text: str, kind: str = "idle"):
        self.clone_status_label.setText(text)
        name = {"good": "statusGood", "warn": "statusWarn", "bad": "statusBad"}.get(kind, "muted")
        self.clone_status_label.setObjectName(name)
        self.clone_status_label.style().unpolish(self.clone_status_label)
        self.clone_status_label.style().polish(self.clone_status_label)

    def set_clone_busy(self, busy: bool):
        self._clone_busy = bool(busy)
        self._refresh_action_states()

    def _on_script_changed(self):
        if not self._loading_project:
            self._script_dirty = True
        text = self.script_editor.toPlainText()
        words = len(text.split()) if text.strip() else 0
        self.script_stats.setText(f"Từ: {words:,}   ·   Ký tự: {len(text):,}")
        if self._script_dirty:
            self.script_status.setText("Có thay đổi chưa lưu.")
            self.script_status.setObjectName("statusWarn")
            self.script_status.style().unpolish(self.script_status)
            self.script_status.style().polish(self.script_status)
        self._refresh_action_states()

    def script_text(self) -> str:
        return self.script_editor.toPlainText()

    def is_script_dirty(self) -> bool:
        return bool(self._script_dirty)

    def selected_language(self) -> str:
        return str(self.language_combo.currentData() or "und")

    def set_script_text(self, text: str, language: str = "en", *, clean: bool = True):
        self._loading_project = True
        try:
            self.script_editor.setPlainText(text or "")
            index = self.language_combo.findData(language or "und")
            if index < 0:
                index = self.language_combo.findData("und")
            if index >= 0:
                self.language_combo.setCurrentIndex(index)
        finally:
            self._loading_project = False
        self._script_dirty = not clean
        self._on_script_changed()
        if clean:
            self._script_dirty = False
            if text.strip():
                self.script_status.setText("Kịch bản đã được lưu trong dự án.")
                self.script_status.setObjectName("statusGood")
            else:
                self.script_status.setText("Chưa có kịch bản.")
                self.script_status.setObjectName("muted")
            self.script_status.style().unpolish(self.script_status)
            self.script_status.style().polish(self.script_status)
        self._refresh_action_states()

    def append_log(self, text: str):
        if text:
            self.process_log.appendPlainText(text)

    def set_process_status(self, text: str, kind: str = "idle"):
        self.process_status.setText(text)
        object_name = {
            "good": "statusGood",
            "warn": "statusWarn",
            "bad": "statusBad",
        }.get(kind, "muted")
        self.process_status.setObjectName(object_name)
        self.process_status.style().unpolish(self.process_status)
        self.process_status.style().polish(self.process_status)

    def set_preview_playback_state(self, active: bool, paused: bool = False):
        self._preview_active = bool(active)
        self._preview_paused = bool(paused and active)
        self.tts_pause_preview_button.setText(
            "Tiếp tục" if self._preview_paused else "Tạm dừng"
        )
        self._refresh_action_states()

    def set_busy(self, busy: bool):
        self._pipeline_busy = bool(busy)
        self._refresh_action_states()

    def set_tts_busy(self, busy: bool):
        self._tts_busy = bool(busy)
        self._refresh_action_states()

    def _refresh_action_states(self):
        busy = self._pipeline_busy or self._tts_busy or self._clone_busy
        has_project = self._manifest_path is not None
        has_voice = self._voice_path is not None
        has_script = bool(self.script_editor.toPlainText().strip())
        generated_mode = self.generated_mode_radio.isChecked()
        has_provider = bool(self.selected_tts_provider_id())
        has_tts_voice = bool(self.selected_tts_voice_id())

        self.run_pipeline_button.setEnabled(not busy and has_voice)
        self.select_voice_button.setEnabled(not busy and has_project and not generated_mode)
        self.clear_voice_button.setEnabled(not busy and has_voice)
        self.import_script_button.setEnabled(not busy and has_project)
        self.save_script_button.setEnabled(not busy and has_project)
        self.clear_script_button.setEnabled(not busy and has_project)
        self.preview_voice_button.setEnabled(not busy and has_voice)
        self.tts_provider_combo.setEnabled(not busy and has_project and generated_mode)
        self.tts_engine_combo.setEnabled(not busy and has_project and generated_mode)
        self.tts_voice_combo.setEnabled(not busy and has_project and generated_mode)
        self.tts_refresh_button.setEnabled(not busy and has_project and generated_mode)
        self.tts_speed_spin.setEnabled(not busy and has_project and generated_mode)
        self.tts_speed_down_button.setEnabled(not busy and has_project and generated_mode)
        self.tts_speed_up_button.setEnabled(not busy and has_project and generated_mode)
        self.tts_preview_button.setEnabled(
            not busy and has_project and generated_mode and has_script and has_provider and has_tts_voice
        )
        self.tts_pause_preview_button.setEnabled(self._preview_active)
        self.tts_stop_preview_button.setEnabled(self._preview_active)
        self.tts_generate_button.setEnabled(
            not busy and has_project and generated_mode and has_script and has_provider and has_tts_voice
        )
        clone_available = generated_mode and bool(self._clone_available)
        clone_ready = (
            clone_available
            and self._clone_reference_path is not None
            and bool(self.clone_name_edit.text().strip())
            and self.clone_permission_check.isChecked()
        )
        self.clone_name_edit.setEnabled(not busy and has_project and clone_available)
        self.clone_language_combo.setEnabled(not busy and has_project and clone_available)
        self.clone_audio_button.setEnabled(not busy and has_project and clone_available)
        self.clone_transcript_edit.setEnabled(not busy and has_project and clone_available)
        self.clone_permission_check.setEnabled(not busy and has_project and clone_available)
        self.clone_create_button.setEnabled(not busy and has_project and clone_ready)
        self.imported_mode_radio.setEnabled(not busy and has_project)
        self.generated_mode_radio.setEnabled(not busy and has_project)
        self.saved_scripts_button.setEnabled(has_project)
        self.voice_workspace_open_button.setEnabled(has_project)
        self.voice_history_open_button.setEnabled(has_project)
        self._refresh_voice_asset_buttons()

    def set_project(self, manifest: ProjectManifest | None, manifest_path: Path | None):
        self._manifest_path = Path(manifest_path) if manifest_path is not None else None
        self._voice_path = None

        if manifest is None:
            self.project_notice.setText("Hãy tạo hoặc mở một dự án trước khi làm việc với giọng đọc và kịch bản.")
            self.project_notice.setObjectName("statusWarn")
            self.voice_name_value.setText("Chưa chọn tệp")
            self.voice_path_value.setText("-")
            self.voice_notice.setText("Chưa có giọng đọc trong dự án.")
            self.set_script_text("", "en", clean=True)
            self.process_log.clear()
            self.set_process_status("Chưa xử lý.", "idle")
            self.refresh_workspace_display()
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.project_notice.setText(f"Dự án hiện tại: {manifest.project_name}")
        self.project_notice.setObjectName("statusGood")
        self.project_notice.style().unpolish(self.project_notice)
        self.project_notice.style().polish(self.project_notice)

        for item in getattr(manifest, "inputs", []) or []:
            if getattr(item, "id", None) == VOICE_INPUT_ID or getattr(item, "kind", None) == InputKind.VOICE:
                reference = str(getattr(item, "reference", "") or "")
                if reference:
                    self._voice_path = Path(reference)
                    break

        voice_state = getattr(manifest, "voice", None)
        generated = getattr(voice_state, "kind", None) == VoiceKind.GENERATED
        self.generated_mode_radio.setChecked(generated)
        self.imported_mode_radio.setChecked(not generated)

        if generated:
            provider_id = str(getattr(voice_state, "provider", "") or "")
            voice_id = str(getattr(voice_state, "voice_id", "") or "")
            speed = float(getattr(voice_state, "speed", 1.0) or 1.0)
            p_index = self.tts_provider_combo.findData(provider_id)
            if p_index >= 0:
                self.tts_provider_combo.setCurrentIndex(p_index)
            v_index = self.tts_voice_combo.findData(voice_id)
            if v_index >= 0:
                self.tts_voice_combo.setCurrentIndex(v_index)
            if 0.50 <= speed <= 2.00:
                self.tts_speed_spin.setValue(speed)

        if self._voice_path is not None:
            self.voice_name_value.setText(self._voice_path.name)
            self.voice_path_value.setText(str(self._voice_path))
            if self._voice_path.is_file():
                if generated:
                    provider = str(getattr(voice_state, "provider", "") or "TTS")
                    voice_id = str(getattr(voice_state, "voice_id", "") or "-")
                    self.voice_notice.setText(f"Giọng đọc do {provider} tạo · voice: {voice_id}")
                else:
                    self.voice_notice.setText("Giọng đọc đã được gắn với dự án.")
                self.voice_notice.setObjectName("statusGood")
            else:
                self.voice_notice.setText("Tệp giọng đọc đã lưu trong dự án nhưng hiện không tìm thấy trên ổ đĩa.")
                self.voice_notice.setObjectName("statusWarn")
        else:
            self.voice_name_value.setText("Chưa chọn tệp")
            self.voice_path_value.setText("-")
            self.voice_notice.setText("Chưa có giọng đọc trong dự án.")
            self.voice_notice.setObjectName("muted")

        self.voice_notice.style().unpolish(self.voice_notice)
        self.voice_notice.style().polish(self.voice_notice)

        content = getattr(manifest, "content", None)
        script = str(getattr(content, "script", "") or "")
        language = str(getattr(content, "source_language", "en") or "en")
        self.set_script_text(script, language, clean=True)

        self._refresh_derived_status()
        self._pipeline_busy = False
        self._tts_busy = False
        self._sync_voice_mode_ui()

    def refresh_workspace_display(self):
        if self._manifest_path is None:
            self.voice_workspace_path_value.setText("-")
            self.workspace_voice_value.setText("Chưa có")
            self.workspace_assets_value.setText("Chưa có")
            self.workspace_history_value.setText("Chưa có bản lưu lịch sử.")
            self.voice_workspace_open_button.setEnabled(False)
            self.voice_history_open_button.setEnabled(False)
            return

        output_dir = self._manifest_path.parent / VOICE_WORKSPACE_DIRNAME
        self.voice_workspace_path_value.setText(str(output_dir))
        self.voice_workspace_open_button.setEnabled(True)
        self.voice_history_open_button.setEnabled(True)

        voice_path = self._voice_path
        if voice_path is not None:
            voice_path = Path(voice_path)
            if voice_path.is_file():
                try:
                    size_bytes = voice_path.stat().st_size
                    size_mb = size_bytes / (1024.0 * 1024.0)
                    self.workspace_voice_value.setText(
                        f"{voice_path}  ·  {size_mb:.2f} MB"
                    )
                except Exception:
                    self.workspace_voice_value.setText(str(voice_path))
            else:
                self.workspace_voice_value.setText(
                    f"{voice_path}  ·  KHÔNG TÌM THẤY"
                )
        else:
            generated_candidate = output_dir / GENERATED_VOICE_FILENAME
            if generated_candidate.is_file():
                try:
                    size_mb = generated_candidate.stat().st_size / (1024.0 * 1024.0)
                    self.workspace_voice_value.setText(
                        f"{generated_candidate}  ·  {size_mb:.2f} MB"
                    )
                except Exception:
                    self.workspace_voice_value.setText(str(generated_candidate))
            else:
                self.workspace_voice_value.setText("Chưa có tệp giọng chính thức.")

        artifacts = []
        artifact_specs = (
            (GENERATED_VOICE_FILENAME, "giọng"),
            ("clean_transcript.srt", "SRT"),
            (VOICE_PIPELINE_RESULT_FILENAME, "kết quả"),
            ("voice_scenes.json", "cảnh"),
        )
        for filename, label in artifact_specs:
            path = output_dir / filename
            if path.is_file():
                artifacts.append(f"✓ {label}: {filename}")
            else:
                artifacts.append(f"— {label}: {filename}")
        self.workspace_assets_value.setText("   |   ".join(artifacts))

        history_root = output_dir / VOICE_HISTORY_DIRNAME
        try:
            history_runs = sorted(
                [item for item in history_root.iterdir() if item.is_dir()],
                key=lambda item: item.name,
                reverse=True,
            ) if history_root.is_dir() else []
        except Exception:
            history_runs = []

        if history_runs:
            self.workspace_history_value.setText(
                f"{len(history_runs)} bản lưu · mới nhất: {history_runs[0].name}"
            )
        else:
            self.workspace_history_value.setText(
                "Chưa có bản lưu lịch sử. Từ M104.5, mỗi lần tạo giọng sẽ được giữ lại."
            )

    def _refresh_derived_status(self):
        self.refresh_workspace_display()
        if self._manifest_path is None:
            self.set_process_status("Chưa xử lý.", "idle")
            self.open_output_button.setEnabled(False)
            return

        output_dir = self._manifest_path.parent / VOICE_WORKSPACE_DIRNAME
        result_path = output_dir / VOICE_PIPELINE_RESULT_FILENAME
        self.open_output_button.setEnabled(True)

        if not result_path.is_file():
            self.set_process_status("Chưa xử lý giọng đọc cho dự án này.", "idle")
            return

        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            stored_voice = str(data.get("source_voice", ""))
            current_voice = str(self._voice_path) if self._voice_path is not None else ""
            if not current_voice or stored_voice != current_voice:
                self.set_process_status("Kết quả cũ không còn khớp với tệp giọng đọc hiện tại.", "warn")
                return
            summary = data.get("summary", {}) if isinstance(data, dict) else {}
            duration = _format_duration(summary.get("duration"))
            scenes = summary.get("scenes", 0)
            self.set_process_status(
                f"Đã xử lý giọng đọc · Thời lượng {duration} · {scenes} cảnh dẫn xuất.",
                "good",
            )
        except Exception:
            self.set_process_status("Có dữ liệu xử lý cũ nhưng không thể đọc trạng thái.", "warn")


class DiagnosticsPage(QWidget):
    def __init__(
        self,
        provider_view: ProviderDiagnosticsQtView,
        open_api_settings_callback,
    ):
        super().__init__()

        self.provider_view = provider_view
        self.provider_view.setStyleSheet(DIAGNOSTICS_VIEW_STYLE)
        QTimer.singleShot(0, lambda: _translate_known_ui_texts(self.provider_view))

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
            "Trang này sử dụng lại hệ thống chẩn đoán hiện có gồm request builder, host, "
            "giao diện Qt, binder và worker. API Key vẫn được quản lý bởi trình quản lý API hiện tại."
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


class MediaAssetLibraryPage(QWidget):
    def __init__(
        self,
        import_image_callback,
        import_video_callback,
        refresh_callback,
        open_file_callback,
        open_folder_callback,
    ):
        super().__init__()
        self._records: list[MediaAssetRecord] = []
        self._project_loaded = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Tìm tư liệu")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "M106 quản lý ảnh và video theo Asset Library của từng dự án. "
            "Tệp nhập vào được copy vào project và không ghi đè asset cũ."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        action_card = Card()
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(20, 18, 20, 20)
        action_layout.setSpacing(12)

        action_title = QLabel("Thêm tư liệu vào dự án")
        action_title.setObjectName("sectionTitle")
        action_help = QLabel(
            "Ảnh/video được nhập sẽ nằm trong assets/images hoặc assets/videos. "
            "Bản gốc bên ngoài project không được dùng làm đường dẫn làm việc lâu dài."
        )
        action_help.setObjectName("muted")
        action_help.setWordWrap(True)
        action_layout.addWidget(action_title)
        action_layout.addWidget(action_help)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.import_image_button = QPushButton("Nhập ảnh")
        self.import_video_button = QPushButton("Nhập video")
        self.import_image_button.setProperty("class", "primaryButton")
        self.import_video_button.setProperty("class", "primaryButton")
        for button in (self.import_image_button, self.import_video_button):
            button.setMinimumHeight(38)
            action_row.addWidget(button)
        action_row.addStretch(1)
        action_layout.addLayout(action_row)

        self.import_image_button.clicked.connect(import_image_callback)
        self.import_video_button.clicked.connect(import_video_callback)
        layout.addWidget(action_card)

        library_card = Card()
        library_layout = QVBoxLayout(library_card)
        library_layout.setContentsMargins(20, 18, 20, 20)
        library_layout.setSpacing(10)

        header = QHBoxLayout()
        header_title = QLabel("Media Asset Library")
        header_title.setObjectName("sectionTitle")
        header.addWidget(header_title)
        header.addStretch(1)
        filter_label = QLabel("Hiển thị")
        filter_label.setObjectName("muted")
        header.addWidget(filter_label)
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Tất cả", "all")
        self.filter_combo.addItem("Ảnh", "image")
        self.filter_combo.addItem("Video", "video")
        self.filter_combo.setMinimumWidth(120)
        header.addWidget(self.filter_combo)
        self.asset_count = QLabel("0 tệp")
        self.asset_count.setObjectName("muted")
        header.addWidget(self.asset_count)
        library_layout.addLayout(header)

        library_help = QLabel(
            "M107.1 vẫn không tự động đưa các tệp này vào ProjectManifest.media. "
            "Bạn có thể gán asset thủ công cho cảnh tại trang Cảnh; Timeline/Render vẫn chưa được tạo."
        )
        library_help.setObjectName("muted")
        library_help.setWordWrap(True)
        library_layout.addWidget(library_help)

        self.asset_table = QTableWidget(0, 6)
        self.asset_table.setHorizontalHeaderLabels(
            ["Tên", "Loại", "Nguồn", "Định dạng", "Kích thước", "Ngày tạo"]
        )
        self.asset_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.asset_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.asset_table.setAlternatingRowColors(False)
        self.asset_table.verticalHeader().setVisible(False)
        self.asset_table.setMinimumHeight(270)
        table_header = self.asset_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            table_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.asset_table.itemSelectionChanged.connect(self._refresh_action_states)
        library_layout.addWidget(self.asset_table)

        library_actions = QHBoxLayout()
        library_actions.setSpacing(10)
        self.refresh_button = QPushButton("Làm mới thư viện")
        self.open_file_button = QPushButton("Mở tệp")
        self.open_folder_button = QPushButton("Mở thư mục asset")
        for button in (self.refresh_button, self.open_file_button, self.open_folder_button):
            button.setProperty("class", "secondaryButton")
            button.setMinimumHeight(36)
            library_actions.addWidget(button)
        library_actions.addStretch(1)
        library_layout.addLayout(library_actions)

        self.refresh_button.clicked.connect(refresh_callback)
        self.open_file_button.clicked.connect(open_file_callback)
        self.open_folder_button.clicked.connect(open_folder_callback)
        self.filter_combo.currentIndexChanged.connect(self._rebuild_table)
        layout.addWidget(library_card)

        self.notice = QLabel("Hãy tạo hoặc mở dự án để quản lý tư liệu.")
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)
        self.set_project(None, None)

    def set_project(self, manifest: ProjectManifest | None, manifest_path: Path | None):
        self._project_loaded = manifest is not None and manifest_path is not None
        for button in (
            self.import_image_button,
            self.import_video_button,
            self.refresh_button,
            self.open_folder_button,
        ):
            button.setEnabled(self._project_loaded)
        if not self._project_loaded:
            self._records = []
            self._rebuild_table()
            self.notice.setText("Hãy tạo hoặc mở dự án để quản lý tư liệu.")
        else:
            self.notice.setText(
                "Asset Library sẵn sàng. Ảnh/video mới sẽ được copy vào thư mục của dự án."
            )
        self._refresh_action_states()

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

    def set_assets(self, records):
        selected = self.selected_media_asset_path()
        self._records = list(records or ())
        self._rebuild_table(selected)

    def _filtered_records(self):
        selected_filter = self.filter_combo.currentData() or "all"
        if selected_filter == "all":
            return list(self._records)
        return [r for r in self._records if r.media_type == selected_filter]

    def _rebuild_table(self, selected_path: Path | None = None):
        if isinstance(selected_path, int):
            selected_path = self.selected_media_asset_path()
        records = self._filtered_records()
        self.asset_table.setRowCount(0)
        selected_row = None
        for record in records:
            row = self.asset_table.rowCount()
            self.asset_table.insertRow(row)
            path = record.media_path
            type_text = "Ảnh" if record.media_type == "image" else "Video"
            origin_text = {
                "imported": "Nhập",
                "downloaded": "Tải xuống",
                "generated": "AI tạo",
            }.get(record.origin, record.origin)
            if record.provider_id:
                origin_text += f" · {record.provider_id}"
            suffix = path.suffix.lower().lstrip(".").upper() or "-"
            if record.size_bytes is None:
                size_text = "-"
            elif record.size_bytes >= 1024 * 1024:
                size_text = f"{record.size_bytes / (1024 * 1024):.2f} MB"
            else:
                size_text = f"{record.size_bytes / 1024:.1f} KB"
            try:
                date_text = datetime.fromisoformat(record.created_at).strftime("%d/%m/%Y %H:%M")
            except Exception:
                date_text = record.created_at
            values = [record.display_name, type_text, origin_text, suffix, size_text, date_text]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setData(Qt.ItemDataRole.UserRole + 1, record.asset_id)
                self.asset_table.setItem(row, column, item)
            if selected_path is not None:
                try:
                    if path.resolve() == Path(selected_path).resolve():
                        selected_row = row
                except Exception:
                    pass
        self.asset_count.setText(f"{len(records)} tệp")
        if selected_row is not None:
            self.asset_table.selectRow(selected_row)
        self._refresh_action_states()

    def selected_media_asset_path(self) -> Path | None:
        row = self.asset_table.currentRow()
        if row < 0:
            return None
        item = self.asset_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(value)) if value else None

    def _refresh_action_states(self):
        selected = self.selected_media_asset_path()
        has_selected = selected is not None and selected.is_file()
        self.open_file_button.setEnabled(self._project_loaded and has_selected)
        self.open_folder_button.setEnabled(self._project_loaded)


class SceneAssetAssignmentPage(QWidget):
    PREVIEW_WIDTH = 560
    PREVIEW_HEIGHT = 315

    def __init__(
        self,
        refresh_callback,
        assign_callback,
        remove_callback,
        open_asset_callback,
    ):
        super().__init__()
        self._project_loaded = False
        self._scenes: list[dict] = []
        self._assets: list[MediaAssetRecord] = []
        self._assignment_state: SceneAssetAssignmentState | None = None
        self._asset_by_id: dict[str, MediaAssetRecord] = {}
        self._video_player = None
        self._video_audio_output = None
        self._video_widget = None
        self._video_preview_path: Path | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Cảnh")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "M108 hiển thị workspace cảnh trực quan hơn: xem trước ảnh/video, kiểm tra "
            "tư liệu đang gán và đổi asset nhanh. Assignment M107 vẫn là nguồn mapping; "
            "bước này chưa tạo timeline, chưa cắt video và chưa render."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        source_card = Card()
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(20, 18, 20, 18)
        source_layout.setSpacing(8)
        source_title = QLabel("Nguồn cảnh")
        source_title.setObjectName("sectionTitle")
        self.source_value = QLabel("Chưa có VoicePipeline run.")
        self.source_value.setObjectName("muted")
        self.source_value.setWordWrap(True)
        source_row = QHBoxLayout()
        source_row.addWidget(source_title)
        source_row.addStretch(1)
        self.refresh_button = QPushButton("Làm mới cảnh")
        self.refresh_button.setProperty("class", "secondaryButton")
        self.refresh_button.setMinimumHeight(36)
        self.refresh_button.clicked.connect(refresh_callback)
        source_row.addWidget(self.refresh_button)
        source_layout.addLayout(source_row)
        source_layout.addWidget(self.source_value)
        layout.addWidget(source_card)

        main_row = QHBoxLayout()
        main_row.setSpacing(14)

        scenes_card = Card()
        scenes_layout = QVBoxLayout(scenes_card)
        scenes_layout.setContentsMargins(18, 16, 18, 18)
        scenes_layout.setSpacing(10)
        scenes_title = QLabel("Danh sách cảnh")
        scenes_title.setObjectName("sectionTitle")
        scenes_layout.addWidget(scenes_title)
        self.scene_table = QTableWidget(0, 4)
        self.scene_table.setHorizontalHeaderLabels(["Cảnh", "Thời gian", "Nội dung", "Tư liệu đã gán"])
        self.scene_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.scene_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.scene_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scene_table.verticalHeader().setVisible(False)
        self.scene_table.setMinimumHeight(330)
        sh = self.scene_table.horizontalHeader()
        sh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        sh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        sh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        sh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.scene_table.itemSelectionChanged.connect(self._on_selection_changed)
        scenes_layout.addWidget(self.scene_table)
        main_row.addWidget(scenes_card, 3)

        assets_card = Card()
        assets_layout = QVBoxLayout(assets_card)
        assets_layout.setContentsMargins(18, 16, 18, 18)
        assets_layout.setSpacing(10)
        assets_header = QHBoxLayout()
        assets_title = QLabel("Media Asset Library")
        assets_title.setObjectName("sectionTitle")
        assets_header.addWidget(assets_title)
        assets_header.addStretch(1)
        self.asset_filter = QComboBox()
        self.asset_filter.addItem("Tất cả", "all")
        self.asset_filter.addItem("Ảnh", "image")
        self.asset_filter.addItem("Video", "video")
        self.asset_filter.currentIndexChanged.connect(self._rebuild_asset_table)
        assets_header.addWidget(self.asset_filter)
        assets_layout.addLayout(assets_header)

        self.asset_table = QTableWidget(0, 3)
        self.asset_table.setHorizontalHeaderLabels(["Tên", "Loại", "Nguồn"])
        self.asset_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.asset_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.asset_table.verticalHeader().setVisible(False)
        self.asset_table.setMinimumHeight(330)
        ah = self.asset_table.horizontalHeader()
        ah.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ah.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        ah.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.asset_table.itemSelectionChanged.connect(self._on_selection_changed)
        assets_layout.addWidget(self.asset_table)
        main_row.addWidget(assets_card, 2)
        layout.addLayout(main_row)

        preview_card = Card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 16, 18, 18)
        preview_layout.setSpacing(10)

        preview_header = QHBoxLayout()
        preview_title = QLabel("Xem trước tư liệu")
        preview_title.setObjectName("sectionTitle")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        self.preview_source_badge = QLabel("Chưa chọn")
        self.preview_source_badge.setObjectName("muted")
        preview_header.addWidget(self.preview_source_badge)
        preview_layout.addLayout(preview_header)

        preview_body = QHBoxLayout()
        preview_body.setSpacing(16)

        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumSize(self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT)
        self.preview_stack.setMaximumHeight(390)

        self.preview_placeholder = QLabel(
            "Chọn một Media Asset ở bên phải hoặc chọn một cảnh đã được gán tư liệu."
        )
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setWordWrap(True)
        self.preview_placeholder.setStyleSheet(
            "QLabel { background: #0b1118; border: 1px solid #263241; "
            "border-radius: 10px; color: #7e8da3; padding: 22px; }"
        )
        self.preview_stack.addWidget(self.preview_placeholder)

        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumSize(self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT)
        self.image_preview.setStyleSheet(
            "QLabel { background: #080d13; border: 1px solid #263241; "
            "border-radius: 10px; }"
        )
        self.preview_stack.addWidget(self.image_preview)

        if QT_VIDEO_PREVIEW_AVAILABLE:
            try:
                self._video_widget = QVideoWidget()
                self._video_widget.setMinimumSize(self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT)
                self._video_player = QMediaPlayer(self)
                self._video_audio_output = QAudioOutput(self)
                self._video_player.setAudioOutput(self._video_audio_output)
                self._video_player.setVideoOutput(self._video_widget)
                self._video_player.playbackStateChanged.connect(
                    self._on_video_playback_state_changed
                )
                self._video_player.errorOccurred.connect(self._on_video_preview_error)
                self.preview_stack.addWidget(self._video_widget)
            except Exception:
                self._video_widget = None
                self._video_player = None
                self._video_audio_output = None

        preview_body.addWidget(self.preview_stack, 3)

        info_panel = QFrame()
        info_panel.setStyleSheet(
            "QFrame { background: #0f151d; border: 1px solid #202a36; "
            "border-radius: 8px; }"
        )
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(7)

        self.preview_name = QLabel("Chưa chọn tư liệu")
        self.preview_name.setStyleSheet("font-weight: 600; color: #e7eef7; border: none;")
        self.preview_name.setWordWrap(True)
        self.preview_meta = QLabel("—")
        self.preview_meta.setObjectName("muted")
        self.preview_meta.setWordWrap(True)
        self.preview_path = QLabel("")
        self.preview_path.setObjectName("muted")
        self.preview_path.setWordWrap(True)

        info_layout.addWidget(self.preview_name)
        info_layout.addWidget(self.preview_meta)
        info_layout.addWidget(self.preview_path)
        info_layout.addStretch(1)
        preview_body.addWidget(info_panel, 2)
        preview_layout.addLayout(preview_body)

        preview_actions = QHBoxLayout()
        preview_actions.setSpacing(10)
        self.preview_button = QPushButton("Xem trước")
        self.preview_button.setProperty("class", "secondaryButton")
        self.video_pause_button = QPushButton("Tạm dừng")
        self.video_pause_button.setProperty("class", "secondaryButton")
        self.video_stop_button = QPushButton("Dừng")
        self.video_stop_button.setProperty("class", "secondaryButton")
        self.open_button = QPushButton("Mở tư liệu")
        self.open_button.setProperty("class", "secondaryButton")

        for button in (
            self.preview_button,
            self.video_pause_button,
            self.video_stop_button,
            self.open_button,
        ):
            button.setMinimumHeight(38)
            preview_actions.addWidget(button)
        preview_actions.addStretch(1)

        self.preview_button.clicked.connect(self.preview_selected_media)
        self.video_pause_button.clicked.connect(self.toggle_video_preview_pause)
        self.video_stop_button.clicked.connect(self.stop_video_preview)
        self.open_button.clicked.connect(open_asset_callback)
        preview_layout.addLayout(preview_actions)
        layout.addWidget(preview_card)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.assign_button = QPushButton("Gán tư liệu cho cảnh")
        self.assign_button.setProperty("class", "primaryButton")
        self.remove_button = QPushButton("Bỏ gán")
        self.remove_button.setProperty("class", "secondaryButton")
        for button in (self.assign_button, self.remove_button):
            button.setMinimumHeight(38)
            actions.addWidget(button)
        actions.addStretch(1)
        self.assign_button.clicked.connect(assign_callback)
        self.remove_button.clicked.connect(remove_callback)
        layout.addLayout(actions)

        self.notice = QLabel("Hãy tạo hoặc mở dự án để xem cảnh.")
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)
        self.set_project(None, None)

    def set_project(self, manifest: ProjectManifest | None, manifest_path: Path | None):
        self._project_loaded = manifest is not None and manifest_path is not None
        self.refresh_button.setEnabled(self._project_loaded)
        if not self._project_loaded:
            self.stop_video_preview()
            self.set_data([], [], None, None)
            self.set_notice("Hãy tạo hoặc mở dự án để xem cảnh.")
        self._refresh_action_states()

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

    def set_data(self, scenes, assets, assignment_state, source_path: Path | None):
        selected_scene = self.selected_scene_id()
        selected_asset = self.selected_asset_id()
        self._scenes = list(scenes or ())
        self._assets = list(assets or ())
        self._asset_by_id = {item.asset_id: item for item in self._assets}
        self._assignment_state = assignment_state
        self.source_value.setText(str(source_path) if source_path is not None else "Chưa có VoicePipeline run.")
        self._rebuild_scene_table(selected_scene)
        self._rebuild_asset_table(selected_asset)
        self._refresh_preview_candidate()
        self._refresh_action_states()

    def _assignment_map(self):
        if self._assignment_state is None:
            return {}
        return self._assignment_state.assignment_map()

    @staticmethod
    def _time_text(value):
        try:
            total = float(value)
        except Exception:
            return "-"
        minutes = int(total // 60)
        seconds = total - minutes * 60
        return f"{minutes:02d}:{seconds:05.2f}"

    @staticmethod
    def _duration_text(value) -> str:
        try:
            total = float(value)
        except Exception:
            return "—"
        if total <= 0:
            return "—"
        minutes = int(total // 60)
        seconds = total - minutes * 60
        return f"{minutes:02d}:{seconds:05.2f}"

    def _rebuild_scene_table(self, selected_scene_id=None):
        if isinstance(selected_scene_id, int):
            selected_scene_id = self.selected_scene_id()
        mapping = self._assignment_map()
        self.scene_table.setRowCount(0)
        selected_row = None
        for scene in self._scenes:
            scene_id = str(scene.get("id", ""))
            assignment = mapping.get(scene_id)
            asset = self._asset_by_id.get(assignment.asset_id) if assignment else None
            assigned_text = "—"
            if assignment is not None:
                assigned_text = asset.display_name if asset is not None else f"{assignment.asset_id} (thiếu asset)"
            row = self.scene_table.rowCount()
            self.scene_table.insertRow(row)
            values = [
                scene_id,
                f"{self._time_text(scene.get('start'))} → {self._time_text(scene.get('end'))}",
                str(scene.get("text", "") or ""),
                assigned_text,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, scene_id)
                if assignment is not None:
                    item.setData(Qt.ItemDataRole.UserRole + 1, assignment.asset_id)
                self.scene_table.setItem(row, col, item)
            if scene_id == selected_scene_id:
                selected_row = row
        if selected_row is not None:
            self.scene_table.selectRow(selected_row)

    def _filtered_assets(self):
        wanted = self.asset_filter.currentData() or "all"
        if wanted == "all":
            return list(self._assets)
        return [item for item in self._assets if item.media_type == wanted]

    def _rebuild_asset_table(self, selected_asset_id=None):
        if isinstance(selected_asset_id, int):
            selected_asset_id = self.selected_asset_id()
        self.asset_table.setRowCount(0)
        selected_row = None
        for record in self._filtered_assets():
            row = self.asset_table.rowCount()
            self.asset_table.insertRow(row)
            type_text = "Ảnh" if record.media_type == "image" else "Video"
            origin_text = {
                "imported": "Nhập",
                "downloaded": "Tải xuống",
                "generated": "AI tạo",
            }.get(record.origin, record.origin)
            values = [record.display_name, type_text, origin_text]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, record.asset_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, str(record.media_path))
                self.asset_table.setItem(row, col, item)
            if record.asset_id == selected_asset_id:
                selected_row = row
        if selected_row is not None:
            self.asset_table.selectRow(selected_row)
        self._refresh_action_states()

    def selected_scene_id(self) -> str | None:
        row = self.scene_table.currentRow()
        if row < 0:
            return None
        item = self.scene_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def selected_scene_assignment_asset_id(self) -> str | None:
        row = self.scene_table.currentRow()
        if row < 0:
            return None
        item = self.scene_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole + 1)
        return str(value) if value else None

    def selected_asset_id(self) -> str | None:
        row = self.asset_table.currentRow()
        if row < 0:
            return None
        item = self.asset_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def selected_asset_path(self) -> Path | None:
        row = self.asset_table.currentRow()
        if row < 0:
            return None
        item = self.asset_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole + 1)
        return Path(str(value)) if value else None

    def asset_path_by_id(self, asset_id: str | None) -> Path | None:
        if not asset_id:
            return None
        record = self._asset_by_id.get(asset_id)
        return record.media_path if record is not None else None

    def selected_preview_record(self) -> tuple[MediaAssetRecord | None, str]:
        selected_asset_id = self.selected_asset_id()
        if selected_asset_id:
            return self._asset_by_id.get(selected_asset_id), "Media Asset đang chọn"
        assigned_asset_id = self.selected_scene_assignment_asset_id()
        if assigned_asset_id:
            return self._asset_by_id.get(assigned_asset_id), "Tư liệu đang gán cho cảnh"
        return None, "Chưa chọn"

    def _on_selection_changed(self):
        self.stop_video_preview()
        self._refresh_preview_candidate()
        self._refresh_action_states()

    def _refresh_preview_candidate(self):
        record, source = self.selected_preview_record()
        self.preview_source_badge.setText(source)

        if record is None:
            self.preview_name.setText("Chưa chọn tư liệu")
            self.preview_meta.setText("—")
            self.preview_path.setText("")
            self.image_preview.clear()
            self.preview_placeholder.setText(
                "Chọn một Media Asset ở bên phải hoặc chọn một cảnh đã được gán tư liệu."
            )
            self.preview_stack.setCurrentWidget(self.preview_placeholder)
            return

        type_text = "Ảnh" if record.media_type == "image" else "Video"
        origin_text = {
            "imported": "Nhập",
            "downloaded": "Tải xuống",
            "generated": "AI tạo",
        }.get(record.origin, record.origin)
        dimension = "—"
        if record.width and record.height:
            dimension = f"{record.width}×{record.height}"
        duration = self._duration_text(record.duration_seconds)
        size_mb = max(0, int(record.size_bytes or 0)) / (1024 * 1024)

        self.preview_name.setText(record.display_name)
        self.preview_meta.setText(
            f"{type_text} · {origin_text} · {dimension} · "
            f"{duration if record.media_type == 'video' else f'{size_mb:.2f} MB'}"
        )
        self.preview_path.setText(str(record.media_path))

        if not record.media_path.is_file():
            self.image_preview.clear()
            self.preview_placeholder.setText(
                "Tệp Media Asset không còn tồn tại trên ổ đĩa."
            )
            self.preview_stack.setCurrentWidget(self.preview_placeholder)
            return

        if record.media_type == "image":
            self._show_image_preview(record.media_path)
        else:
            self.image_preview.clear()
            if self._video_player is None or self._video_widget is None:
                self.preview_placeholder.setText(
                    "Video đã sẵn sàng. Qt Multimedia preview không khả dụng trên máy này.\n"
                    "Bạn vẫn có thể dùng nút Mở tư liệu."
                )
            else:
                self.preview_placeholder.setText(
                    "Video đã sẵn sàng.\nBấm “Xem trước” để phát video trong Creator Studio."
                )
            self.preview_stack.setCurrentWidget(self.preview_placeholder)

    def _show_image_preview(self, path: Path):
        self.stop_video_preview()
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_preview.clear()
            self.preview_placeholder.setText(
                f"Không thể đọc preview ảnh:\n{path.name}"
            )
            self.preview_stack.setCurrentWidget(self.preview_placeholder)
            return
        scaled = pixmap.scaled(
            self.PREVIEW_WIDTH,
            self.PREVIEW_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_preview.setPixmap(scaled)
        self.preview_stack.setCurrentWidget(self.image_preview)

    def preview_selected_media(self):
        record, _ = self.selected_preview_record()
        if record is None or not record.media_path.is_file():
            return
        if record.media_type == "image":
            self._show_image_preview(record.media_path)
            return
        self._play_video_preview(record.media_path)

    def _play_video_preview(self, path: Path):
        if self._video_player is None or self._video_widget is None:
            self.preview_placeholder.setText(
                "Không thể phát video trong ứng dụng vì Qt Multimedia không khả dụng.\n"
                "Dùng “Mở tư liệu” để mở video bằng trình phát mặc định."
            )
            self.preview_stack.setCurrentWidget(self.preview_placeholder)
            return
        try:
            self.stop_video_preview()
            self._video_preview_path = Path(path)
            self._video_player.setSource(QUrl.fromLocalFile(str(path)))
            self.preview_stack.setCurrentWidget(self._video_widget)
            self._video_player.play()
            self.video_pause_button.setText("Tạm dừng")
        except Exception as exc:
            self.preview_placeholder.setText(
                f"Không thể bắt đầu preview video.\n{type(exc).__name__}: {exc}"
            )
            self.preview_stack.setCurrentWidget(self.preview_placeholder)
            self._video_preview_path = None
        self._refresh_action_states()

    def toggle_video_preview_pause(self):
        if self._video_player is None or self._video_preview_path is None:
            return
        try:
            if self._video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._video_player.pause()
                self.video_pause_button.setText("Tiếp tục")
            else:
                self.preview_stack.setCurrentWidget(self._video_widget)
                self._video_player.play()
                self.video_pause_button.setText("Tạm dừng")
        except Exception:
            pass
        self._refresh_action_states()

    def stop_video_preview(self):
        if self._video_player is not None:
            try:
                self._video_player.stop()
                self._video_player.setSource(QUrl())
            except Exception:
                pass
        self._video_preview_path = None
        self.video_pause_button.setText("Tạm dừng")
        self._refresh_action_states()

    def _on_video_playback_state_changed(self, state):
        if self._video_player is None:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.video_pause_button.setText("Tạm dừng")
        elif self._video_preview_path is not None:
            self.video_pause_button.setText("Tiếp tục")
        self._refresh_action_states()

    def _on_video_preview_error(self, *args):
        message = "Không thể phát video preview."
        if self._video_player is not None:
            try:
                detail = self._video_player.errorString()
                if detail:
                    message = f"{message}\n{detail}"
            except Exception:
                pass
        self._video_preview_path = None
        self.preview_placeholder.setText(message)
        self.preview_stack.setCurrentWidget(self.preview_placeholder)
        self._refresh_action_states()

    def _refresh_action_states(self):
        scene_id = self.selected_scene_id()
        asset_id = self.selected_asset_id()
        assigned_asset_id = self.selected_scene_assignment_asset_id()
        self.assign_button.setEnabled(self._project_loaded and bool(scene_id) and bool(asset_id))
        self.remove_button.setEnabled(self._project_loaded and bool(scene_id) and bool(assigned_asset_id))

        record, _ = self.selected_preview_record()
        has_preview = (
            self._project_loaded
            and record is not None
            and record.media_path.is_file()
        )
        self.preview_button.setEnabled(has_preview)
        self.open_button.setEnabled(has_preview)

        video_active = (
            self._video_player is not None
            and self._video_preview_path is not None
        )
        self.video_pause_button.setEnabled(video_active)
        self.video_stop_button.setEnabled(video_active)


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
        self.voice_pipeline_worker: VoicePipelineWorker | None = None
        self.media_query_worker: SceneQueryPlanningWorker | None = None
        self.stock_acquisition_worker: StockAcquisitionWorker | None = None
        self.youtube_reference_worker: YouTubeReferenceWorker | None = None
        self.tts_worker: TTSSynthesisWorker | None = None
        self._tts_worker_action: str | None = None
        self._pending_tts_asset_target: VoiceAssetRecord | None = None
        self.automation_coordinator: AutomationPipelineCoordinator | None = None
        self._automation_cancel_requested = False
        self._automation_waiting_for_voice_pipeline = False
        self.clone_worker: VoiceCloneWorker | None = None
        self.audio_preview_controller = AudioPreviewController(self)
        self._voicestudio_autostart_active = False
        self._voicestudio_autostart_attempts = 0
        # VoiceStudio Electron itself allows a multi-minute startup budget.
        # Keep the GUI responsive while waiting up to ~10 minutes for first-run
        # setup/model/runtime initialization.
        self._voicestudio_autostart_max_attempts = 400
        self.voicestudio_runtime = VoiceStudioLocalRuntimeManager()
        self.tts_service = self._build_tts_service()
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
        _translate_known_ui_texts(self)
        self._connect_provider_diagnostics()

        self.provider_diagnostics_view.setEnabled(True)
        self._sync_provider_diagnostics_status(self.provider_diagnostics_bridge.state)

        self._restore_recent_project()
        self.navigate_to("automation")

    def _build_tts_service(self) -> TTSService:
        registry = TTSProviderRegistry()
        registry.register(
            PiperProcessProvider(
                python_executable=PIPER_PYTHON,
                voices_root=PIPER_VOICES_ROOT,
                project_root=ROOT,
            )
        )
        self.voicestudio_provider = VoiceStudioLocalProvider(
            base_url=VOICESTUDIO_BASE_URL,
        )
        registry.register(self.voicestudio_provider)
        return TTSService(registry)

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
        self.audio_preview_controller.finished.connect(self._on_tts_preview_playback_success)
        self.audio_preview_controller.failed.connect(self._on_tts_preview_playback_failed)
        self.audio_preview_controller.state_changed.connect(self._on_tts_preview_state_changed)

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

        primary_label = QLabel("LÀM VIDEO")
        primary_label.setObjectName("brandSub")
        primary_label.setContentsMargins(10, 0, 0, 3)
        layout.addWidget(primary_label)

        for item in PRIMARY_NAV_ITEMS:
            button = QPushButton(f"  {item.label}")
            button.setProperty("class", "navButton")
            button.setProperty("selected", False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(40)
            button.clicked.connect(lambda checked=False, key=item.key: self.navigate_to(key))
            self.nav_buttons[item.key] = button
            layout.addWidget(button)

        layout.addSpacing(8)
        self.advanced_toggle_button = QPushButton("  ▸ Nâng cao")
        self.advanced_toggle_button.setProperty("class", "navButton")
        self.advanced_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.advanced_toggle_button.setMinimumHeight(40)
        self.advanced_toggle_button.clicked.connect(self._toggle_advanced_navigation)
        layout.addWidget(self.advanced_toggle_button)

        self.advanced_nav_buttons: list[QPushButton] = []
        self._advanced_nav_expanded = False
        for item in ADVANCED_NAV_ITEMS:
            button = QPushButton(f"      {item.label}")
            button.setProperty("class", "navButton")
            button.setProperty("selected", False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(36)
            button.clicked.connect(lambda checked=False, key=item.key: self.navigate_to(key))
            button.setVisible(False)
            self.nav_buttons[item.key] = button
            self.advanced_nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        version = QLabel("Creator Studio · M110.3 YouTube Reference Search")
        version.setObjectName("brandSub")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setWordWrap(True)
        layout.addWidget(version)
        return sidebar

    def _toggle_advanced_navigation(self, checked=False, force: bool | None = None):
        expanded = (not self._advanced_nav_expanded) if force is None else bool(force)
        self._advanced_nav_expanded = expanded
        self.advanced_toggle_button.setText("  ▾ Nâng cao" if expanded else "  ▸ Nâng cao")
        for button in self.advanced_nav_buttons:
            button.setVisible(expanded)

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(66)

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        self.top_title = QLabel("Tạo video")
        self.top_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #eef4fb;")

        self.top_subtitle = QLabel("Quy trình tự động từ kịch bản đến video hoàn chỉnh")
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

        ui_status = QLabel("● Giao diện sẵn sàng")
        ui_status.setObjectName("statusGood")

        engine_status = QLabel("Engine: sẵn sàng")
        engine_status.setObjectName("muted")

        self.project_footer_status = QLabel("Dự án: chưa mở")
        self.project_footer_status.setObjectName("muted")

        self.provider_footer_status = QLabel("Chẩn đoán nhà cung cấp: sẵn sàng")
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
        self.automation_page = AutomationPage(
            self.create_new_project,
            self.open_project,
            self._start_automation_workflow,
            lambda: self.navigate_to("voice"),
            self._cancel_automation_workflow,
        )
        self._register_page("automation", self.automation_page)

        # M108 dashboard is kept as an internal compatibility surface, but it is
        # intentionally removed from the default end-user navigation.
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

        self.voice_page = VoiceScriptPage(
            self.select_voice_file,
            self.preview_voice_file,
            self.clear_voice_file,
            self.import_script_file,
            self.save_script_from_page,
            self.clear_script_from_project,
            self.run_voice_pipeline,
            self.open_voice_output_folder,
            self.open_voice_history_folder,
            self.refresh_tts_provider,
            self.refresh_tts_voices,
            self.preview_tts_voice,
            self.toggle_tts_preview_pause,
            self.stop_tts_preview,
            self.generate_tts_voice,
            self.open_script_folder,
            self.select_clone_reference_audio,
            self.create_voice_clone,
            self.refresh_voice_asset_library,
            self.preview_selected_voice_asset,
            self.use_selected_voice_asset,
            self.open_voice_asset_folder,
        )
        self.voice_page.set_tts_providers(self.tts_service.list_providers())
        QTimer.singleShot(0, self.refresh_tts_provider)
        self._register_page(
            "voice",
            self.voice_page,
        )

        self.scene_page = SceneAssetAssignmentPage(
            self.refresh_scene_asset_assignment,
            self.assign_selected_scene_asset,
            self.remove_selected_scene_asset,
            self.open_selected_scene_media_asset,
        )
        self._register_page("scenes", self.scene_page)

        self.media_page = MediaAssetLibraryPage(
            self.import_image_asset,
            self.import_video_asset,
            self.refresh_media_asset_library,
            self.open_selected_media_asset,
            self.open_media_asset_folder,
        )
        self._register_page("media", self.media_page)

        self._register_page(
            "vision",
            ModulePage(
                "AI hình ảnh",
                "Cấu hình và kiểm tra các chức năng AI hình ảnh/nhà cung cấp được pipeline sử dụng.",
                "Khu vực AI hình ảnh",
                "Nhà cung cấp, mô hình, giới hạn dữ liệu và quá trình gửi yêu cầu sẽ được hiển thị tại đây.",
                [
                    ("Nhà cung cấp", "Chọn nhà cung cấp AI và mô hình đã cấu hình."),
                    ("Giới hạn yêu cầu", "Kiểm soát giới hạn dữ liệu gửi và đầu vào hình ảnh."),
                    ("Kiểm tra", "Hiển thị trạng thái sẵn sàng và kết quả chẩn đoán phản hồi."),
                ],
                "Kiểm tra AI hình ảnh",
            ),
        )

        self._register_page(
            "timeline",
            ModulePage(
                "Dòng thời gian",
                "Đồng bộ giọng đọc, cảnh và tư liệu đã gán trước khi xuất video.",
                "Khu vực dòng thời gian",
                "Phiên bản đầu tập trung vào đồng bộ thời gian cảnh ổn định thay vì xây dựng ngay một trình dựng phim phức tạp.",
                [
                    ("Track giọng đọc", "Thời lượng giọng đọc là mốc thời gian chính."),
                    ("Khối cảnh", "Mỗi cảnh hiển thị thời điểm bắt đầu, kết thúc và tư liệu được gán."),
                    ("Điều chỉnh", "Cắt, kéo dài, thay thế hoặc tắt âm tư liệu của cảnh."),
                ],
                "Tạo dòng thời gian",
            ),
        )

        self._register_page(
            "export",
            ModulePage(
                "Xuất video",
                "Chọn thiết lập kết xuất và tạo video hoàn chỉnh bằng engine hiện có.",
                "Khu vực xuất video",
                "FFmpeg và bộ chạy sản xuất hiện tại vẫn hoạt động phía sau giao diện.",
                [
                    ("Định dạng", "Độ phân giải, FPS, codec và mức chất lượng."),
                    ("Kiểm tra", "Kiểm tra mức độ sẵn sàng của dự án trước khi kết xuất."),
                    ("Tiến trình", "Hiển thị tiến trình kết xuất và đường dẫn video đầu ra."),
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
                "Quản lý tùy chọn ứng dụng, nhà cung cấp và API Key.",
                "Thiết lập ứng dụng",
                "Trang này sẽ kết nối với trình quản lý API Key hiện có mà không đưa thông tin bí mật vào trạng thái giao diện.",
                [
                    ("Nhà cung cấp API", "Quản lý các cấu hình nhà cung cấp đã thiết lập."),
                    ("Nguồn stock", "Pexels, Pixabay và các nguồn bổ sung sau này."),
                    ("Ứng dụng", "Đường dẫn, bộ nhớ đệm, giao diện và thiết lập xuất mặc định."),
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
            default_projects_root = data.get("default_projects_root")

            if recent is not None and type(recent) is not str:
                return {}
            if default_projects_root is not None and type(default_projects_root) is not str:
                return {}

            return {
                "recent_project": recent or "",
                "default_projects_root": default_projects_root or "",
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
            "default_projects_root": str(
                (self._ui_state or {}).get("default_projects_root", "") or ""
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
                f"Đã mở lại dự án gần nhất: "
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

        if hasattr(self, "automation_page"):
            self.automation_page.set_project(manifest, manifest_path)
            self._sync_automation_voice_summary()

        if hasattr(
            self,
            "voice_page",
        ):
            self.voice_page.set_project(
                manifest,
                manifest_path,
            )

        if hasattr(self, "media_page"):
            self.media_page.set_project(manifest, manifest_path)

        if hasattr(self, "scene_page"):
            self.scene_page.set_project(manifest, manifest_path)

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
                    else "Dự án: chưa mở"
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

    def _sync_automation_voice_summary(self):
        if not hasattr(self, "automation_page"):
            return
        if self.current_project is None:
            self.automation_page.set_voice_summary("Chưa có dự án. Thiết lập giọng đọc sau khi tạo hoặc mở dự án.")
            return

        voice = getattr(self.current_project, "voice", None)
        provider = str(getattr(voice, "provider", "") or "Chưa chọn provider")
        voice_id = str(getattr(voice, "voice_id", "") or "Chưa chọn giọng")
        speed = getattr(voice, "speed", None)
        speed_text = f" · tốc độ {float(speed):.2f}" if isinstance(speed, (int, float)) else ""
        self.automation_page.set_voice_summary(
            f"{provider} · {voice_id}{speed_text}. Bấm 'Thiết lập giọng đọc' để thay đổi."
        )

    def _automation_workflow_from_project(self) -> AutomationWorkflowState:
        state = AutomationWorkflowState()
        manifest = self.current_project
        manifest_path = self.current_project_path
        if manifest is None or manifest_path is None:
            state.message = "Chưa mở dự án."
            return state

        script = str(getattr(getattr(manifest, "content", None), "script", "") or "").strip()
        if script:
            state.mark_completed("script", "Kịch bản đã được lưu trong dự án.")

        voice_input = next(
            (
                item
                for item in (getattr(manifest, "inputs", []) or [])
                if getattr(item, "id", None) == VOICE_INPUT_ID
                or getattr(item, "kind", None) == InputKind.VOICE
            ),
            None,
        )
        voice_path = None
        if voice_input is not None:
            reference = str(getattr(voice_input, "reference", "") or "")
            if reference:
                voice_path = Path(reference)
        if voice_path is not None and voice_path.is_file():
            state.mark_completed("voice", f"Đã có Voice Asset: {voice_path.name}")

            try:
                record = find_voice_asset_by_path(manifest_path.parent, voice_path)
                if record is not None:
                    scenes_path = latest_voice_scenes_path(manifest_path.parent, record.asset_id)
                    if scenes_path is not None and scenes_path.is_file():
                        scenes = load_voice_scenes(scenes_path)
                        state.mark_completed(
                            "voice_timing",
                            f"Đã có dữ liệu timing từ {scenes_path.parent.name}.",
                        )
                        state.mark_completed(
                            "scene_analysis",
                            f"Đã tạo {len(scenes)} cảnh dẫn xuất từ voice.",
                        )
            except Exception:
                pass

        next_key = state.first_incomplete_key()
        if next_key is None:
            state.message = "Các bước nền hiện có đều đã hoàn thành."
        else:
            label = next((item.label for item in AUTOMATION_STAGES if item.key == next_key), next_key)
            state.message = f"Bước tiếp theo: {label}."
        return state

    def _automation_apply_state(self):
        coordinator = self.automation_coordinator
        if coordinator is None or not hasattr(self, "automation_page"):
            return
        try:
            coordinator.save()
        except Exception:
            pass
        self.automation_page.apply_workflow_state(coordinator.state)

    def _automation_fail(self, stage_key: str, message: str):
        coordinator = self.automation_coordinator
        if coordinator is None:
            return
        try:
            coordinator.fail(stage_key, message)
        except Exception:
            coordinator.state.mark_failed(stage_key, str(message))
            coordinator.state.message = str(message)
        self._automation_waiting_for_voice_pipeline = False
        if hasattr(self, "automation_page"):
            self.automation_page.set_runner_controls_enabled(False)
        self._automation_apply_state()

    def _start_automation_workflow(self, script_text: str, language: str, config: dict):
        if self.current_project is None or self.current_project_path is None:
            QMessageBox.information(self, "Tạo video", "Hãy tạo hoặc mở dự án trước.")
            return None
        if self.tts_worker is not None and self.tts_worker.isRunning():
            QMessageBox.information(self, "Tạo video", "Một tác vụ tạo giọng đọc đang chạy. Hãy chờ tác vụ hiện tại hoàn tất.")
            return None
        if self.voice_pipeline_worker is not None and self.voice_pipeline_worker.isRunning():
            QMessageBox.information(self, "Tạo video", "Một tác vụ phân tích giọng đọc đang chạy. Hãy chờ tác vụ hiện tại hoàn tất.")
            return None
        if self.media_query_worker is not None and self.media_query_worker.isRunning():
            QMessageBox.information(self, "Tạo video", "Một tác vụ tạo truy vấn tìm tư liệu đang chạy. Hãy chờ tác vụ hiện tại hoàn tất.")
            return None
        if self.stock_acquisition_worker is not None and self.stock_acquisition_worker.isRunning():
            QMessageBox.information(self, "Tạo video", "Một tác vụ tìm/tải stock đang chạy. Hãy chờ tác vụ hiện tại hoàn tất.")
            return None
        if self.youtube_reference_worker is not None and self.youtube_reference_worker.isRunning():
            QMessageBox.information(self, "Tạo video", "Một tác vụ tìm YouTube Reference đang chạy. Hãy chờ tác vụ hiện tại hoàn tất.")
            return None

        try:
            saved_script_path = self._persist_script_file(script_text)
            updated = self._ingest_script_text(
                script_text,
                language,
                source_path=saved_script_path,
            )
            self._persist_project_update(
                updated,
                f"Đã chuẩn bị kịch bản cho quy trình tự động: {saved_script_path}",
            )
            if hasattr(self, "voice_page"):
                self.voice_page.set_script_text(
                    updated.content.script,
                    updated.content.source_language,
                    clean=True,
                )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Tạo video",
                f"Không thể lưu kịch bản.\n\n{type(exc).__name__}: {exc}",
            )
            return None

        try:
            coordinator = AutomationPipelineCoordinator.create(
                self.current_project_path.parent,
                script_text=script_text,
                language=language,
                config=config,
            )
            self.automation_coordinator = coordinator
            self._automation_cancel_requested = False
            self._automation_waiting_for_voice_pipeline = False
            state = coordinator.begin()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Tạo video",
                f"Không thể tạo phiên tự động.\n\n{type(exc).__name__}: {exc}",
            )
            return None

        if hasattr(self, "automation_page"):
            self.automation_page.set_runner_controls_enabled(True)

        request = self._validate_tts_request(preview=False)
        if request is None:
            coordinator.fail(
                "voice",
                "Không thể bắt đầu tạo giọng đọc. Hãy kiểm tra nhà cung cấp, engine và giọng đã chọn.",
            )
            if hasattr(self, "automation_page"):
                self.automation_page.set_runner_controls_enabled(False)
            return coordinator.state

        # The same tested TTSService/worker path used by the manual workspace is
        # reused here.  Automation only orchestrates it; no second TTS engine is
        # introduced.
        self._start_tts_worker(request, action="automation_generate")
        return state

    def _cancel_automation_workflow(self):
        coordinator = self.automation_coordinator
        if coordinator is None or coordinator.status not in (AutomationRunStatus.RUNNING, AutomationRunStatus.WAITING):
            return
        self._automation_cancel_requested = True
        self._automation_waiting_for_voice_pipeline = False
        coordinator.cancel(
            "Đã nhận yêu cầu hủy. Tác vụ đang chạy sẽ được phép kết thúc an toàn và Creator Studio sẽ không chạy bước tiếp theo."
        )
        if hasattr(self, "automation_page"):
            self.automation_page.set_runner_controls_enabled(False)
        self._automation_apply_state()

    def _automation_start_voice_pipeline(self):
        coordinator = self.automation_coordinator
        if coordinator is None:
            return
        self._automation_waiting_for_voice_pipeline = False
        if self._automation_cancel_requested or coordinator.status == AutomationRunStatus.CANCELLED:
            return

        try:
            coordinator.state.mark_running(
                "voice_timing",
                "Đang chép lời và xác định mốc thời gian từ giọng đọc...",
                progress=10,
            )
            coordinator.state.message = "Đang phân tích nội dung giọng đọc."
            coordinator.status = AutomationRunStatus.RUNNING
            coordinator.save()
        except Exception as exc:
            self._automation_fail("voice_timing", f"Không thể cập nhật trạng thái phân tích: {type(exc).__name__}: {exc}")
            return
        self._automation_apply_state()

        self.run_voice_pipeline()
        if self.voice_pipeline_worker is None or not self.voice_pipeline_worker.isRunning():
            self._automation_fail(
                "voice_timing",
                "Không thể khởi động bước phân tích nội dung từ giọng đọc.",
            )

    def _automation_start_media_query_planning(self, scenes_path: Path):
        coordinator = self.automation_coordinator
        if coordinator is None:
            return
        if self._automation_cancel_requested or coordinator.status == AutomationRunStatus.CANCELLED:
            return
        scenes_path = Path(scenes_path)
        if not scenes_path.is_file():
            self._automation_fail(
                "media_search",
                "Không tìm thấy danh sách cảnh để tạo truy vấn tìm tư liệu.",
            )
            return
        if self.media_query_worker is not None and self.media_query_worker.isRunning():
            return

        try:
            runtime_environment = self.api_manager.runtime_environment() or {}
        except Exception:
            runtime_environment = {}

        output_path = coordinator.run_dir / QUERY_PLAN_FILENAME
        cache_dir = coordinator.project_root / "cache" / "scene_intelligence"
        self.media_query_worker = SceneQueryPlanningWorker(
            scenes_path,
            output_path,
            language=coordinator.language,
            runtime_environment=runtime_environment,
            cache_dir=cache_dir,
            batch_size=8,
            parent=self,
        )
        self.media_query_worker.progress.connect(self._on_media_query_progress)
        self.media_query_worker.activity.connect(self._on_media_query_activity)
        self.media_query_worker.succeeded.connect(self._on_media_query_succeeded)
        self.media_query_worker.failed.connect(self._on_media_query_failed)
        self.media_query_worker.finished.connect(self._on_media_query_thread_finished)
        self.media_query_worker.start()

    def _on_media_query_activity(self, detail: str, progress: int):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        try:
            coordinator.media_query_activity(detail, progress=progress)
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"Không thể cập nhật trạng thái phân tích nhóm cảnh: {type(exc).__name__}: {exc}",
            )

    def _on_media_query_progress(self, current: int, total: int, scene_id: str, primary_query: str):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        try:
            coordinator.media_query_progress(
                current=current,
                total=total,
                scene_id=scene_id,
                primary_query=primary_query,
            )
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"Không thể cập nhật tiến trình tạo truy vấn: {type(exc).__name__}: {exc}",
            )

    def _on_media_query_succeeded(self, report):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        report = report if isinstance(report, dict) else {}
        try:
            coordinator.media_query_plan_completed(
                scene_count=int(report.get("scene_count") or 0),
                planned_count=int(report.get("planned_count") or 0),
                reused_gap_count=int(report.get("reused_gap_count") or 0),
                ai_count=int(report.get("ai_count") or 0),
                cache_hit_count=int(report.get("cache_hit_count") or 0),
                fallback_count=int(report.get("fallback_count") or 0),
                batch_request_count=int(report.get("batch_request_count") or 0),
                plan_filename=Path(str(report.get("output_path") or QUERY_PLAN_FILENAME)).name,
            )
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"Đã tạo truy vấn nhưng không thể lưu trạng thái tự động: {type(exc).__name__}: {exc}",
            )
            return

        query_plan_path = Path(str(report.get("output_path") or ""))
        source_scenes_path = Path(str(report.get("source_scenes_path") or ""))
        QTimer.singleShot(
            0,
            lambda qp=query_plan_path, sp=source_scenes_path: self._automation_start_stock_acquisition(qp, sp),
        )

    def _automation_start_stock_acquisition(self, query_plan_path: Path, source_scenes_path: Path):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        if self.stock_acquisition_worker is not None and self.stock_acquisition_worker.isRunning():
            return
        query_plan_path = Path(query_plan_path)
        source_scenes_path = Path(source_scenes_path)
        if not query_plan_path.is_file():
            self._automation_fail("media_search", "Không tìm thấy visual_query_plan.json để tìm stock.")
            return
        if not source_scenes_path.is_file():
            self._automation_fail("media_search", "Không tìm thấy voice_scenes.json để gán stock vào cảnh.")
            return
        voice_asset_id = self._active_voice_asset_id_for_scenes()
        if not voice_asset_id:
            self._automation_fail("media_search", "Không xác định được Voice Asset hiện tại để lưu assignment.")
            return
        try:
            runtime_environment = self.api_manager.runtime_environment() or {}
        except Exception:
            runtime_environment = {}

        try:
            coordinator.media_stock_progress(current=0, total=1, scene_id="", phase="searching")
            self._automation_apply_state()
        except Exception:
            pass

        self.stock_acquisition_worker = StockAcquisitionWorker(
            project_root=coordinator.project_root,
            run_dir=coordinator.run_dir,
            query_plan_path=query_plan_path,
            source_scenes_path=source_scenes_path,
            voice_asset_id=voice_asset_id,
            runtime_environment=runtime_environment,
            parent=self,
        )
        self.stock_acquisition_worker.progress.connect(self._on_stock_acquisition_progress)
        self.stock_acquisition_worker.succeeded.connect(self._on_stock_acquisition_succeeded)
        self.stock_acquisition_worker.failed.connect(self._on_stock_acquisition_failed)
        self.stock_acquisition_worker.finished.connect(self._on_stock_acquisition_thread_finished)
        self.stock_acquisition_worker.start()

    def _on_stock_acquisition_progress(self, current: int, total: int, scene_id: str, phase: str):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        try:
            coordinator.media_stock_progress(
                current=current,
                total=total,
                scene_id=scene_id,
                phase=phase,
            )
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"Không thể cập nhật tiến trình tìm stock: {type(exc).__name__}: {exc}",
            )

    def _on_stock_acquisition_succeeded(self, report):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        report = report if isinstance(report, dict) else {}
        try:
            coordinator.media_stock_completed(
                total_search_scenes=int(report.get("total_search_scenes") or 0),
                validated_count=int(report.get("validated_count") or 0),
                assigned_count=int(report.get("assigned_count") or 0),
                unresolved_count=int(report.get("unresolved_count") or 0),
                cache_hit_count=int(report.get("cache_hit_count") or 0),
                provider_names=tuple(report.get("provider_names") or ()),
                continue_to_youtube=True,
            )
            self.refresh_media_asset_library()
            self.refresh_scene_asset_assignment()
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"Stock hoàn tất nhưng không thể cập nhật Asset Library/assignment: {type(exc).__name__}: {exc}",
            )
            return

        stock_manifest_path = Path(str(report.get("manifest_path") or ""))
        query_plan_path = coordinator.run_dir / QUERY_PLAN_FILENAME
        QTimer.singleShot(
            0,
            lambda qp=query_plan_path, sm=stock_manifest_path: self._automation_start_youtube_reference(qp, sm),
        )

    def _automation_start_youtube_reference(self, query_plan_path: Path, stock_manifest_path: Path):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        if self.youtube_reference_worker is not None and self.youtube_reference_worker.isRunning():
            return
        query_plan_path = Path(query_plan_path)
        stock_manifest_path = Path(stock_manifest_path)
        if not query_plan_path.is_file():
            self._automation_fail("media_search", "Không tìm thấy visual_query_plan.json để tìm YouTube Reference.")
            return
        if not stock_manifest_path.is_file():
            self._automation_fail("media_search", "Không tìm thấy stock_acquisition_manifest.json để đánh giá fallback YouTube.")
            return
        try:
            runtime_environment = self.api_manager.runtime_environment() or {}
        except Exception:
            runtime_environment = {}
        # APIKeyManager may not expose YouTube yet; preserve an existing process
        # environment value without persisting it to automation state.
        if os.getenv("YOUTUBE_API_KEY") and not runtime_environment.get("YOUTUBE_API_KEY"):
            runtime_environment["YOUTUBE_API_KEY"] = os.getenv("YOUTUBE_API_KEY")

        self.youtube_reference_worker = YouTubeReferenceWorker(
            run_dir=coordinator.run_dir,
            query_plan_path=query_plan_path,
            stock_manifest_path=stock_manifest_path,
            language=coordinator.language,
            runtime_environment=runtime_environment,
            parent=self,
        )
        self.youtube_reference_worker.progress.connect(self._on_youtube_reference_progress)
        self.youtube_reference_worker.succeeded.connect(self._on_youtube_reference_succeeded)
        self.youtube_reference_worker.failed.connect(self._on_youtube_reference_failed)
        self.youtube_reference_worker.finished.connect(self._on_youtube_reference_thread_finished)
        self.youtube_reference_worker.start()

    def _on_youtube_reference_progress(self, current: int, total: int, scene_id: str, query: str):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        try:
            coordinator.media_youtube_progress(
                current=current,
                total=total,
                scene_id=scene_id,
                query=query,
            )
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"Không thể cập nhật tiến trình YouTube Reference: {type(exc).__name__}: {exc}",
            )

    def _on_youtube_reference_succeeded(self, report):
        coordinator = self.automation_coordinator
        if coordinator is None or self._automation_cancel_requested:
            return
        report = report if isinstance(report, dict) else {}
        try:
            coordinator.media_youtube_completed(
                target_count=int(report.get("target_count") or 0),
                searched_count=int(report.get("searched_count") or 0),
                reference_scene_count=int(report.get("reference_scene_count") or 0),
                candidate_count=int(report.get("candidate_count") or 0),
                chapter_segment_count=int(report.get("chapter_segment_count") or 0),
                unresolved_stock_count=int(report.get("unresolved_stock_count") or 0),
                weak_stock_count=int(report.get("weak_stock_count") or 0),
                missing_api_key=bool(report.get("missing_api_key")),
                error_count=int(report.get("error_count") or 0),
                manifest_filename=Path(str(report.get("manifest_path") or YOUTUBE_REFERENCE_FILENAME)).name,
            )
            if hasattr(self, "automation_page"):
                self.automation_page.set_runner_controls_enabled(False)
            self._automation_apply_state()
        except Exception as exc:
            self._automation_fail(
                "media_search",
                f"YouTube Reference hoàn tất nhưng không thể lưu trạng thái: {type(exc).__name__}: {exc}",
            )

    def _on_youtube_reference_failed(self, message: str):
        # Structural failures are surfaced. Ordinary HTTP/provider errors are
        # already converted to per-scene diagnostics inside the service.
        if self.automation_coordinator is not None and not self._automation_cancel_requested:
            self._automation_fail("media_search", f"Không thể chạy YouTube Reference: {message}")

    def _on_youtube_reference_thread_finished(self):
        worker = self.youtube_reference_worker
        self.youtube_reference_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_stock_acquisition_failed(self, message: str):
        if self.automation_coordinator is not None and not self._automation_cancel_requested:
            self._automation_fail("media_search", f"Không thể tìm/tải stock: {message}")

    def _on_stock_acquisition_thread_finished(self):
        worker = self.stock_acquisition_worker
        self.stock_acquisition_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_media_query_failed(self, message: str):
        if self.automation_coordinator is not None and not self._automation_cancel_requested:
            self._automation_fail("media_search", f"Không thể tạo truy vấn tìm tư liệu: {message}")

    def _on_media_query_thread_finished(self):
        worker = self.media_query_worker
        self.media_query_worker = None
        if worker is not None:
            worker.deleteLater()

    # Compatibility alias for tests/tools that still look up the M109.1 name.
    def _prepare_automation_workflow(self, script_text: str, language: str, config: dict):
        return self._start_automation_workflow(script_text, language, config)

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
        try:
            initialize_project_layout(self.current_project_path.parent)
        except Exception:
            pass

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
        if hasattr(self, "voice_page"):
            self.refresh_voice_asset_library()
        if hasattr(self, "media_page"):
            self.refresh_media_asset_library()
        if hasattr(self, "scene_page"):
            self.refresh_scene_asset_assignment()

    def create_new_project(self):
        if self.provider_diagnostics_binder.is_running:
            QMessageBox.information(
                self,
                "Chẩn đoán nhà cung cấp đang chạy",
                "Hãy chờ chẩn đoán nhà cung cấp kết thúc trước khi tạo dự án mới.",
            )
            return

        default_parent_text = str((self._ui_state or {}).get("default_projects_root", "") or "")
        default_parent = Path(default_parent_text) if default_parent_text else WORKSPACES_ROOT
        try:
            default_parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            default_parent = Path.home()

        dialog = ProjectCreationDialog(default_parent, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        project_name = dialog.project_name()
        parent_directory = dialog.parent_directory()

        project_folder = None
        try:
            manifest = ProjectManifest(project_name)
            project_folder = create_project_root(parent_directory, project_name)
            manifest_path = project_folder / PROJECT_MANIFEST_FILENAME
            save_project_manifest(manifest, manifest_path)
        except Exception as exc:
            if project_folder is not None and project_folder.exists():
                try:
                    if not (project_folder / PROJECT_MANIFEST_FILENAME).exists():
                        shutil.rmtree(project_folder, ignore_errors=True)
                except Exception:
                    pass
            QMessageBox.critical(
                self,
                "Tạo dự án mới",
                "Không thể tạo dự án.\n\n"
                f"{type(exc).__name__}: {exc}",
            )
            return

        self._ui_state["default_projects_root"] = str(parent_directory)
        self._set_current_project(
            manifest,
            manifest_path,
            notice=f"Đã tạo dự án tại: {project_folder}",
            notice_kind="good",
        )
        self.refresh_voice_asset_library()
        self.refresh_media_asset_library()
        self.refresh_scene_asset_assignment()
        self.navigate_to("project")

    def open_project(self):
        start_directory = (
            str(
                self.current_project_path.parent
            )
            if self.current_project_path is not None
            else str(
                Path((self._ui_state or {}).get("default_projects_root", "") or WORKSPACES_ROOT)
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


    def _voice_input_path(self) -> Path | None:
        if self.current_project is None:
            return None
        for item in getattr(self.current_project, "inputs", []) or []:
            if getattr(item, "id", None) == VOICE_INPUT_ID or getattr(item, "kind", None) == InputKind.VOICE:
                reference = str(getattr(item, "reference", "") or "")
                if reference:
                    return Path(reference)
        return None

    def _persist_project_update(self, manifest: ProjectManifest, notice: str | None = None):
        if self.current_project_path is None:
            raise RuntimeError("Chưa có tệp dự án để lưu.")
        save_project_manifest(manifest, self.current_project_path)
        self.current_project = manifest
        self._apply_project_to_ui(self.current_project, self.current_project_path)
        self._save_ui_state()
        if notice and hasattr(self, "project_page"):
            self.project_page.set_notice(notice, "good")

    def select_voice_file(self):
        if self.current_project is None or self.current_project_path is None:
            QMessageBox.information(self, "Giọng đọc", "Hãy tạo hoặc mở dự án trước.")
            return

        start_dir = str(self.current_project_path.parent)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp giọng đọc",
            start_dir,
            "Tệp âm thanh (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus);;Tất cả tệp (*.*)",
        )
        if not file_path:
            return

        source_path = Path(file_path).resolve()
        if not source_path.is_file():
            QMessageBox.warning(self, "Giọng đọc", "Tệp đã chọn không tồn tại.")
            return

        try:
            record = import_voice_asset(
                self.current_project_path.parent,
                source_path,
                display_name=source_path.stem,
            )
            path = record.audio_path.resolve()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Nhập giọng đọc",
                "Không thể sao chép tệp giọng vào thư viện asset của dự án.\n\n"
                f"{type(exc).__name__}: {exc}",
            )
            return

        inputs = [
            item
            for item in (getattr(self.current_project, "inputs", []) or [])
            if getattr(item, "id", None) != VOICE_INPUT_ID
            and getattr(item, "kind", None) != InputKind.VOICE
        ]
        inputs.append(
            InputSource(
                id=VOICE_INPUT_ID,
                kind=InputKind.VOICE,
                reference=str(path),
            )
        )

        updated_voice = replace(
            self.current_project.voice,
            kind=VoiceKind.IMPORTED,
            provider=None,
            voice_id=record.asset_id,
            speed=1.0,
            style="",
            status=Status.PENDING,
            audio_media_id=None,
            alignment_reference=None,
        )
        updated = replace(self.current_project, inputs=inputs, voice=updated_voice)

        try:
            self._persist_project_update(updated, f"Đã nhập Voice Asset: {path.name}")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Giọng đọc",
                f"Asset đã được tạo nhưng không thể cập nhật dự án.\n\n{type(exc).__name__}: {exc}",
            )
            return

        self.refresh_voice_asset_library()
        self.navigate_to("voice")

    def preview_voice_file(self):
        path = self._voice_input_path()
        if path is None or not path.is_file():
            QMessageBox.information(self, "Nghe thử", "Không tìm thấy tệp giọng đọc hiện tại.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "Nghe thử", "Windows không thể mở tệp âm thanh bằng trình phát mặc định.")

    def clear_voice_file(self):
        if self.current_project is None:
            return
        if self.voice_pipeline_worker is not None and self.voice_pipeline_worker.isRunning():
            QMessageBox.information(self, "Giọng đọc", "Hãy chờ quá trình xử lý giọng đọc kết thúc.")
            return

        answer = QMessageBox.question(
            self,
            "Bỏ giọng đọc",
            "Bỏ liên kết tệp giọng đọc khỏi dự án? Tệp gốc trên ổ đĩa sẽ không bị xóa.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        inputs = [
            item
            for item in (getattr(self.current_project, "inputs", []) or [])
            if getattr(item, "id", None) != VOICE_INPUT_ID
            and getattr(item, "kind", None) != InputKind.VOICE
        ]
        updated_voice = replace(
            self.current_project.voice,
            kind=VoiceKind.IMPORTED,
            provider=None,
            voice_id=None,
            speed=1.0,
            style="",
            status=Status.PENDING,
            audio_media_id=None,
            alignment_reference=None,
        )
        updated = replace(self.current_project, inputs=inputs, voice=updated_voice)
        try:
            self._persist_project_update(updated, "Đã bỏ giọng đọc khỏi dự án.")
        except Exception as exc:
            QMessageBox.critical(self, "Giọng đọc", f"Không thể cập nhật dự án.\n\n{type(exc).__name__}: {exc}")

    def refresh_voice_asset_library(self):
        if not hasattr(self, "voice_page"):
            return
        if self.current_project_path is None:
            self.voice_page.set_voice_assets((), None)
            return
        try:
            records = scan_voice_assets(self.current_project_path.parent)
        except Exception as exc:
            records = []
            if hasattr(self.voice_page, "append_log"):
                self.voice_page.append_log(
                    f"VOICE ASSET LIBRARY WARNING: {type(exc).__name__}: {exc}"
                )
        self.voice_page.set_voice_assets(records, self._voice_input_path())

    def _selected_voice_asset_record(self) -> VoiceAssetRecord | None:
        if self.current_project_path is None:
            return None
        path = self.voice_page.selected_voice_asset_path()
        if path is None:
            return None
        return find_voice_asset_by_path(self.current_project_path.parent, path)

    def preview_selected_voice_asset(self):
        path = self.voice_page.selected_voice_asset_path()
        if path is None or not path.is_file():
            QMessageBox.information(self, "Voice Asset", "Hãy chọn một tệp trong thư viện giọng.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "Voice Asset", "Windows không thể mở tệp âm thanh đã chọn.")

    def open_voice_asset_folder(self):
        if self.current_project_path is None:
            QMessageBox.information(self, "Voice Asset", "Hãy tạo hoặc mở dự án trước.")
            return
        path = self.voice_page.selected_voice_asset_path()
        target = path.parent if path is not None and path.exists() else voice_assets_root(self.current_project_path.parent)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            QMessageBox.warning(self, "Voice Asset", f"Windows không thể mở thư mục:\n\n{target}")

    def use_selected_voice_asset(self):
        if self.current_project is None or self.current_project_path is None:
            return
        record = self._selected_voice_asset_record()
        if record is None or not record.audio_path.is_file():
            QMessageBox.warning(self, "Voice Asset", "Không tìm thấy Voice Asset đã chọn.")
            return

        path = record.audio_path.resolve()
        inputs = [
            item
            for item in (getattr(self.current_project, "inputs", []) or [])
            if getattr(item, "id", None) != VOICE_INPUT_ID
            and getattr(item, "kind", None) != InputKind.VOICE
        ]
        inputs.append(InputSource(id=VOICE_INPUT_ID, kind=InputKind.VOICE, reference=str(path)))

        generated = record.kind == "generated"
        updated_voice = replace(
            self.current_project.voice,
            kind=VoiceKind.GENERATED if generated else VoiceKind.IMPORTED,
            provider=record.provider_id if generated else None,
            language=record.language or self.voice_page.selected_language(),
            voice_id=record.voice_id or record.asset_id,
            speed=record.speed or 1.0,
            style="",
            status=Status.SUCCEEDED if generated else Status.PENDING,
            audio_media_id=None,
            alignment_reference=None,
        )
        updated = replace(self.current_project, inputs=inputs, voice=updated_voice)
        try:
            self._persist_project_update(updated, f"Đang dùng Voice Asset: {record.display_name}")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Voice Asset",
                f"Không thể đặt Voice Asset làm giọng hiện tại.\n\n{type(exc).__name__}: {exc}",
            )
            return
        self.refresh_voice_asset_library()
        self.voice_page.set_process_status(
            "Đã chọn Voice Asset. Có thể chạy Chép lời + Tạo phụ đề + Cảnh.",
            "good",
        )

    def refresh_media_asset_library(self):
        if not hasattr(self, "media_page"):
            return
        if self.current_project_path is None:
            self.media_page.set_assets(())
            return
        try:
            records = scan_media_assets(self.current_project_path.parent)
        except Exception as exc:
            records = []
            self.media_page.set_notice(
                f"Không thể đọc Media Asset Library: {type(exc).__name__}: {exc}",
                "warn",
            )
        self.media_page.set_assets(records)

    def _import_media_asset_dialog(self, media_type: str):
        if self.current_project_path is None:
            QMessageBox.information(
                self,
                "Media Asset Library",
                "Hãy tạo hoặc mở dự án trước.",
            )
            return

        if media_type == "image":
            title = "Nhập ảnh vào dự án"
            file_filter = "Ảnh (*.jpg *.jpeg *.png *.webp *.bmp *.gif);;Tất cả tệp (*.*)"
        else:
            title = "Nhập video vào dự án"
            file_filter = "Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v);;Tất cả tệp (*.*)"

        files, _ = QFileDialog.getOpenFileNames(
            self,
            title,
            str(Path.home()),
            file_filter,
        )
        if not files:
            return

        imported = 0
        failures = []
        for file_name in files:
            try:
                import_media_asset(
                    self.current_project_path.parent,
                    Path(file_name),
                    media_type=media_type,
                )
                imported += 1
            except Exception as exc:
                failures.append(f"{Path(file_name).name}: {type(exc).__name__}: {exc}")

        self.refresh_media_asset_library()
        if failures:
            detail = "\n".join(failures[:8])
            if len(failures) > 8:
                detail += f"\n... và {len(failures) - 8} lỗi khác."
            self.media_page.set_notice(
                f"Đã nhập {imported} tệp; {len(failures)} tệp lỗi.",
                "warn",
            )
            QMessageBox.warning(
                self,
                "Nhập Media Asset",
                f"Đã nhập {imported} tệp. Có {len(failures)} tệp không nhập được.\n\n{detail}",
            )
        else:
            label = "ảnh" if media_type == "image" else "video"
            self.media_page.set_notice(
                f"Đã nhập {imported} {label} vào Asset Library của dự án.",
                "good",
            )

    def import_image_asset(self):
        self._import_media_asset_dialog("image")

    def import_video_asset(self):
        self._import_media_asset_dialog("video")

    def open_selected_media_asset(self):
        path = self.media_page.selected_media_asset_path()
        if path is None or not path.is_file():
            QMessageBox.information(
                self,
                "Media Asset",
                "Hãy chọn một ảnh hoặc video trong thư viện.",
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                "Media Asset",
                f"Windows không thể mở tệp:\n\n{path}",
            )

    def open_media_asset_folder(self):
        if self.current_project_path is None:
            QMessageBox.information(
                self,
                "Media Asset",
                "Hãy tạo hoặc mở dự án trước.",
            )
            return
        selected = self.media_page.selected_media_asset_path()
        target = (
            selected.parent
            if selected is not None and selected.exists()
            else media_assets_root(self.current_project_path.parent)
        )
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            QMessageBox.warning(
                self,
                "Media Asset",
                f"Windows không thể mở thư mục:\n\n{target}",
            )

    def _active_voice_asset_id_for_scenes(self) -> str | None:
        if self.current_project_path is None:
            return None
        voice_path = self._voice_input_path()
        if voice_path is None or not voice_path.is_file():
            return None
        record = find_voice_asset_by_path(self.current_project_path.parent, voice_path)
        if record is not None:
            return record.asset_id
        return f"legacy_{storage_safe_slug(voice_path.stem, 'voice')}"

    def refresh_scene_asset_assignment(self):
        if not hasattr(self, "scene_page"):
            return
        if self.current_project_path is None or self.current_project is None:
            self.scene_page.set_data([], [], None, None)
            self.scene_page.set_notice("Hãy tạo hoặc mở dự án để xem cảnh.")
            return

        project_root = self.current_project_path.parent
        try:
            assets = scan_media_assets(project_root)
        except Exception as exc:
            self.scene_page.set_data([], [], None, None)
            self.scene_page.set_notice(
                f"Không thể đọc Media Asset Library: {type(exc).__name__}: {exc}",
                "bad",
            )
            return

        voice_asset_id = self._active_voice_asset_id_for_scenes()
        if not voice_asset_id:
            self.scene_page.set_data([], assets, None, None)
            self.scene_page.set_notice(
                "Chưa có Voice Asset hiện tại. Hãy chọn/tạo giọng đọc rồi chạy VoicePipeline.",
                "warn",
            )
            return

        try:
            scenes_path = latest_voice_scenes_path(project_root, voice_asset_id)
        except Exception as exc:
            self.scene_page.set_data([], assets, None, None)
            self.scene_page.set_notice(
                f"Không thể tìm VoicePipeline run: {type(exc).__name__}: {exc}",
                "bad",
            )
            return

        if scenes_path is None:
            self.scene_page.set_data([], assets, None, None)
            self.scene_page.set_notice(
                "Chưa có voice_scenes.json cho Voice Asset hiện tại. Hãy chạy VoicePipeline trước.",
                "warn",
            )
            return

        try:
            scenes = load_voice_scenes(scenes_path)
            state = load_scene_assignment_state(
                project_root,
                voice_asset_id,
                scenes_path,
            )
        except Exception as exc:
            self.scene_page.set_data([], assets, None, scenes_path)
            self.scene_page.set_notice(
                f"Không thể đọc nguồn cảnh/assignment: {type(exc).__name__}: {exc}",
                "bad",
            )
            return

        self.scene_page.set_data(scenes, assets, state, scenes_path)
        assigned_count = len(state.assignments)
        self.scene_page.set_notice(
            f"Đã nạp {len(scenes)} cảnh · {assigned_count} cảnh đã gán tư liệu · "
            "assignment được lưu riêng theo VoicePipeline run.",
            "good",
        )

    def _current_scene_assignment_context(self):
        if self.current_project_path is None:
            return None, None, None
        voice_asset_id = self._active_voice_asset_id_for_scenes()
        if not voice_asset_id:
            return self.current_project_path.parent, None, None
        scenes_path = latest_voice_scenes_path(self.current_project_path.parent, voice_asset_id)
        return self.current_project_path.parent, voice_asset_id, scenes_path

    def assign_selected_scene_asset(self):
        scene_id = self.scene_page.selected_scene_id()
        asset_id = self.scene_page.selected_asset_id()
        if not scene_id or not asset_id:
            QMessageBox.information(
                self,
                "Gán tư liệu",
                "Hãy chọn một cảnh và một Media Asset trước.",
            )
            return
        project_root, voice_asset_id, scenes_path = self._current_scene_assignment_context()
        if project_root is None or not voice_asset_id or scenes_path is None:
            QMessageBox.warning(
                self,
                "Gán tư liệu",
                "Chưa có VoicePipeline run phù hợp với Voice Asset hiện tại.",
            )
            return
        try:
            assign_media_asset(
                project_root,
                voice_asset_id,
                scenes_path,
                scene_id,
                asset_id,
            )
            self.refresh_scene_asset_assignment()
            self.scene_page.set_notice(
                f"Đã gán Media Asset {asset_id} cho {scene_id}.",
                "good",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Gán tư liệu",
                f"Không thể lưu assignment.\n\n{type(exc).__name__}: {exc}",
            )

    def remove_selected_scene_asset(self):
        scene_id = self.scene_page.selected_scene_id()
        if not scene_id:
            return
        project_root, voice_asset_id, scenes_path = self._current_scene_assignment_context()
        if project_root is None or not voice_asset_id or scenes_path is None:
            return
        try:
            remove_scene_assignment(
                project_root,
                voice_asset_id,
                scenes_path,
                scene_id,
            )
            self.refresh_scene_asset_assignment()
            self.scene_page.set_notice(f"Đã bỏ tư liệu khỏi {scene_id}.", "good")
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Bỏ gán tư liệu",
                f"Không thể cập nhật assignment.\n\n{type(exc).__name__}: {exc}",
            )

    def open_selected_scene_media_asset(self):
        path = self.scene_page.selected_asset_path()
        if path is None or not path.is_file():
            assigned_id = self.scene_page.selected_scene_assignment_asset_id()
            path = self.scene_page.asset_path_by_id(assigned_id)
        if path is None or not path.is_file():
            QMessageBox.information(
                self,
                "Tư liệu cảnh",
                "Hãy chọn Media Asset hoặc một cảnh đã được gán tư liệu.",
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                "Tư liệu cảnh",
                f"Windows không thể mở tệp:\n\n{path}",
            )

    def _script_workspace_dir(self) -> Path:
        if self.current_project_path is None:
            raise RuntimeError("Hãy tạo hoặc mở dự án trước.")
        script_dir = self.current_project_path.parent / SCRIPT_WORKSPACE_DIRNAME
        script_dir.mkdir(parents=True, exist_ok=True)
        return script_dir

    def _persist_script_file(self, text: str) -> Path:
        if not text.strip():
            raise ValueError("Kịch bản không được để trống.")

        script_dir = self._script_workspace_dir()
        script_path = script_dir / SCRIPT_WORKSPACE_FILENAME
        temp_path = script_dir / f".{SCRIPT_WORKSPACE_FILENAME}.tmp"

        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(script_path)
        return script_path

    def open_script_folder(self):
        if self.current_project_path is None:
            QMessageBox.information(
                self,
                "Kịch bản đã lưu",
                "Hãy tạo hoặc mở dự án trước.",
            )
            return

        try:
            script_dir = self._script_workspace_dir()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kịch bản đã lưu",
                f"Không thể tạo thư mục kịch bản.\n\n{type(exc).__name__}: {exc}",
            )
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(script_dir))):
            QMessageBox.warning(
                self,
                "Kịch bản đã lưu",
                f"Windows không thể mở thư mục:\n\n{script_dir}",
            )

    def _ingest_script_text(self, text: str, language: str, source_path: Path | None = None):
        if self.current_project is None or self.current_project_path is None:
            raise RuntimeError("Hãy tạo hoặc mở dự án trước.")
        if not text.strip():
            raise ValueError("Kịch bản không được để trống.")

        request = IngestRequest(
            content_id=SCRIPT_CONTENT_ID,
            text=text,
            language=language or "und",
            title="Kịch bản Creator Studio",
        )
        result = ingest_content(request)
        if getattr(result, "content", None) is None:
            diagnostics = getattr(result, "diagnostics", []) or []
            detail = "; ".join(str(getattr(item, "code", item)) for item in diagnostics) or "content_ingest_failed"
            raise ValueError(detail)

        updated = apply_ingest(self.current_project, result, canonical=True)
        inputs = [
            item
            for item in (getattr(updated, "inputs", []) or [])
            if getattr(item, "id", None) != SCRIPT_INPUT_ID
        ]
        if source_path is not None:
            inputs.append(
                InputSource(
                    id=SCRIPT_INPUT_ID,
                    kind=InputKind.TXT,
                    reference=str(Path(source_path).resolve()),
                )
            )
        return replace(updated, inputs=inputs)

    def save_script_from_page(self):
        if self.current_project is None:
            QMessageBox.information(self, "Kịch bản", "Hãy tạo hoặc mở dự án trước.")
            return
        text = self.voice_page.script_text()
        language = self.voice_page.selected_language()
        try:
            saved_script_path = self._persist_script_file(text)
            updated = self._ingest_script_text(
                text,
                language,
                source_path=saved_script_path,
            )
            self._persist_project_update(
                updated,
                f"Đã lưu kịch bản: {saved_script_path}",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Lưu kịch bản",
                f"Không thể lưu kịch bản.\n\n{type(exc).__name__}: {exc}",
            )
            return
        self.voice_page.set_script_text(updated.content.script, updated.content.source_language, clean=True)

    def import_script_file(self):
        if self.current_project is None or self.current_project_path is None:
            QMessageBox.information(self, "Kịch bản", "Hãy tạo hoặc mở dự án trước.")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Nhập kịch bản từ TXT",
            str(self.current_project_path.parent),
            "Tệp văn bản UTF-8 (*.txt);;Tất cả tệp (*.*)",
        )
        if not file_path:
            return
        path = Path(file_path)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            QMessageBox.warning(self, "Nhập kịch bản", f"Không thể đọc tệp UTF-8.\n\n{type(exc).__name__}: {exc}")
            return

        language = self.voice_page.selected_language()
        try:
            saved_script_path = self._persist_script_file(text)
            updated = self._ingest_script_text(
                text,
                language,
                source_path=saved_script_path,
            )
            self._persist_project_update(
                updated,
                f"Đã nhập kịch bản {path.name} và lưu tại: {saved_script_path}",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Nhập kịch bản",
                f"Không thể nhập kịch bản.\n\n{type(exc).__name__}: {exc}",
            )
            return
        self.voice_page.set_script_text(updated.content.script, updated.content.source_language, clean=True)

    def clear_script_from_project(self):
        if self.current_project is None:
            return
        if (getattr(self.current_project, "scenes", None) or []) or _object_has_non_default_state(getattr(self.current_project, "semantic", None)):
            QMessageBox.warning(
                self,
                "Xóa kịch bản",
                "Dự án đã có dữ liệu downstream liên quan đến kịch bản. Hãy tạo dự án mới hoặc xử lý việc vô hiệu hóa dữ liệu downstream trước khi xóa kịch bản.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Xóa kịch bản",
            "Xóa kịch bản hiện tại khỏi ProjectManifest?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        inputs = [
            item
            for item in (getattr(self.current_project, "inputs", []) or [])
            if getattr(item, "id", None) != SCRIPT_INPUT_ID
        ]
        cleared_content = Content(
            source_language=self.voice_page.selected_language(),
            review_language=getattr(self.current_project.content, "review_language", "vi"),
        )
        updated = replace(self.current_project, content=cleared_content, inputs=inputs)
        try:
            self._persist_project_update(updated, "Đã xóa kịch bản khỏi dự án.")
        except Exception as exc:
            QMessageBox.warning(self, "Xóa kịch bản", f"Không thể xóa kịch bản.\n\n{type(exc).__name__}: {exc}")

    def _sync_voicestudio_backend_endpoint(self) -> str | None:
        """Discover VoiceStudio's real loopback port and update the provider."""
        try:
            endpoint = self.voicestudio_runtime.discover_backend_url(timeout_seconds=0.12)
        except Exception:
            endpoint = None
        if endpoint:
            try:
                self.voicestudio_provider.set_base_url(endpoint)
            except Exception:
                return None
        return endpoint

    def refresh_tts_provider(self):
        if not hasattr(self, "voice_page"):
            return
        provider_id = self.voice_page.selected_tts_provider_id()
        if not provider_id:
            self.voice_page.set_tts_engines(())
            self.voice_page.set_tts_voices(())
            self.voice_page.set_voice_clone_available(False)
            self.voice_page.set_tts_health("Chưa có nhà cung cấp TTS.", "warn")
            return

        # VoiceStudio Electron may move its backend away from 3900 when Windows
        # reserves that port. Do not call the provider's old/default endpoint
        # when discovery has not found a real VoiceStudio service yet.
        endpoint = None
        if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            endpoint = self._sync_voicestudio_backend_endpoint()
            if endpoint is None:
                detail = (
                    "Chưa tìm thấy backend VoiceStudio trên loopback. "
                    "AI Video Editor sẽ mở VoiceStudio và tiếp tục dò cổng tự động."
                )
                self.voice_page.set_tts_engines(())
                self.voice_page.set_tts_voices(())
                self.voice_page.set_voice_clone_available(False)
                if self._begin_voicestudio_autostart(detail):
                    return
                self.voice_page.set_tts_health(detail, "warn")
                return

        try:
            healthy, detail = self.tts_service.health_check(provider_id)
        except Exception as exc:
            healthy = False
            detail = f"Không thể kiểm tra TTS: {type(exc).__name__}: {exc}"

        if not healthy and provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            self.voice_page.set_tts_engines(())
            self.voice_page.set_tts_voices(())
            self.voice_page.set_voice_clone_available(False)
            if self._begin_voicestudio_autostart(detail):
                return
            self.voice_page.set_tts_health(detail, "warn")
            return

        if not healthy:
            self.voice_page.set_tts_engines(())
            self.voice_page.set_tts_voices(())
            self.voice_page.set_voice_clone_available(False)
            self.voice_page.set_tts_health(detail, "warn")
            return

        if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            try:
                engines = self.tts_service.list_engines(provider_id)
            except Exception as exc:
                engines = ()
                detail = f"{detail} · Không lấy được engine: {type(exc).__name__}: {exc}"
            self.voice_page.set_tts_engines(engines)
            self.voice_page.set_tts_engine_visible(bool(engines))
        else:
            self.voice_page.set_tts_engines(())
            self.voice_page.set_tts_engine_visible(False)

        self.refresh_tts_voices(health_detail=detail)

    def refresh_tts_voices(self, *args, health_detail: str | None = None):
        if not hasattr(self, "voice_page"):
            return
        provider_id = self.voice_page.selected_tts_provider_id()
        if not provider_id:
            return

        if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            endpoint = self._sync_voicestudio_backend_endpoint()
            if endpoint is None:
                self.voice_page.set_tts_voices(())
                self.voice_page.set_voice_clone_available(False)
                detail = "VoiceStudio đang khởi động hoặc backend chưa xuất hiện trên cổng loopback."
                if self._begin_voicestudio_autostart(detail):
                    return
                self.voice_page.set_tts_health(detail, "warn")
                return

        try:
            healthy, detail = self.tts_service.health_check(provider_id)
        except Exception as exc:
            healthy = False
            detail = f"Không thể kiểm tra TTS: {type(exc).__name__}: {exc}"

        if health_detail:
            detail = health_detail

        if not healthy:
            self.voice_page.set_tts_voices(())
            self.voice_page.set_voice_clone_available(False)
            if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
                if self._begin_voicestudio_autostart(detail):
                    return
            self.voice_page.set_tts_health(detail, "warn")
            return

        model_id = None
        if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            model_id = self.voice_page.selected_tts_engine_id() or "tts-1"

        if model_id == "kittentts":
            # VoiceStudio 0.5.6 runs KittenTTS on CPU. Its natural cadence can
            # also sound slow at 1.00, so use a modest narration-oriented
            # default the first time this engine is selected. Users can still
            # choose any value afterwards.
            if abs(self.voice_page.selected_tts_speed() - 1.00) < 0.001:
                self.voice_page.set_tts_speed(1.15)

        try:
            voices = self.tts_service.list_voices(provider_id, model_id=model_id)
        except Exception as exc:
            voices = ()
            detail = f"Không thể tải danh sách giọng: {type(exc).__name__}: {exc}"
            healthy = False

        selected_voice_id = None
        if self.current_project is not None:
            voice_state = getattr(self.current_project, "voice", None)
            if str(getattr(voice_state, "provider", "") or "") == provider_id:
                selected_voice_id = str(getattr(voice_state, "voice_id", "") or "") or None

        self.voice_page.set_tts_voices(voices, selected_voice_id)

        if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            try:
                clone_available = healthy and self.tts_service.engine_supports_voice_cloning(
                    provider_id, model_id
                )
            except Exception:
                clone_available = False
        else:
            try:
                clone_available = healthy and self.tts_service.supports_voice_cloning(provider_id)
            except Exception:
                clone_available = False
        self.voice_page.set_voice_clone_available(clone_available)

        if healthy:
            suffix = f" · Có thể chọn {len(voices)} giọng."
            if model_id:
                suffix += f" · Engine: {model_id}."
            if model_id == "kittentts":
                suffix += (
                    " · 8 preset đã ánh xạ đúng speaker ID. "
                    "VoiceStudio 0.5.6 chạy KittenTTS bằng CPU; nghe thử dùng đoạn ngắn để so giọng nhanh hơn. "
                    "Tốc độ gợi ý 1.10–1.30."
                )
            if clone_available:
                suffix += " · Hỗ trợ clone giọng cục bộ."
            detail = f"{detail}{suffix}"
        self.voice_page.set_tts_health(detail, "good" if healthy else "warn")

    def _begin_voicestudio_autostart(self, original_detail: str) -> bool:
        endpoint = self._sync_voicestudio_backend_endpoint()
        if endpoint:
            self.voice_page.set_tts_health(
                f"Đã tìm thấy VoiceStudio backend tại {endpoint}. Đang tải engine và giọng...",
                "good",
            )
            QTimer.singleShot(0, self.refresh_tts_provider)
            return True

        if self._voicestudio_autostart_active:
            self.voice_page.set_tts_health(
                "Đang khởi động VoiceStudio Local và dò backend loopback (3900 hoặc cổng dự phòng)...",
                "warn",
            )
            return True

        started, start_detail = self.voicestudio_runtime.start()
        if not started:
            self.voice_page.set_tts_health(
                f"{start_detail}\n{original_detail}",
                "bad",
            )
            return False

        self._voicestudio_autostart_active = True
        self._voicestudio_autostart_attempts = 0
        self.voice_page.set_tts_health(
            f"{start_detail}. Đang chờ backend VoiceStudio sẵn sàng...",
            "warn",
        )
        QTimer.singleShot(1500, self._poll_voicestudio_autostart)
        return True

    def _poll_voicestudio_autostart(self):
        if not self._voicestudio_autostart_active:
            return
        if not hasattr(self, "voice_page"):
            self._voicestudio_autostart_active = False
            return
        if self.voice_page.selected_tts_provider_id() != VoiceStudioLocalProvider.PROVIDER_ID:
            self._voicestudio_autostart_active = False
            return

        self._voicestudio_autostart_attempts += 1
        endpoint = self._sync_voicestudio_backend_endpoint()
        if endpoint is None:
            healthy = False
            detail = "Backend VoiceStudio chưa xuất hiện trên cổng loopback đã dò."
        else:
            try:
                healthy, detail = self.tts_service.health_check(VoiceStudioLocalProvider.PROVIDER_ID)
            except Exception as exc:
                healthy = False
                detail = f"{type(exc).__name__}: {exc}"

        if healthy:
            self._voicestudio_autostart_active = False
            self._voicestudio_autostart_attempts = 0
            self.voice_page.set_tts_health(
                "VoiceStudio đã khởi động. Đang tải danh sách giọng...",
                "good",
            )
            self.refresh_tts_provider()
            return

        if self._voicestudio_autostart_attempts >= self._voicestudio_autostart_max_attempts:
            self._voicestudio_autostart_active = False
            self.voice_page.set_tts_engines(())
            self.voice_page.set_tts_voices(())
            self.voice_page.set_voice_clone_available(False)
            self.voice_page.set_tts_health(
                "Đã mở VoiceStudio nhưng backend vẫn chưa sẵn sàng sau khoảng 10 phút. "
                "Hãy kiểm tra màn hình Setup/Model Catalogue trong VoiceStudio; lần chạy đầu có thể đang "
                "chuẩn bị runtime/model. Sau khi VoiceStudio báo sẵn sàng, bấm 'Làm mới giọng'. "
                f"Chi tiết cuối: {detail}",
                "bad",
            )
            return

        elapsed_seconds = int(self._voicestudio_autostart_attempts * 1.5)
        endpoint_text = endpoint or "đang dò 3900 và các cổng dự phòng"
        self.voice_page.set_tts_health(
            f"Đang chờ VoiceStudio Local khởi động · {elapsed_seconds}s · {endpoint_text}",
            "warn",
        )
        QTimer.singleShot(1500, self._poll_voicestudio_autostart)

    def select_clone_reference_audio(self):
        if self.current_project is None:
            QMessageBox.information(self, "Clone giọng", "Hãy tạo hoặc mở dự án trước.")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn audio mẫu để clone giọng",
            str(ROOT),
            "Audio (*.wav *.mp3 *.m4a *.flac *.ogg *.oga *.opus *.aac *.webm);;Tất cả tệp (*.*)",
        )
        if not filename:
            return
        path = Path(filename).resolve()
        self.voice_page.set_clone_reference_path(path)
        if not self.voice_page.clone_name():
            self.voice_page.clone_name_edit.setText(path.stem)
        self.voice_page.set_clone_status(
            "Đã chọn audio mẫu. Khuyến nghị đoạn nói rõ, một người, khoảng 3–10 giây.",
            "good",
        )

    def create_voice_clone(self):
        if self.current_project is None:
            QMessageBox.information(self, "Clone giọng", "Hãy tạo hoặc mở dự án trước.")
            return
        if self.clone_worker is not None and self.clone_worker.isRunning():
            return
        provider_id = self.voice_page.selected_tts_provider_id()
        if provider_id != "voicestudio_local":
            QMessageBox.warning(self, "Clone giọng", "Voice clone hiện chỉ khả dụng với VoiceStudio Local.")
            return
        path = self.voice_page.clone_reference_path()
        if path is None or not path.is_file():
            QMessageBox.warning(self, "Clone giọng", "Hãy chọn một file audio mẫu hợp lệ.")
            return
        name = self.voice_page.clone_name()
        if not name:
            QMessageBox.warning(self, "Clone giọng", "Hãy nhập tên cho giọng clone.")
            return
        if not self.voice_page.clone_permission_confirmed():
            QMessageBox.warning(
                self,
                "Clone giọng",
                "Bạn cần xác nhận mình sở hữu giọng này hoặc đã được phép clone và sử dụng.",
            )
            return

        request = {
            "provider_id": provider_id,
            "name": name,
            "reference_audio": path,
            "ref_text": self.voice_page.clone_transcript(),
            "language": self.voice_page.clone_language(),
            "instruct": "",
        }
        self.voice_page.set_clone_busy(True)
        self.voice_page.set_clone_status("Đang tạo voice clone bằng VoiceStudio Local...", "warn")
        self.voice_page.append_log(
            f"VOICE CLONE bắt đầu · name={name} · audio={path.name} · language={request['language']}"
        )
        worker = VoiceCloneWorker(self.tts_service, request, self)
        self.clone_worker = worker
        worker.succeeded.connect(self._on_voice_clone_success)
        worker.failed.connect(self._on_voice_clone_failed)
        worker.finished.connect(self._on_voice_clone_finished)
        worker.start()

    def _on_voice_clone_success(self, result):
        voice_id = str(getattr(result, "voice_id", "") or "")
        display_name = str(getattr(result, "display_name", voice_id) or voice_id)
        self.voice_page.set_clone_status(
            f"Đã tạo voice clone: {display_name} · profile={voice_id}",
            "good",
        )
        self.voice_page.append_log(f"VOICE CLONE hoàn tất · profile={voice_id} · name={display_name}")

        # Refresh VoiceStudio profiles and automatically select the new clone.
        self.refresh_tts_voices()
        index = self.voice_page.tts_voice_combo.findData(voice_id)
        if index >= 0:
            self.voice_page.tts_voice_combo.setCurrentIndex(index)

        QMessageBox.information(
            self,
            "Clone giọng hoàn tất",
            f"Đã tạo giọng clone '{display_name}'.\n\n"
            "Giọng mới đã được thêm vào danh sách Giọng đọc và có thể dùng ngay để Nghe thử hoặc Tạo giọng đọc.",
        )

    def _on_voice_clone_failed(self, message: str):
        self.voice_page.set_clone_status(f"Clone giọng thất bại: {message}", "bad")
        self.voice_page.append_log(f"VOICE CLONE ERROR: {message}")
        concise = message.strip()
        if len(concise) > 700:
            concise = concise[:700].rstrip() + "…"
        QMessageBox.warning(
            self,
            "Clone giọng",
            "Không thể tạo voice clone bằng VoiceStudio Local.\n\n"
            f"{concise}\n\n"
            "Nếu transcript để trống, hãy bảo đảm VoiceStudio đã cài một ASR local hoặc nhập transcript khớp chính xác với audio mẫu.",
        )

    def _on_voice_clone_finished(self):
        self.voice_page.set_clone_busy(False)
        worker = self.clone_worker
        self.clone_worker = None
        if worker is not None:
            worker.deleteLater()

    def _validate_tts_request(self, *, preview: bool):
        if self.current_project is None or self.current_project_path is None:
            QMessageBox.information(self, "Tạo giọng đọc", "Hãy tạo hoặc mở dự án trước.")
            return None
        if self.tts_worker is not None and self.tts_worker.isRunning():
            return None

        text = self.voice_page.script_text().strip()
        if not text:
            QMessageBox.warning(self, "Tạo giọng đọc", "Hãy nhập kịch bản trước.")
            return None

        if self.voice_page.is_script_dirty() and not preview:
            QMessageBox.information(
                self,
                "Tạo giọng đọc",
                "Kịch bản đang có thay đổi chưa lưu. Hãy bấm 'Lưu kịch bản' trước khi tạo giọng đọc chính thức.",
            )
            return None

        provider_id = self.voice_page.selected_tts_provider_id()
        voice_id = self.voice_page.selected_tts_voice_id()
        if not provider_id or not voice_id:
            QMessageBox.warning(self, "Tạo giọng đọc", "Chưa chọn nhà cung cấp hoặc giọng đọc.")
            return None

        model_id = None
        if provider_id == VoiceStudioLocalProvider.PROVIDER_ID:
            model_id = self.voice_page.selected_tts_engine_id() or "tts-1"

        if preview:
            # KittenTTS in VoiceStudio 0.5.6 is CPU-only. A 600-character
            # preview can create ~30 seconds of speech and makes voice
            # comparison feel unnecessarily slow. Keep Kitten previews short
            # while leaving full-project generation unchanged.
            preview_limit = 220 if model_id == "kittentts" else 600
            preview_text = text[:preview_limit]
            if len(text) > preview_limit:
                split_at = max(preview_text.rfind("."), preview_text.rfind("!"), preview_text.rfind("?"))
                if split_at >= 60:
                    preview_text = preview_text[: split_at + 1]
            text = preview_text

        if preview:
            preview_dir = Path(tempfile.gettempdir()) / "AI_Video_Editor" / "tts_preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            # Short, unique basename.  QtMultimedia supports long paths, but a
            # short basename also keeps compatibility with any Windows audio
            # fallback that may be used on another machine.
            token = f"{time.time_ns() & 0xFFFFFF:06x}"
            output_path = preview_dir / f"pv{token}.wav"
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            asset_target = new_generated_voice_target(
                self.current_project_path.parent,
                provider_id=provider_id,
                model_id=model_id,
                voice_id=voice_id,
            )
            output_path = asset_target.audio_path

        request = {
            "provider_id": provider_id,
            "voice_id": voice_id,
            "text": text,
            "output_path": output_path,
            "speed": self.voice_page.selected_tts_speed(),
            "volume": 1.0,
            "model_id": model_id,
        }
        if not preview:
            request["_asset_target"] = asset_target
        return request

    def preview_tts_voice(self):
        # Selecting/listening to another voice replaces any preview already
        # playing, so voices never overlap.
        self.stop_tts_preview(silent=True)
        request = self._validate_tts_request(preview=True)
        if request is None:
            return
        self._start_tts_worker(request, action="preview")

    @staticmethod
    def _history_token(value: str, fallback: str = "unknown") -> str:
        token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        token = token.strip("._-")
        return (token or fallback)[:48]

    @staticmethod
    def _voice_file_fingerprint(path: Path) -> dict:
        path = Path(path)
        stat = path.stat()
        return {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }

    def _voice_workspace_dir(self) -> Path:
        if self.current_project_path is None:
            raise RuntimeError("Chưa có dự án đang mở.")
        output_dir = self.current_project_path.parent / VOICE_WORKSPACE_DIRNAME
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _voice_history_root(self) -> Path:
        history_root = self._voice_workspace_dir() / VOICE_HISTORY_DIRNAME
        history_root.mkdir(parents=True, exist_ok=True)
        return history_root

    def _active_history_marker_path(self) -> Path:
        return self._voice_workspace_dir() / VOICE_ACTIVE_HISTORY_FILENAME

    def _read_active_history_marker(self) -> dict | None:
        marker_path = self._active_history_marker_path()
        if not marker_path.is_file():
            return None
        try:
            data = json.loads(marker_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _write_active_history_marker(self, run_dir: Path, voice_path: Path):
        marker = {
            "run_dir": str(Path(run_dir).resolve()),
            "voice_path": str(Path(voice_path).resolve()),
            "voice_fingerprint": self._voice_file_fingerprint(voice_path),
            "updated_at": datetime.now().astimezone().isoformat(),
        }
        self._active_history_marker_path().write_text(
            json.dumps(marker, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _active_history_dir_for_voice(self, voice_path: Path) -> Path | None:
        marker = self._read_active_history_marker()
        if not marker:
            return None
        try:
            expected = marker.get("voice_fingerprint")
            current = self._voice_file_fingerprint(voice_path)
            run_dir = Path(str(marker.get("run_dir", "")))
            if expected == current and run_dir.is_dir():
                return run_dir
        except Exception:
            return None
        return None

    def _create_history_run_dir(
        self,
        *,
        provider_id: str,
        voice_id: str,
        model_id: str | None = None,
        prefix: str = "tts",
    ) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        provider_token = self._history_token(provider_id, "provider")
        voice_token = self._history_token(voice_id, "voice")
        model_token = self._history_token(model_id or "", "")
        parts = [stamp, prefix, provider_token]
        if model_token:
            parts.append(model_token)
        parts.append(voice_token)
        base_name = "_".join(parts)
        history_root = self._voice_history_root()
        run_dir = history_root / base_name
        suffix = 1
        while run_dir.exists():
            run_dir = history_root / f"{base_name}_{suffix:02d}"
            suffix += 1
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    def _archive_generated_voice(
        self,
        voice_path: Path,
        *,
        provider_id: str,
        voice_id: str,
        model_id: str | None,
        duration: float,
    ) -> Path:
        voice_path = Path(voice_path)
        if not voice_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy tệp giọng để lưu lịch sử: {voice_path}")

        run_dir = self._create_history_run_dir(
            provider_id=provider_id,
            voice_id=voice_id,
            model_id=model_id,
            prefix="tts",
        )
        archived_voice = run_dir / GENERATED_VOICE_FILENAME
        shutil.copy2(voice_path, archived_voice)

        metadata = {
            "format": "creator_studio_voice_history_m104_5",
            "created_at": datetime.now().astimezone().isoformat(),
            "project_id": str(getattr(self.current_project, "project_id", "") or ""),
            "project_name": str(getattr(self.current_project, "project_name", "") or ""),
            "provider_id": provider_id,
            "model_id": model_id,
            "voice_id": voice_id,
            "language": self.voice_page.selected_language(),
            "speed": self.voice_page.selected_tts_speed(),
            "duration_seconds": float(duration or 0.0),
            "current_voice_path": str(voice_path.resolve()),
            "archived_voice_path": str(archived_voice.resolve()),
            "voice_fingerprint": self._voice_file_fingerprint(voice_path),
        }
        (run_dir / "generation.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_active_history_marker(run_dir, voice_path)
        return run_dir

    def _archive_current_workspace_if_needed(self) -> Path | None:
        """Protect an existing current snapshot before a new TTS overwrites it."""
        if self.current_project_path is None:
            return None
        output_dir = self._voice_workspace_dir()
        voice_path = output_dir / GENERATED_VOICE_FILENAME
        if not voice_path.is_file():
            return None

        active_dir = self._active_history_dir_for_voice(voice_path)
        if active_dir is not None:
            return active_dir

        voice_state = getattr(self.current_project, "voice", None) if self.current_project is not None else None
        provider_id = str(getattr(voice_state, "provider", "") or "existing")
        voice_id = str(getattr(voice_state, "voice_id", "") or "voice")
        run_dir = self._create_history_run_dir(
            provider_id=provider_id,
            voice_id=voice_id,
            model_id=None,
            prefix="snapshot",
        )
        shutil.copy2(voice_path, run_dir / GENERATED_VOICE_FILENAME)

        for filename in ("clean_transcript.srt", VOICE_PIPELINE_RESULT_FILENAME, "voice_scenes.json"):
            source = output_dir / filename
            if source.is_file():
                shutil.copy2(source, run_dir / filename)

        metadata = {
            "format": "creator_studio_voice_history_m104_5",
            "created_at": datetime.now().astimezone().isoformat(),
            "reason": "protect_current_before_new_generation",
            "provider_id": provider_id,
            "voice_id": voice_id,
            "current_voice_path": str(voice_path.resolve()),
            "voice_fingerprint": self._voice_file_fingerprint(voice_path),
        }
        (run_dir / "snapshot.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_active_history_marker(run_dir, voice_path)
        return run_dir

    def generate_tts_voice(self):
        self.stop_tts_preview(silent=True)
        request = self._validate_tts_request(preview=False)
        if request is None:
            return
        self._start_tts_worker(request, action="generate")

    def _start_tts_worker(self, request: dict, *, action: str):
        self._tts_worker_action = action
        worker_request = dict(request)
        self._pending_tts_asset_target = worker_request.pop("_asset_target", None)
        self.voice_page.set_tts_busy(True)
        if action == "preview":
            self.voice_page.set_tts_health("Đang tạo đoạn nghe thử bằng nhà cung cấp đã chọn...", "warn")
        else:
            self.voice_page.set_tts_health("Đang tạo giọng đọc từ toàn bộ kịch bản...", "warn")
            self.voice_page.append_log(
                f"TTS bắt đầu · provider={request['provider_id']} · model={request.get('model_id') or '-'} · voice={request['voice_id']} · speed={request['speed']:.2f}"
            )

        worker = TTSSynthesisWorker(self.tts_service, worker_request, self)
        self.tts_worker = worker
        worker.succeeded.connect(self._on_tts_success)
        worker.failed.connect(self._on_tts_failed)
        worker.finished.connect(self._on_tts_finished)
        worker.start()

    def _on_tts_success(self, result):
        action = self._tts_worker_action
        output_path = Path(getattr(result, "output_path", ""))
        duration = float(getattr(result, "duration_seconds", 0.0) or 0.0)
        provider_id = str(getattr(result, "provider_id", "") or "")
        voice_id = str(getattr(result, "voice_id", "") or "")

        if action == "preview":
            if not output_path.is_file():
                self.voice_page.set_tts_health(
                    "Đã tạo đoạn nghe thử nhưng không tìm thấy tệp WAV tạm.",
                    "bad",
                )
                return
            self.voice_page.set_tts_health(
                f"Đang phát nghe thử trực tiếp · {_format_duration(duration)}",
                "good",
            )
            self._play_tts_preview(output_path)
            return

        if self.current_project is None or self.current_project_path is None:
            return

        target = self._pending_tts_asset_target
        if target is None:
            self.voice_page.set_tts_health(
                "TTS hoàn tất nhưng Creator Studio không còn thông tin Voice Asset đích.",
                "bad",
            )
            if action == "automation_generate":
                self._automation_fail(
                    "voice",
                    "TTS hoàn tất nhưng không còn thông tin Voice Asset đích.",
                )
            return

        try:
            if output_path.resolve() != target.audio_path.resolve():
                if not output_path.is_file():
                    raise FileNotFoundError(output_path)
                target.audio_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output_path, target.audio_path)
                output_path = target.audio_path.resolve()
            else:
                output_path = target.audio_path.resolve()

            finalized_asset = finalize_voice_asset(
                target,
                language=self.voice_page.selected_language(),
                speed=self.voice_page.selected_tts_speed(),
                duration_seconds=duration,
            )
            output_path = finalized_asset.audio_path.resolve()
        except Exception as exc:
            self.voice_page.set_tts_health(
                f"TTS đã trả kết quả nhưng không thể hoàn tất Voice Asset: {exc}",
                "bad",
            )
            self.voice_page.append_log(
                f"VOICE ASSET FINALIZE ERROR: {type(exc).__name__}: {exc}"
            )
            if action == "automation_generate":
                self._automation_fail(
                    "voice",
                    f"Không thể hoàn tất Voice Asset: {type(exc).__name__}: {exc}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Lưu Voice Asset",
                    "Nhà cung cấp TTS đã hoàn tất nhưng Creator Studio không thể lưu Voice Asset.\n\n"
                    f"{type(exc).__name__}: {exc}",
                )
            return

        inputs = [
            item
            for item in (getattr(self.current_project, "inputs", []) or [])
            if getattr(item, "id", None) != VOICE_INPUT_ID
            and getattr(item, "kind", None) != InputKind.VOICE
        ]
        inputs.append(
            InputSource(
                id=VOICE_INPUT_ID,
                kind=InputKind.VOICE,
                reference=str(output_path.resolve()),
            )
        )

        updated_voice = replace(
            self.current_project.voice,
            kind=VoiceKind.GENERATED,
            provider=provider_id,
            language=self.voice_page.selected_language(),
            voice_id=voice_id,
            speed=self.voice_page.selected_tts_speed(),
            status=Status.SUCCEEDED,
            audio_media_id=None,
            alignment_reference=None,
        )
        updated = replace(self.current_project, inputs=inputs, voice=updated_voice)

        try:
            self._persist_project_update(
                updated,
                f"Đã tạo giọng đọc: provider={provider_id} · voice={voice_id}",
            )
        except Exception as exc:
            if action == "automation_generate":
                self._automation_fail(
                    "voice",
                    f"Audio đã được tạo nhưng không thể cập nhật dự án: {type(exc).__name__}: {exc}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Tạo giọng đọc",
                    f"Audio đã được tạo nhưng không thể cập nhật ProjectManifest.\n\n{type(exc).__name__}: {exc}",
                )
            return

        self.voice_page.set_tts_health(
            f"Đã tạo Voice Asset · {_format_duration(duration)} · {voice_id}",
            "good",
        )
        try:
            output_size_mb = output_path.stat().st_size / (1024.0 * 1024.0)
        except Exception:
            output_size_mb = 0.0
        self.voice_page.append_log(f"TTS hoàn tất: {output_path}")
        self.voice_page.append_log(
            f"Voice Asset mới: {finalized_asset.asset_id} · {output_size_mb:.2f} MB"
        )
        self.voice_page.append_log(f"Thời lượng: {_format_duration(duration)}")
        self._pending_tts_asset_target = None
        self.refresh_voice_asset_library()
        self.voice_page.set_process_status(
            "Đã tạo Voice Asset mới và đặt làm giọng hiện tại. Có thể chạy bước chép lời + phụ đề + cảnh.",
            "good",
        )

        if action == "automation_generate" and self.automation_coordinator is not None:
            if not self._automation_cancel_requested:
                try:
                    self.automation_coordinator.voice_completed(
                        filename=output_path.name,
                        duration_seconds=duration,
                    )
                    self._automation_waiting_for_voice_pipeline = True
                    self._automation_apply_state()
                except Exception as exc:
                    self._automation_fail(
                        "voice",
                        f"Không thể chuyển sang bước phân tích nội dung: {type(exc).__name__}: {exc}",
                    )

    def _play_tts_preview(self, output_path: Path):
        try:
            self.audio_preview_controller.play(output_path)
        except Exception as exc:
            try:
                Path(output_path).unlink(missing_ok=True)
            except Exception:
                pass
            self._on_tts_preview_playback_failed(
                f"{type(exc).__name__}: {exc}"
            )
            return

        self.voice_page.set_preview_playback_state(True, False)
        self.voice_page.set_tts_health(
            "Đang phát nghe thử trực tiếp. Có thể Tạm dừng, Dừng, hoặc chọn giọng khác rồi bấm Nghe thử.",
            "good",
        )

    def toggle_tts_preview_pause(self):
        if not self.audio_preview_controller.is_active:
            return
        self.audio_preview_controller.toggle_pause()

    def stop_tts_preview(self, checked=False, *, silent: bool = False):
        was_active = self.audio_preview_controller.is_active
        self.audio_preview_controller.stop(delete_temp=True)
        self.voice_page.set_preview_playback_state(False, False)
        if was_active and not silent:
            self.voice_page.set_tts_health(
                "Đã dừng đoạn nghe thử.",
                "idle",
            )

    def _on_tts_preview_state_changed(self, active: bool, paused: bool):
        self.voice_page.set_preview_playback_state(active, paused)
        if not active:
            return
        if paused:
            self.voice_page.set_tts_health(
                "Đã tạm dừng đoạn nghe thử. Bấm 'Tiếp tục' để nghe tiếp.",
                "warn",
            )
        else:
            self.voice_page.set_tts_health(
                "Đang phát nghe thử trực tiếp.",
                "good",
            )

    def _on_tts_preview_playback_success(self):
        self.voice_page.set_preview_playback_state(False, False)
        self.voice_page.set_tts_health(
            "Đã phát xong đoạn nghe thử trực tiếp. Tệp preview tạm đã được xóa.",
            "good",
        )

    def _on_tts_preview_playback_failed(self, message: str):
        self.voice_page.set_preview_playback_state(False, False)
        self.voice_page.set_tts_health(
            f"Không thể phát nghe thử trực tiếp: {message}",
            "bad",
        )
        self.voice_page.append_log(f"PREVIEW PLAYBACK ERROR: {message}")

    def _on_tts_failed(self, message: str):
        action = self._tts_worker_action
        target = self._pending_tts_asset_target
        self._pending_tts_asset_target = None
        if target is not None:
            try:
                target.audio_path.unlink(missing_ok=True)
                target.metadata_path.unlink(missing_ok=True)
            except Exception:
                pass
        self.voice_page.set_tts_health(f"TTS thất bại: {message}", "bad")
        self.voice_page.append_log(f"TTS ERROR: {message}")
        concise = message.strip()
        if len(concise) > 700:
            concise = concise[:700].rstrip() + "…"

        if action == "automation_generate":
            self._automation_fail("voice", f"Không thể tạo giọng đọc: {concise}")
            return

        QMessageBox.warning(
            self,
            "Tạo giọng đọc",
            "Không thể tạo giọng đọc bằng nhà cung cấp TTS đã chọn.\n\n"
            f"{concise}\n\n"
            "Chi tiết đầy đủ đã được ghi trong nhật ký xử lý.",
        )

    def _on_tts_finished(self):
        action = self._tts_worker_action
        self.voice_page.set_tts_busy(False)
        worker = self.tts_worker
        self.tts_worker = None
        self._tts_worker_action = None
        if worker is not None:
            worker.deleteLater()

        if (
            action == "automation_generate"
            and self._automation_waiting_for_voice_pipeline
            and not self._automation_cancel_requested
        ):
            QTimer.singleShot(0, self._automation_start_voice_pipeline)

    def run_voice_pipeline(self):
        if self.current_project is None or self.current_project_path is None:
            QMessageBox.information(self, "Xử lý giọng đọc", "Hãy tạo hoặc mở dự án trước.")
            return
        if self.voice_pipeline_worker is not None and self.voice_pipeline_worker.isRunning():
            return

        voice_path = self._voice_input_path()
        if voice_path is None or not voice_path.is_file():
            QMessageBox.warning(self, "Xử lý giọng đọc", "Hãy chọn một tệp giọng đọc hợp lệ trước.")
            return

        record = find_voice_asset_by_path(self.current_project_path.parent, voice_path)
        asset_id = record.asset_id if record is not None else f"legacy_{storage_safe_slug(voice_path.stem, 'voice')}"
        try:
            output_dir = create_voice_work_run(self.current_project_path.parent, asset_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Xử lý giọng đọc",
                f"Không thể tạo thư mục xử lý riêng cho Voice Asset.\n\n{type(exc).__name__}: {exc}",
            )
            return

        srt_path = output_dir / "clean_transcript.srt"

        self.voice_page.process_log.clear()
        self.voice_page.append_log("Bắt đầu VoicePipeline trong luồng nền.")
        self.voice_page.append_log(f"Giọng đọc: {voice_path}")
        self.voice_page.append_log(f"Thư mục run: {output_dir}")
        self.voice_page.append_log(f"Phụ đề đầu ra: {srt_path}")
        self.voice_page.set_process_status("Đang chép lời và xây dựng cảnh dẫn xuất...", "warn")
        self.voice_page.set_busy(True)

        worker = VoicePipelineWorker(voice_path, srt_path, self)
        self.voice_pipeline_worker = worker
        worker.succeeded.connect(
            lambda result, vp=voice_path, sp=srt_path, od=output_dir: self._on_voice_pipeline_success(
                result, vp, sp, od
            )
        )
        worker.failed.connect(self._on_voice_pipeline_failed)
        worker.finished.connect(self._on_voice_pipeline_thread_finished)
        worker.start()

    def _on_voice_pipeline_success(self, result, voice_path: Path, srt_path: Path, output_dir: Path):
        if self.current_project_path is None:
            return
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_result = _json_safe(result)
        summary = {}
        if isinstance(safe_result, dict):
            duration = safe_result.get("audio_duration", safe_result.get("duration"))
            scenes = safe_result.get("scenes", [])
            summary = {
                "duration": duration,
                "scenes": len(scenes) if isinstance(scenes, list) else safe_result.get("scene_count", 0),
                "language": safe_result.get("language"),
                "srt": str(srt_path),
            }

        payload = {
            "format": "creator_studio_voice_pipeline_m105_v1",
            "source_voice": str(voice_path),
            "srt": str(srt_path),
            "summary": summary,
            "result": safe_result,
        }
        result_path = output_dir / VOICE_PIPELINE_RESULT_FILENAME
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        if isinstance(safe_result, dict) and isinstance(safe_result.get("scenes"), list):
            (output_dir / "voice_scenes.json").write_text(
                json.dumps(safe_result.get("scenes"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        duration_text = _format_duration(summary.get("duration"))
        scene_count = summary.get("scenes", 0)
        self.voice_page.append_log("VoicePipeline hoàn tất thành công.")
        self.voice_page.append_log(f"Thời lượng: {duration_text}")
        self.voice_page.append_log(f"Cảnh dẫn xuất: {scene_count}")
        self.voice_page.append_log(f"Kết quả: {result_path}")
        if voice_path.is_file():
            self.voice_page.append_log(f"Voice Asset nguồn vẫn được giữ nguyên: {voice_path}")

        self.voice_page.set_process_status(
            f"Hoàn tất · Thời lượng {duration_text} · {scene_count} cảnh · Run riêng, không ghi đè run cũ.",
            "good",
        )
        if hasattr(self, "scene_page"):
            self.refresh_scene_asset_assignment()

        if self.automation_coordinator is not None and not self._automation_cancel_requested:
            try:
                self.automation_coordinator.voice_pipeline_completed(
                    scene_count=int(scene_count or 0),
                    duration_seconds=float(summary.get("duration") or 0.0),
                    run_name=output_dir.name,
                )
                self._automation_apply_state()
                scenes_path = output_dir / "voice_scenes.json"
                QTimer.singleShot(
                    0,
                    lambda path=scenes_path: self._automation_start_media_query_planning(path),
                )
            except Exception as exc:
                self._automation_fail(
                    "scene_analysis",
                    f"VoicePipeline hoàn tất nhưng không thể cập nhật trạng thái tự động: {type(exc).__name__}: {exc}",
                )

    def _on_voice_pipeline_failed(self, message: str):
        self.voice_page.append_log("VoicePipeline thất bại.")
        self.voice_page.append_log(message)
        self.voice_page.set_process_status("Xử lý giọng đọc thất bại. Xem nhật ký bên dưới.", "bad")
        if self.automation_coordinator is not None and self.automation_coordinator.status == AutomationRunStatus.RUNNING:
            self._automation_fail("voice_timing", f"Không thể phân tích nội dung: {message}")
            return
        QMessageBox.warning(
            self,
            "Xử lý giọng đọc",
            "VoicePipeline không hoàn tất.\n\n" + message,
        )

    def _on_voice_pipeline_thread_finished(self):
        self.voice_page.set_busy(False)
        worker = self.voice_pipeline_worker
        self.voice_pipeline_worker = None
        self.media_query_worker = None
        if worker is not None:
            worker.deleteLater()

    def open_voice_output_folder(self):
        if self.current_project_path is None:
            QMessageBox.information(self, "Xử lý giọng đọc", "Hãy tạo hoặc mở dự án trước.")
            return
        try:
            output_dir = voice_work_root(self.current_project_path.parent)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Xử lý giọng đọc",
                f"Không thể tạo thư mục work/voice.\n\n{type(exc).__name__}: {exc}",
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir))):
            QMessageBox.warning(self, "Xử lý giọng đọc", f"Windows không thể mở thư mục:\n\n{output_dir}")

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

    def open_voice_history_folder(self):
        if self.current_project_path is None:
            QMessageBox.information(
                self,
                "Lịch sử giọng đọc",
                "Hãy tạo hoặc mở dự án trước.",
            )
            return

        history_root = (
            self.current_project_path.parent
            / VOICE_WORKSPACE_DIRNAME
            / VOICE_HISTORY_DIRNAME
        )
        try:
            history_root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Lịch sử giọng đọc",
                f"Không thể tạo thư mục lịch sử.\n\n{type(exc).__name__}: {exc}",
            )
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(history_root))):
            QMessageBox.warning(
                self,
                "Lịch sử giọng đọc",
                f"Windows không thể mở thư mục:\n\n{history_root}",
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
                "Chẩn đoán nhà cung cấp",
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
            "Đang chạy",
            "warn",
            "Hệ thống chẩn đoán M100 đang chạy.",
        )

    def _on_provider_diagnostics_state_changed(self, state):
        self._sync_provider_diagnostics_status(state)
        QTimer.singleShot(0, lambda: _translate_known_ui_texts(self.provider_diagnostics_view))

    def _on_provider_diagnostics_fatal(self):
        self._set_provider_status(
            "Lỗi nội bộ",
            "bad",
            "Chẩn đoán gặp lỗi nội bộ đã được hệ thống bảo vệ.",
        )

    def _on_provider_diagnostics_finished(self, state):
        self._sync_provider_diagnostics_status(state)
        QTimer.singleShot(0, lambda: _translate_known_ui_texts(self.provider_diagnostics_view))

        if not self._provider_diagnostics_close_pending:
            return

        self._provider_diagnostics_close_pending = False
        QTimer.singleShot(0, self.close)

    def _sync_provider_diagnostics_status(self, state):
        phase = getattr(getattr(state, "phase", None), "name", "IDLE")
        view_model = getattr(state, "view_model", None)

        if phase == "RUNNING":
            self._set_provider_status(
                "Đang chạy",
                "warn",
                "Đang kiểm tra trạng thái sẵn sàng và kết nối của KIE AI.",
            )
            return

        if phase == "COMPLETED":
            is_ready = bool(getattr(view_model, "is_ready", False))

            if is_ready:
                self._set_provider_status(
                    "Sẵn sàng",
                    "good",
                    "Chẩn đoán KIE AI đã hoàn tất thành công.",
                )
            else:
                status_text = getattr(view_model, "status_text", "Cần kiểm tra")
                self._set_provider_status(
                    status_text,
                    "warn",
                    "Chẩn đoán đã hoàn tất; hãy xem kết quả trên trang Chẩn đoán.",
                )
            return

        if phase == "CANCELLED":
            self._set_provider_status(
                "Đã hủy",
                "warn",
                "Lần chẩn đoán gần nhất đã bị hủy.",
            )
            return

        if phase == "FAILED":
            self._set_provider_status(
                "Thất bại",
                "bad",
                "Chẩn đoán nhà cung cấp không hoàn tất thành công.",
            )
            return

        self._set_provider_status(
            "Sẵn sàng chạy",
            "idle",
            "Hệ thống chẩn đoán M100 đã được kết nối.",
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
                f"Chẩn đoán nhà cung cấp: {text}"
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
                "Chẩn đoán nhà cung cấp đang chạy",
                (
                    "Hãy chờ chẩn đoán nhà cung cấp kết thúc "
                    "trước khi thay đổi API Key."
                ),
            )
            return

        dialog = APIKeysDialog(
            manager=self.api_manager,
            parent=self,
        )
        dialog.setStyleSheet(API_DIALOG_STYLE)
        dialog.setWindowTitle("API Key & Nhà cung cấp")
        _translate_known_ui_texts(dialog)
        dialog.exec()

        self._set_provider_status(
            "Sẵn sàng chạy",
            "idle",
            "Cấu hình API đã được cập nhật. Hãy chạy chẩn đoán lại để kiểm tra.",
        )

    def closeEvent(self, event):
        if self.audio_preview_controller.is_active:
            self.audio_preview_controller.stop(delete_temp=True)

        if self.clone_worker is not None and self.clone_worker.isRunning():
            QMessageBox.information(
                self,
                "Đang clone giọng",
                "VoiceStudio đang tạo voice clone. Hãy chờ quá trình hoàn tất trước khi đóng Creator Studio.",
            )
            event.ignore()
            return

        if self.tts_worker is not None and self.tts_worker.isRunning():
            QMessageBox.information(
                self,
                "TTS đang chạy",
                "TTS đang tạo giọng đọc. Hãy chờ quá trình hoàn tất trước khi đóng Creator Studio.",
            )
            event.ignore()
            return

        try:
            self._save_ui_state()
        except Exception:
            pass

        if self.voice_pipeline_worker is not None and self.voice_pipeline_worker.isRunning():
            QMessageBox.information(
                self,
                "Đang xử lý giọng đọc",
                "VoicePipeline đang chạy. Hãy chờ quá trình này kết thúc trước khi đóng Creator Studio.",
            )
            event.ignore()
            return

        if self.provider_diagnostics_binder.is_running:
            if self._provider_diagnostics_close_pending:
                event.ignore()
                return

            answer = QMessageBox.question(
                self,
                "Chẩn đoán nhà cung cấp đang chạy",
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

        if key in {item.key for item in ADVANCED_NAV_ITEMS}:
            self._toggle_advanced_navigation(force=True)

        if key == "scenes" and hasattr(self, "scene_page"):
            self.refresh_scene_asset_assignment()

        self.pages.setCurrentIndex(self.page_indexes[key])

        selected_label = key
        for item in NAV_ITEMS:
            button = self.nav_buttons.get(item.key)
            if button is None:
                continue
            is_selected = item.key == key
            button.setProperty("selected", is_selected)
            button.style().unpolish(button)
            button.style().polish(button)
            if is_selected:
                selected_label = item.label

        if key == "dashboard":
            selected_label = "Tổng quan kỹ thuật"

        self.top_title.setText(selected_label)
        subtitles = {
            "automation": "Quy trình tự động từ kịch bản đến video hoàn chỉnh",
            "project": "Tạo, mở và quản lý dự án",
            "settings": "Thiết lập ứng dụng và nhà cung cấp",
            "voice": "Công cụ nâng cao cho kịch bản và giọng đọc",
            "scenes": "Công cụ nâng cao cho cảnh và tư liệu được gán",
            "media": "Media Asset Library của dự án",
            "vision": "Thiết lập AI hình ảnh",
            "timeline": "Kiểm tra và chỉnh sửa timeline",
            "export": "Thiết lập xuất video thủ công",
            "diagnostics": "Kiểm tra trạng thái provider và runtime",
        }
        self.top_subtitle.setText(subtitles.get(key, "Không gian làm việc Creator Studio"))


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
