from __future__ import annotations

import sys
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "AI Video Editor"
APP_SUBTITLE = "Creator Studio"


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    short: str


NAV_ITEMS = [
    NavItem("dashboard", "Dashboard", "D"),
    NavItem("project", "Project", "P"),
    NavItem("voice", "Voice & Script", "V"),
    NavItem("scenes", "Scenes", "S"),
    NavItem("media", "Media Search", "M"),
    NavItem("vision", "AI Vision", "AI"),
    NavItem("timeline", "Timeline", "T"),
    NavItem("export", "Export", "E"),
    NavItem("diagnostics", "Diagnostics", "DX"),
    NavItem("settings", "Settings", "ST"),
]


APP_STYLE = """
QMainWindow, QWidget {
    background: #0b0f14;
    color: #e8eef6;
    font-family: "Segoe UI";
    font-size: 13px;
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

QFrame.card {
    background: #121923;
    border: 1px solid #222d3a;
    border-radius: 12px;
}

QFrame.card:hover {
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

QPushButton.navButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #9aa9bc;
    text-align: left;
    padding: 11px 12px;
    font-size: 13px;
}

QPushButton.navButton:hover {
    background: #161e29;
    color: #eef4fb;
}

QPushButton.navButton[selected="true"] {
    background: #17263a;
    color: #dcecff;
    border-left: 3px solid #5da9ff;
    padding-left: 9px;
    font-weight: 600;
}

QPushButton.primaryButton {
    background: #2d7ff9;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
}

QPushButton.primaryButton:hover {
    background: #3d8cff;
}

QPushButton.secondaryButton {
    background: #151d27;
    color: #d9e4f0;
    border: 1px solid #2a3544;
    border-radius: 8px;
    padding: 8px 14px;
}

QPushButton.secondaryButton:hover {
    background: #1b2532;
    border: 1px solid #3a4a60;
}

QPushButton.projectButton {
    background: #121923;
    color: #d8e2ef;
    border: 1px solid #273242;
    border-radius: 8px;
    padding: 8px 12px;
}

QPushButton.projectButton:hover {
    background: #18212d;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}
"""


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

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")

        hint_label = QLabel(hint)
        hint_label.setObjectName("metricHint")
        hint_label.setWordWrap(True)

        if status == "good":
            value_label.setStyleSheet("color: #5dd39e;")
        elif status == "warn":
            value_label.setStyleSheet("color: #f5bd60;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)
        layout.addStretch(1)


class WorkflowRow(QWidget):
    def __init__(
        self,
        name: str,
        detail: str,
        status_text: str,
        status_kind: str,
    ):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)

        name_label = QLabel(name)
        name_label.setStyleSheet(
            "font-weight: 600; color: #e6edf6;"
        )

        detail_label = QLabel(detail)
        detail_label.setObjectName("muted")

        status_label = QLabel(status_text)
        status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        if status_kind == "good":
            status_label.setObjectName("statusGood")
        elif status_kind == "warn":
            status_label.setObjectName("statusWarn")
        else:
            status_label.setObjectName("statusIdle")

        left.addWidget(name_label)
        left.addWidget(detail_label)

        layout.addLayout(left, 1)
        layout.addWidget(status_label)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            28,
            24,
            28,
            28,
        )
        content_layout.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(12)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Overview of the current video production workflow."
        )
        subtitle.setObjectName("pageSubtitle")

        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        continue_button = QPushButton(
            "Continue Project"
        )
        continue_button.setProperty(
            "class",
            "primaryButton",
        )
        continue_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        continue_button.setMinimumHeight(38)

        header.addLayout(
            header_text,
            1,
        )
        header.addWidget(
            continue_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        content_layout.addLayout(
            header
        )

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        metrics.setVerticalSpacing(14)

        metrics.addWidget(
            MetricCard(
                "Voice",
                "00:00",
                "No voice file loaded",
            ),
            0,
            0,
        )

        metrics.addWidget(
            MetricCard(
                "Scenes",
                "0",
                "No scenes generated yet",
            ),
            0,
            1,
        )

        metrics.addWidget(
            MetricCard(
                "Media",
                "0 / 0",
                "Scene coverage",
            ),
            0,
            2,
        )

        metrics.addWidget(
            MetricCard(
                "Export",
                "Not ready",
                "Timeline has not been built",
                "warn",
            ),
            0,
            3,
        )

        for column in range(4):
            metrics.setColumnStretch(
                column,
                1,
            )

        content_layout.addLayout(
            metrics
        )

        lower = QGridLayout()

        lower.setHorizontalSpacing(14)
        lower.setVerticalSpacing(14)

        lower.setColumnStretch(
            0,
            3,
        )

        lower.setColumnStretch(
            1,
            2,
        )

        workflow_card = Card()

        workflow_layout = QVBoxLayout(
            workflow_card
        )

        workflow_layout.setContentsMargins(
            18,
            16,
            18,
            18,
        )

        workflow_layout.setSpacing(4)

        workflow_title = QLabel(
            "Production workflow"
        )

        workflow_title.setObjectName(
            "sectionTitle"
        )

        workflow_sub = QLabel(
            "Each module will be connected to the "
            "existing engine in later steps."
        )

        workflow_sub.setObjectName(
            "muted"
        )

        workflow_sub.setWordWrap(
            True
        )

        workflow_layout.addWidget(
            workflow_title
        )

        workflow_layout.addWidget(
            workflow_sub
        )

        workflow_layout.addSpacing(6)

        rows = [
            (
                "Project",
                "Create or open a production project",
                "Not started",
                "idle",
            ),
            (
                "Voice & Script",
                "Import voice, transcript and script",
                "Waiting",
                "idle",
            ),
            (
                "Scenes",
                "Generate and review scene plan",
                "Waiting",
                "idle",
            ),
            (
                "Media Search",
                "Find and assign stock/local media",
                "Waiting",
                "idle",
            ),
            (
                "Timeline",
                "Synchronize media with narration",
                "Waiting",
                "idle",
            ),
            (
                "Export",
                "Render the final video",
                "Waiting",
                "idle",
            ),
        ]

        for index, row in enumerate(
            rows
        ):
            workflow_layout.addWidget(
                WorkflowRow(
                    *row
                )
            )

            if index < len(rows) - 1:

                divider = QFrame()

                divider.setFrameShape(
                    QFrame.Shape.HLine
                )

                divider.setStyleSheet(
                    "color: #202b38;"
                )

                workflow_layout.addWidget(
                    divider
                )

        system_card = Card()

        system_layout = QVBoxLayout(
            system_card
        )

        system_layout.setContentsMargins(
            18,
            16,
            18,
            18,
        )

        system_layout.setSpacing(12)

        system_title = QLabel(
            "System status"
        )

        system_title.setObjectName(
            "sectionTitle"
        )

        system_sub = QLabel(
            "UI shell only. Real diagnostics will "
            "be connected after the layout is approved."
        )

        system_sub.setObjectName(
            "muted"
        )

        system_sub.setWordWrap(
            True
        )

        system_layout.addWidget(
            system_title
        )

        system_layout.addWidget(
            system_sub
        )

        system_layout.addSpacing(6)

        system_layout.addWidget(
            WorkflowRow(
                "Application UI",
                "Creator Studio shell",
                "Ready",
                "good",
            )
        )

        system_layout.addWidget(
            WorkflowRow(
                "Provider diagnostics",
                "Existing M100 integration",
                "Not connected",
                "warn",
            )
        )

        system_layout.addWidget(
            WorkflowRow(
                "Pipeline",
                "Existing production engine",
                "Untouched",
                "good",
            )
        )

        system_layout.addStretch(1)

        diagnostics_button = QPushButton(
            "Open Diagnostics"
        )

        diagnostics_button.setProperty(
            "class",
            "secondaryButton",
        )

        diagnostics_button.setMinimumHeight(
            36
        )

        diagnostics_button.clicked.connect(
            lambda:
            self.window().navigate_to(
                "diagnostics"
            )
            if hasattr(
                self.window(),
                "navigate_to",
            )
            else None
        )

        system_layout.addWidget(
            diagnostics_button
        )

        lower.addWidget(
            workflow_card,
            0,
            0,
        )

        lower.addWidget(
            system_card,
            0,
            1,
        )

        content_layout.addLayout(
            lower
        )

        content_layout.addStretch(1)

        scroll.setWidget(
            content
        )

        root.addWidget(
            scroll
        )


class ModulePage(QWidget):

    def __init__(
        self,
        title: str,
        subtitle: str,
        primary_title: str,
        primary_text: str,
        items: list[tuple[str, str]],
        button_text: str | None = None,
    ):

        super().__init__()

        root = QVBoxLayout(self)

        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        content = QWidget()

        layout = QVBoxLayout(
            content
        )

        layout.setContentsMargins(
            28,
            24,
            28,
            28,
        )

        layout.setSpacing(18)

        title_label = QLabel(
            title
        )

        title_label.setObjectName(
            "pageTitle"
        )

        subtitle_label = QLabel(
            subtitle
        )

        subtitle_label.setObjectName(
            "pageSubtitle"
        )

        subtitle_label.setWordWrap(
            True
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            subtitle_label
        )

        card = Card()

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            20,
            18,
            20,
            20,
        )

        card_layout.setSpacing(12)

        card_title = QLabel(
            primary_title
        )

        card_title.setObjectName(
            "sectionTitle"
        )

        card_text = QLabel(
            primary_text
        )

        card_text.setObjectName(
            "muted"
        )

        card_text.setWordWrap(
            True
        )

        card_layout.addWidget(
            card_title
        )

        card_layout.addWidget(
            card_text
        )

        card_layout.addSpacing(4)

        for (
            item_title,
            item_text,
        ) in items:

            row = QFrame()

            row.setStyleSheet(
                "QFrame {"
                "background: #0f151d;"
                "border: 1px solid #202a36;"
                "border-radius: 8px;"
                "}"
            )

            row_layout = QVBoxLayout(
                row
            )

            row_layout.setContentsMargins(
                14,
                12,
                14,
                12,
            )

            row_layout.setSpacing(3)

            item_title_label = QLabel(
                item_title
            )

            item_title_label.setStyleSheet(
                "font-weight: 600;"
                "color: #e7eef7;"
                "border: none;"
            )

            item_text_label = QLabel(
                item_text
            )

            item_text_label.setWordWrap(
                True
            )

            item_text_label.setStyleSheet(
                "color: #7e8da3;"
                "border: none;"
            )

            row_layout.addWidget(
                item_title_label
            )

            row_layout.addWidget(
                item_text_label
            )

            card_layout.addWidget(
                row
            )

        if button_text:

            card_layout.addSpacing(4)

            button = QPushButton(
                button_text
            )

            button.setProperty(
                "class",
                "primaryButton",
            )

            button.setMinimumHeight(
                38
            )

            button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )

            card_layout.addWidget(
                button,
                0,
                Qt.AlignmentFlag.AlignLeft,
            )

        layout.addWidget(
            card
        )

        layout.addStretch(1)

        scroll.setWidget(
            content
        )

        root.addWidget(
            scroll
        )


class CreatorStudioWindow(
    QMainWindow
):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            f"{APP_NAME} - {APP_SUBTITLE}"
        )

        self.resize(
            1400,
            880,
        )

        self.setMinimumSize(
            1120,
            720,
        )

        self.nav_buttons = {}

        self.page_indexes = {}

        self._build_ui()

        self.navigate_to(
            "dashboard"
        )


    def _build_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        shell = QHBoxLayout(
            central
        )

        shell.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        shell.setSpacing(0)

        sidebar = (
            self._build_sidebar()
        )

        shell.addWidget(
            sidebar
        )

        right = QWidget()

        right_layout = QVBoxLayout(
            right
        )

        right_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        right_layout.setSpacing(0)

        topbar = (
            self._build_topbar()
        )

        right_layout.addWidget(
            topbar
        )

        self.pages = (
            QStackedWidget()
        )

        right_layout.addWidget(
            self.pages,
            1,
        )

        self._register_pages()

        footer = (
            self._build_footer()
        )

        right_layout.addWidget(
            footer
        )

        shell.addWidget(
            right,
            1,
        )


    def _build_sidebar(
        self
    ):

        sidebar = QFrame()

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            224
        )

        layout = QVBoxLayout(
            sidebar
        )

        layout.setContentsMargins(
            14,
            18,
            14,
            16,
        )

        layout.setSpacing(6)

        brand_row = (
            QHBoxLayout()
        )

        brand_row.setSpacing(10)

        logo = QLabel(
            "AI"
        )

        logo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        logo.setFixedSize(
            40,
            40,
        )

        logo.setStyleSheet(
            "background: #2d7ff9;"
            "color: white;"
            "border-radius: 10px;"
            "font-size: 14px;"
            "font-weight: 800;"
        )

        brand_text = (
            QVBoxLayout()
        )

        brand_text.setSpacing(0)

        brand = QLabel(
            APP_NAME
        )

        brand.setObjectName(
            "brand"
        )

        brand_sub = QLabel(
            APP_SUBTITLE.upper()
        )

        brand_sub.setObjectName(
            "brandSub"
        )

        brand_text.addWidget(
            brand
        )

        brand_text.addWidget(
            brand_sub
        )

        brand_row.addWidget(
            logo
        )

        brand_row.addLayout(
            brand_text,
            1,
        )

        layout.addLayout(
            brand_row
        )

        layout.addSpacing(16)

        workspace = QLabel(
            "WORKSPACE"
        )

        workspace.setObjectName(
            "brandSub"
        )

        workspace.setContentsMargins(
            10,
            0,
            0,
            3,
        )

        layout.addWidget(
            workspace
        )

        for item in NAV_ITEMS:

            button = QPushButton(
                f"  {item.label}"
            )

            button.setProperty(
                "class",
                "navButton",
            )

            button.setProperty(
                "selected",
                False,
            )

            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            button.setMinimumHeight(
                40
            )

            button.clicked.connect(
                lambda checked=False,
                key=item.key:
                self.navigate_to(
                    key
                )
            )

            self.nav_buttons[
                item.key
            ] = button

            layout.addWidget(
                button
            )

        layout.addStretch(1)

        version = QLabel(
            "UI prototype · M101"
        )

        version.setObjectName(
            "brandSub"
        )

        version.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            version
        )

        return sidebar


    def _build_topbar(
        self
    ):

        topbar = QFrame()

        topbar.setObjectName(
            "topbar"
        )

        topbar.setFixedHeight(
            66
        )

        layout = QHBoxLayout(
            topbar
        )

        layout.setContentsMargins(
            24,
            0,
            24,
            0,
        )

        layout.setSpacing(12)

        title_box = QVBoxLayout()

        title_box.setSpacing(1)

        self.top_title = QLabel(
            "Dashboard"
        )

        self.top_title.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 700;"
            "color: #eef4fb;"
        )

        self.top_subtitle = QLabel(
            "Creator Studio workspace"
        )

        self.top_subtitle.setObjectName(
            "brandSub"
        )

        title_box.addWidget(
            self.top_title
        )

        title_box.addWidget(
            self.top_subtitle
        )

        layout.addLayout(
            title_box
        )

        layout.addStretch(1)

        project_button = QPushButton(
            "Project: No project loaded"
        )

        project_button.setProperty(
            "class",
            "projectButton",
        )

        project_button.setMinimumHeight(
            36
        )

        project_button.clicked.connect(
            lambda:
            self.navigate_to(
                "project"
            )
        )

        settings_button = QPushButton(
            "Settings"
        )

        settings_button.setProperty(
            "class",
            "secondaryButton",
        )

        settings_button.setMinimumHeight(
            36
        )

        settings_button.clicked.connect(
            lambda:
            self.navigate_to(
                "settings"
            )
        )

        layout.addWidget(
            project_button
        )

        layout.addWidget(
            settings_button
        )

        return topbar


    def _build_footer(
        self
    ):

        footer = QFrame()

        footer.setObjectName(
            "footer"
        )

        footer.setFixedHeight(
            34
        )

        layout = QHBoxLayout(
            footer
        )

        layout.setContentsMargins(
            18,
            0,
            18,
            0,
        )

        ui_status = QLabel(
            "● UI Ready"
        )

        ui_status.setObjectName(
            "statusGood"
        )

        engine_status = QLabel(
            "Engine: untouched"
        )

        engine_status.setObjectName(
            "muted"
        )

        provider_status = QLabel(
            "Provider diagnostics: pending connection"
        )

        provider_status.setObjectName(
            "muted"
        )

        layout.addWidget(
            ui_status
        )

        layout.addSpacing(14)

        layout.addWidget(
            engine_status
        )

        layout.addStretch(1)

        layout.addWidget(
            provider_status
        )

        return footer


    def _register_page(
        self,
        key,
        page,
    ):

        index = (
            self.pages.addWidget(
                page
            )
        )

        self.page_indexes[
            key
        ] = index


    def _register_pages(
        self
    ):

        self._register_page(
            "dashboard",
            DashboardPage(),
        )

        self._register_page(
            "project",
            ModulePage(
                "Project",
                "Create, open and manage one video "
                "production as a single project.",
                "Project workspace",
                "This page will become the source "
                "of truth for project paths, assets "
                "and saved state.",
                [
                    (
                        "Project file",
                        "project.json and persistent "
                        "project metadata.",
                    ),
                    (
                        "Input assets",
                        "Voice, script, subtitle and "
                        "local media references.",
                    ),
                    (
                        "Output location",
                        "Render folder, cache and "
                        "export files.",
                    ),
                ],
                "Create New Project",
            ),
        )

        self._register_page(
            "voice",
            ModulePage(
                "Voice & Script",
                "Prepare narration, transcript and "
                "script before scene generation.",
                "Narration workspace",
                "The existing transcription and "
                "content-ingest modules will be "
                "connected here.",
                [
                    (
                        "Voice",
                        "Load and preview narration audio.",
                    ),
                    (
                        "Transcript",
                        "Generate or import timestamped "
                        "transcription.",
                    ),
                    (
                        "Script",
                        "Review the text used for "
                        "scene planning.",
                    ),
                ],
                "Import Voice",
            ),
        )

        self._register_page(
            "scenes",
            ModulePage(
                "Scenes",
                "Review every generated scene, timing, "
                "dialogue, search keyword and media "
                "assignment.",
                "Scene planner",
                "This page will replace raw JSON "
                "inspection with a visual scene table "
                "and detail panel.",
                [
                    (
                        "Scene table",
                        "Time range, dialogue, duration, "
                        "keyword and media coverage.",
                    ),
                    (
                        "Scene detail",
                        "Context, mood, shot type and "
                        "AI-generated search terms.",
                    ),
                    (
                        "Manual control",
                        "Reanalyze one scene without "
                        "rerunning the whole project.",
                    ),
                ],
                "Generate Scenes",
            ),
        )

        self._register_page(
            "media",
            ModulePage(
                "Media Search",
                "Search stock providers and local files, "
                "then assign the best result to each scene.",
                "Media browser",
                "Pexels, Pixabay and later providers "
                "can share one scene-oriented search "
                "workspace.",
                [
                    (
                        "Provider filters",
                        "Enable or disable available "
                        "media providers.",
                    ),
                    (
                        "Preview grid",
                        "Images and videos displayed "
                        "visually before selection.",
                    ),
                    (
                        "Scene assignment",
                        "Attach selected media directly "
                        "to the current scene.",
                    ),
                ],
                "Search Media",
            ),
        )

        self._register_page(
            "vision",
            ModulePage(
                "AI Vision",
                "Configure and inspect vision/provider "
                "operations used by the production pipeline.",
                "Vision workspace",
                "Provider, model, payload bounds and "
                "request execution will be surfaced here.",
                [
                    (
                        "Provider",
                        "Select the configured AI "
                        "provider and model.",
                    ),
                    (
                        "Request limits",
                        "Control bounded payload and "
                        "vision input limits.",
                    ),
                    (
                        "Inspection",
                        "Show request readiness and "
                        "response diagnostics.",
                    ),
                ],
                "Run Vision Check",
            ),
        )

        self._register_page(
            "timeline",
            ModulePage(
                "Timeline",
                "Synchronize narration, scenes and "
                "assigned media before export.",
                "Timeline workspace",
                "The first version will focus on "
                "reliable scene timing instead of a "
                "full Premiere-style editor.",
                [
                    (
                        "Narration track",
                        "Voice duration remains the "
                        "timing backbone.",
                    ),
                    (
                        "Scene blocks",
                        "Each scene shows start, end "
                        "and assigned media.",
                    ),
                    (
                        "Adjustments",
                        "Trim, extend, replace or mute "
                        "scene media.",
                    ),
                ],
                "Build Timeline",
            ),
        )

        self._register_page(
            "export",
            ModulePage(
                "Export",
                "Choose render settings and produce "
                "the final video through the existing engine.",
                "Render workspace",
                "FFmpeg and the current production "
                "runner will remain behind the UI.",
                [
                    (
                        "Format",
                        "Resolution, FPS, codec and "
                        "quality presets.",
                    ),
                    (
                        "Validation",
                        "Check project readiness "
                        "before rendering.",
                    ),
                    (
                        "Progress",
                        "Display render progress and "
                        "final output path.",
                    ),
                ],
                "Render Video",
            ),
        )

        self._register_page(
            "diagnostics",
            ModulePage(
                "Diagnostics",
                "Central place for provider, model, "
                "credential and runtime readiness checks.",
                "Provider diagnostics",
                "The existing M100 diagnostics "
                "host/controller/view will be integrated "
                "here after the UI shell is approved.",
                [
                    (
                        "Provider readiness",
                        "Credential, endpoint and model checks.",
                    ),
                    (
                        "Vision request",
                        "Payload and bounded vision validation.",
                    ),
                    (
                        "Runtime",
                        "Python, FFmpeg and production "
                        "dependencies.",
                    ),
                ],
                "Run Diagnostics",
            ),
        )

        self._register_page(
            "settings",
            ModulePage(
                "Settings",
                "Manage application preferences, "
                "providers and API key entry points.",
                "Application settings",
                "This page will later link to the existing "
                "API key manager without moving secrets "
                "into GUI state.",
                [
                    (
                        "API providers",
                        "Manage configured provider profiles.",
                    ),
                    (
                        "Stock providers",
                        "Pexels, Pixabay and future sources.",
                    ),
                    (
                        "Application",
                        "Paths, cache, theme and default "
                        "export settings.",
                    ),
                ],
                "Open API Key Manager",
            ),
        )


    def navigate_to(
        self,
        key,
    ):

        if key not in self.page_indexes:
            return

        self.pages.setCurrentIndex(
            self.page_indexes[
                key
            ]
        )

        selected_label = key

        for item in NAV_ITEMS:

            button = self.nav_buttons[
                item.key
            ]

            is_selected = (
                item.key == key
            )

            button.setProperty(
                "selected",
                is_selected,
            )

            button.style().unpolish(
                button
            )

            button.style().polish(
                button
            )

            if is_selected:
                selected_label = (
                    item.label
                )

        self.top_title.setText(
            selected_label
        )


def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setFont(
        QFont(
            "Segoe UI",
            10,
        )
    )

    app.setStyleSheet(
        APP_STYLE
    )

    window = (
        CreatorStudioWindow()
    )

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    from creator_studio.launcher import main as _launch_main
    raise SystemExit(_launch_main())