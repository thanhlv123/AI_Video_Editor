from pathlib import Path
import json
import os
import sys

from PyQt6.QtCore import (
    QProcess,
    QProcessEnvironment,
    Qt,
)

from PyQt6.QtGui import (
    QFont,
    QTextCursor,
)

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.api_key_manager import APIKeyManager
from api_keys_dialog import APIKeysDialog


# ==================================================
# PROJECT
# ==================================================

ROOT = Path(__file__).resolve().parent

RUNNER = ROOT / "run_ai_video.py"

GUI_SETTINGS_FILE = (
    ROOT
    / "config"
    / "gui_settings.json"
)


# ==================================================
# MAIN WINDOW
# ==================================================

class AIVideoEditorGUI(QMainWindow):

    def __init__(self):

        super().__init__()

        self.process = None
        self.audio_path = None
        self.output_path = None
        self.last_success_output = None

        self.api_manager = APIKeyManager(
            ROOT
        )

        self.gui_settings = (
            self._load_gui_settings()
        )

        self.setWindowTitle(
            "AI Video Editor"
        )

        self.resize(
            1000,
            800,
        )

        self.setMinimumSize(
            840,
            680,
        )

        self._build_ui()

        self.refresh_api_status()
        self.refresh_stock_status()


    # ==================================================
    # SETTINGS
    # ==================================================

    def _default_gui_settings(self):

        return {
            "stock_providers": {
                "pexels": True,
                "pixabay": True,
            }
        }


    def _load_gui_settings(self):

        defaults = (
            self._default_gui_settings()
        )

        try:

            if not GUI_SETTINGS_FILE.exists():

                return defaults

            data = json.loads(
                GUI_SETTINGS_FILE.read_text(
                    encoding="utf-8"
                )
            )

            stock = data.get(
                "stock_providers",
                {},
            )

            return {
                "stock_providers": {
                    "pexels":
                        bool(
                            stock.get(
                                "pexels",
                                True,
                            )
                        ),

                    "pixabay":
                        bool(
                            stock.get(
                                "pixabay",
                                True,
                            )
                        ),
                }
            }

        except Exception:

            return defaults


    def _save_gui_settings(self):

        GUI_SETTINGS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "stock_providers": {
                "pexels":
                    self.pexels_check.isChecked(),

                "pixabay":
                    self.pixabay_check.isChecked(),
            }
        }

        GUI_SETTINGS_FILE.write_text(
            json.dumps(
                data,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.gui_settings = data


    # ==================================================
    # UI
    # ==================================================

    def _build_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        main_layout = QVBoxLayout(
            central
        )

        main_layout.setContentsMargins(
            24,
            20,
            24,
            20,
        )

        main_layout.setSpacing(
            12
        )


        # ==================================================
        # TITLE
        # ==================================================

        title = QLabel(
            "AI VIDEO EDITOR"
        )

        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)

        title.setFont(
            title_font
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        subtitle = QLabel(
            "Voice → AI Analysis → Stock → Timeline → Final Video"
        )

        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        main_layout.addWidget(
            title
        )

        main_layout.addWidget(
            subtitle
        )


        # ==================================================
        # 1. AUDIO
        # ==================================================

        audio_label = QLabel(
            "1. Voice / Audio"
        )

        audio_label.setFont(
            self._section_font()
        )

        audio_row = QHBoxLayout()

        self.audio_edit = QLineEdit()

        self.audio_edit.setPlaceholderText(
            "Chọn file voice/audio..."
        )

        self.audio_button = QPushButton(
            "Chọn Voice"
        )

        self.audio_button.clicked.connect(
            self.choose_audio
        )

        audio_row.addWidget(
            self.audio_edit,
            1,
        )

        audio_row.addWidget(
            self.audio_button
        )

        main_layout.addWidget(
            audio_label
        )

        main_layout.addLayout(
            audio_row
        )


        # ==================================================
        # 2. OUTPUT
        # ==================================================

        output_label = QLabel(
            "2. Nơi lưu video"
        )

        output_label.setFont(
            self._section_font()
        )

        output_row = QHBoxLayout()

        self.output_edit = QLineEdit()

        self.output_edit.setPlaceholderText(
            "Video cuối sẽ được lưu tại đây..."
        )

        self.output_button = QPushButton(
            "Chọn nơi lưu"
        )

        self.output_button.clicked.connect(
            self.choose_output
        )

        output_row.addWidget(
            self.output_edit,
            1,
        )

        output_row.addWidget(
            self.output_button
        )

        main_layout.addWidget(
            output_label
        )

        main_layout.addLayout(
            output_row
        )


        # ==================================================
        # 3. STOCK PROVIDERS
        # ==================================================

        stock_label = QLabel(
            "3. Stock Providers"
        )

        stock_label.setFont(
            self._section_font()
        )

        main_layout.addWidget(
            stock_label
        )

        stock_row = QHBoxLayout()

        stock_settings = (
            self.gui_settings.get(
                "stock_providers",
                {},
            )
        )

        self.pexels_check = QCheckBox(
            "Pexels"
        )

        self.pexels_check.setChecked(
            stock_settings.get(
                "pexels",
                True,
            )
        )

        self.pixabay_check = QCheckBox(
            "Pixabay"
        )

        self.pixabay_check.setChecked(
            stock_settings.get(
                "pixabay",
                True,
            )
        )

        self.pexels_check.stateChanged.connect(
            self.stock_provider_changed
        )

        self.pixabay_check.stateChanged.connect(
            self.stock_provider_changed
        )

        self.stock_status_label = QLabel()

        stock_row.addWidget(
            self.pexels_check
        )

        stock_row.addWidget(
            self.pixabay_check
        )

        stock_row.addSpacing(
            20
        )

        stock_row.addWidget(
            self.stock_status_label,
            1,
        )

        main_layout.addLayout(
            stock_row
        )


        # ==================================================
        # 4. API PROVIDERS
        # ==================================================

        api_label = QLabel(
            "4. API Providers"
        )

        api_label.setFont(
            self._section_font()
        )

        api_row = QHBoxLayout()

        self.api_status_label = QLabel(
            "Đang kiểm tra API..."
        )

        self.api_settings_button = QPushButton(
            "API KEYS / SETTINGS"
        )

        self.api_settings_button.setMinimumHeight(
            36
        )

        self.api_settings_button.clicked.connect(
            self.open_api_settings
        )

        api_row.addWidget(
            self.api_status_label,
            1,
        )

        api_row.addWidget(
            self.api_settings_button
        )

        main_layout.addWidget(
            api_label
        )

        main_layout.addLayout(
            api_row
        )


        # ==================================================
        # 5. CONTROLS
        # ==================================================

        control_label = QLabel(
            "5. Điều khiển"
        )

        control_label.setFont(
            self._section_font()
        )

        main_layout.addWidget(
            control_label
        )

        button_row = QHBoxLayout()

        self.start_button = QPushButton(
            "START"
        )

        self.start_button.setMinimumHeight(
            44
        )

        self.start_button.clicked.connect(
            self.start_pipeline
        )

        self.stop_button = QPushButton(
            "DỪNG"
        )

        self.stop_button.setMinimumHeight(
            44
        )

        self.stop_button.setEnabled(
            False
        )

        self.stop_button.clicked.connect(
            self.stop_pipeline
        )

        self.open_video_button = QPushButton(
            "MỞ VIDEO"
        )

        self.open_video_button.setMinimumHeight(
            44
        )

        self.open_video_button.setEnabled(
            False
        )

        self.open_video_button.clicked.connect(
            self.open_video
        )

        self.open_folder_button = QPushButton(
            "MỞ THƯ MỤC"
        )

        self.open_folder_button.setMinimumHeight(
            44
        )

        self.open_folder_button.setEnabled(
            False
        )

        self.open_folder_button.clicked.connect(
            self.open_output_folder
        )

        button_row.addWidget(
            self.start_button
        )

        button_row.addWidget(
            self.stop_button
        )

        button_row.addWidget(
            self.open_video_button
        )

        button_row.addWidget(
            self.open_folder_button
        )

        main_layout.addLayout(
            button_row
        )


        # ==================================================
        # 6. PROGRESS
        # ==================================================

        status_label = QLabel(
            "6. Tiến trình"
        )

        status_label.setFont(
            self._section_font()
        )

        main_layout.addWidget(
            status_label
        )

        self.status_text = QLabel(
            "Sẵn sàng"
        )

        self.progress = QProgressBar()

        self.progress.setRange(
            0,
            100,
        )

        self.progress.setValue(
            0
        )

        self.stage_text = QLabel(
            "Chưa chạy"
        )

        self.stage_text.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        main_layout.addWidget(
            self.status_text
        )

        main_layout.addWidget(
            self.progress
        )

        main_layout.addWidget(
            self.stage_text
        )


        # ==================================================
        # 7. LOG
        # ==================================================

        log_label = QLabel(
            "7. Log"
        )

        log_label.setFont(
            self._section_font()
        )

        self.log = QPlainTextEdit()

        self.log.setReadOnly(
            True
        )

        self.log.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )

        log_font = QFont(
            "Consolas"
        )

        log_font.setPointSize(
            9
        )

        self.log.setFont(
            log_font
        )

        main_layout.addWidget(
            log_label
        )

        main_layout.addWidget(
            self.log,
            1,
        )


    # ==================================================
    # FONT
    # ==================================================

    def _section_font(self):

        font = QFont()

        font.setPointSize(
            10
        )

        font.setBold(
            True
        )

        return font


    # ==================================================
    # STOCK PROVIDERS
    # ==================================================

    def stock_provider_changed(self):

        self._save_gui_settings()

        self.refresh_stock_status()


    def _selected_stock_providers(self):

        providers = []

        if self.pexels_check.isChecked():

            providers.append(
                "pexels"
            )

        if self.pixabay_check.isChecked():

            providers.append(
                "pixabay"
            )

        return providers


    def refresh_stock_status(self):

        providers = (
            self._selected_stock_providers()
        )

        if providers:

            self.stock_status_label.setText(
                "Đang dùng: "
                + ", ".join(
                    provider.capitalize()
                    for provider
                    in providers
                )
            )

        else:

            self.stock_status_label.setText(
                "Chưa chọn nguồn stock."
            )


    # ==================================================
    # API SETTINGS
    # ==================================================

    def open_api_settings(self):

        dialog = APIKeysDialog(
            manager=self.api_manager,
            parent=self,
        )

        dialog.exec()

        self.refresh_api_status()


    def refresh_api_status(self):

        profiles = (
            self.api_manager.load_profiles()
        )

        configured = []

        for profile in profiles:

            if not profile.get(
                "enabled",
                False,
            ):
                continue

            secret = (
                self.api_manager.get_secret(
                    profile.get("id")
                )
            )

            if secret:

                configured.append(
                    profile.get(
                        "name",
                        "Unknown",
                    )
                )

        if configured:

            self.api_status_label.setText(
                "API sẵn sàng: "
                + ", ".join(
                    configured
                )
            )

        else:

            self.api_status_label.setText(
                "Chưa có API Key được cấu hình."
            )


    # ==================================================
    # AUDIO
    # ==================================================

    def choose_audio(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file Voice / Audio",
            str(ROOT / "media"),
            (
                "Audio Files "
                "(*.mp3 *.wav *.m4a *.aac *.flac *.ogg);;"
                "All Files (*.*)"
            ),
        )

        if not file_path:

            return

        self.audio_path = Path(
            file_path
        )

        self.audio_edit.setText(
            str(self.audio_path)
        )

        default_output = (
            ROOT
            / "exports"
            / (
                self.audio_path.stem
                + "_final.mp4"
            )
        )

        self.output_path = (
            default_output
        )

        self.output_edit.setText(
            str(default_output)
        )

        self.status_text.setText(
            "Đã chọn voice."
        )


    # ==================================================
    # OUTPUT
    # ==================================================

    def choose_output(self):

        audio_text = (
            self.audio_edit.text().strip()
        )

        if audio_text:

            default_name = (
                Path(audio_text).stem
                + "_final.mp4"
            )

        else:

            default_name = (
                "final_video.mp4"
            )

        default_path = (
            ROOT
            / "exports"
            / default_name
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Chọn nơi lưu video",
            str(default_path),
            "MP4 Video (*.mp4)",
        )

        if not file_path:

            return

        output = Path(
            file_path
        )

        if output.suffix.lower() != ".mp4":

            output = output.with_suffix(
                ".mp4"
            )

        self.output_path = output

        self.output_edit.setText(
            str(output)
        )


    # ==================================================
    # API PREFLIGHT
    # ==================================================

    def _check_required_api_keys(self):

        runtime = (
            self.api_manager.runtime_environment()
        )

        selected_providers = (
            self._selected_stock_providers()
        )

        if not selected_providers:

            QMessageBox.warning(
                self,
                "Chưa chọn Stock Provider",
                (
                    "Hãy bật ít nhất một nguồn stock:\n\n"
                    "Pexels hoặc Pixabay."
                ),
            )

            return False


        missing = []


        # KIE is always required by current pipeline.

        if not (
            runtime.get("KIE_API_KEY")
            or os.getenv("KIE_API_KEY")
        ):

            missing.append(
                "KIE AI"
            )


        if (
            "pexels"
            in selected_providers
        ):

            if not (
                runtime.get("PEXELS_API_KEY")
                or os.getenv("PEXELS_API_KEY")
            ):

                missing.append(
                    "Pexels"
                )


        if (
            "pixabay"
            in selected_providers
        ):

            if not (
                runtime.get("PIXABAY_API_KEY")
                or os.getenv("PIXABAY_API_KEY")
            ):

                missing.append(
                    "Pixabay"
                )


        if not missing:

            return True


        QMessageBox.warning(
            self,
            "Thiếu API Key",
            (
                "Thiếu API Key:\n\n"
                + "\n".join(
                    "• " + item
                    for item
                    in missing
                )
                + "\n\nMở API KEYS / SETTINGS "
                "để thêm API Key."
            ),
        )

        return False


    # ==================================================
    # PROCESS ENVIRONMENT
    # ==================================================

    def _build_process_environment(self):

        environment = (
            QProcessEnvironment.systemEnvironment()
        )

        runtime_keys = (
            self.api_manager.runtime_environment()
        )

        # API Manager values override inherited env vars.

        for name, value in runtime_keys.items():

            environment.insert(
                str(name),
                str(value),
            )


        # ==================================================
        # STOCK PROVIDER FLAGS
        # ==================================================

        environment.insert(
            "STOCK_PROVIDER_PEXELS",
            (
                "1"
                if self.pexels_check.isChecked()
                else "0"
            ),
        )

        environment.insert(
            "STOCK_PROVIDER_PIXABAY",
            (
                "1"
                if self.pixabay_check.isChecked()
                else "0"
            ),
        )


        return (
            environment,
            runtime_keys,
        )


    # ==================================================
    # VALIDATE INPUTS
    # ==================================================

    def validate_inputs(self):

        audio_text = (
            self.audio_edit.text().strip()
        )

        output_text = (
            self.output_edit.text().strip()
        )

        if not audio_text:

            QMessageBox.warning(
                self,
                "Thiếu Voice",
                "Hãy chọn file voice/audio.",
            )

            return False


        audio_path = Path(
            audio_text
        )

        if not audio_path.exists():

            QMessageBox.warning(
                self,
                "Không tìm thấy file",
                (
                    "Không tìm thấy file audio:\n\n"
                    + str(audio_path)
                ),
            )

            return False


        if not output_text:

            QMessageBox.warning(
                self,
                "Thiếu Output",
                "Hãy chọn nơi lưu video.",
            )

            return False


        if not RUNNER.exists():

            QMessageBox.critical(
                self,
                "Thiếu run_ai_video.py",
                (
                    "Không tìm thấy:\n\n"
                    + str(RUNNER)
                ),
            )

            return False


        if not self._check_required_api_keys():

            return False


        self.audio_path = (
            audio_path.resolve()
        )

        self.output_path = (
            Path(output_text).resolve()
        )

        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._save_gui_settings()

        return True


    # ==================================================
    # PYTHON
    # ==================================================

    def _pipeline_python(self):

        executable = Path(
            sys.executable
        )

        if executable.name.lower() == "pythonw.exe":

            candidate = executable.with_name(
                "python.exe"
            )

            if candidate.exists():

                return candidate

        return executable


    # ==================================================
    # START
    # ==================================================

    def start_pipeline(self):

        if not self.validate_inputs():

            return


        if (
            self.process is not None
            and
            self.process.state()
            != QProcess.ProcessState.NotRunning
        ):

            QMessageBox.information(
                self,
                "Pipeline đang chạy",
                "Pipeline hiện đang chạy.",
            )

            return


        self.last_success_output = None

        self.open_video_button.setEnabled(
            False
        )

        self.open_folder_button.setEnabled(
            False
        )

        self.log.clear()

        self.progress.setValue(
            0
        )

        self.status_text.setText(
            "Đang khởi động..."
        )

        self.stage_text.setText(
            "Khởi động pipeline"
        )

        self._set_running_ui(
            True
        )


        self.process = QProcess(
            self
        )

        self.process.setWorkingDirectory(
            str(ROOT)
        )

        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )


        # ==================================================
        # ENVIRONMENT
        # ==================================================

        environment, runtime_keys = (
            self._build_process_environment()
        )

        self.process.setProcessEnvironment(
            environment
        )


        self.process.readyReadStandardOutput.connect(
            self.read_process_output
        )

        self.process.finished.connect(
            self.process_finished
        )

        self.process.errorOccurred.connect(
            self.process_error
        )


        python_exe = (
            self._pipeline_python()
        )

        arguments = [
            "-u",
            str(RUNNER),
            str(self.audio_path),
            "--output",
            str(self.output_path),
        ]


        # ==================================================
        # LOG
        # ==================================================

        self.append_log(
            "=" * 70
        )

        self.append_log(
            "GUI START"
        )

        self.append_log(
            "=" * 70
        )

        self.append_log(
            f"Python: {python_exe}"
        )

        self.append_log(
            f"Voice: {self.audio_path}"
        )

        self.append_log(
            f"Output: {self.output_path}"
        )


        self.append_log("")
        self.append_log(
            "Stock providers:"
        )

        self.append_log(
            "  - Pexels: "
            + (
                "ENABLED"
                if self.pexels_check.isChecked()
                else "DISABLED"
            )
        )

        self.append_log(
            "  - Pixabay: "
            + (
                "ENABLED"
                if self.pixabay_check.isChecked()
                else "DISABLED"
            )
        )


        self.append_log("")
        self.append_log(
            "API environment loaded:"
        )

        for env_name in runtime_keys.keys():

            self.append_log(
                f"  - {env_name}: READY"
            )


        # Never print API values.

        self.append_log("")

        self.process.start(
            str(python_exe),
            arguments,
        )


    # ==================================================
    # PROCESS OUTPUT
    # ==================================================

    def read_process_output(self):

        if self.process is None:

            return

        raw = (
            self.process.readAllStandardOutput()
        )

        text = bytes(raw).decode(
            "utf-8",
            errors="replace",
        )

        if not text:

            return

        self.log.moveCursor(
            QTextCursor.MoveOperation.End
        )

        self.log.insertPlainText(
            text
        )

        self.log.moveCursor(
            QTextCursor.MoveOperation.End
        )

        self._update_progress_from_text(
            text
        )


    # ==================================================
    # PROGRESS
    # ==================================================

    def _update_progress_from_text(
        self,
        text,
    ):

        if "[1/5] VOICE PIPELINE" in text:

            self.progress.setValue(10)

            self.stage_text.setText(
                "1/5 — Voice"
            )


        if "VOICE STAGE: RESUME" in text:

            self.progress.setValue(
                max(
                    self.progress.value(),
                    20,
                )
            )


        if "[2/5] AI SCENE ANALYSIS" in text:

            self.progress.setValue(30)

            self.stage_text.setText(
                "2/5 — AI Scene Analysis"
            )


        if "AI STAGE: RESUME" in text:

            self.progress.setValue(
                max(
                    self.progress.value(),
                    40,
                )
            )


        if "[3/5] STOCK PIPELINE" in text:

            self.progress.setValue(50)

            self.stage_text.setText(
                "3/5 — Stock"
            )

            self.status_text.setText(
                "Đang tìm và tải stock..."
            )


        if "All speech stock scenes validated: PASS" in text:

            self.progress.setValue(72)


        if "[4/5] BUILD TIMELINE" in text:

            self.progress.setValue(78)

            self.stage_text.setText(
                "4/5 — Timeline"
            )


        if "[5/5] RENDER" in text:

            self.progress.setValue(90)

            self.stage_text.setText(
                "5/5 — Render"
            )


        if "FULL VIDEO PIPELINE SUCCESS" in text:

            self.progress.setValue(100)

            self.stage_text.setText(
                "Hoàn tất"
            )

            self.status_text.setText(
                "Video đã render thành công."
            )


        if "UNEXPECTED ERROR" in text:

            self.status_text.setText(
                "Pipeline gặp lỗi."
            )


    # ==================================================
    # FINISHED
    # ==================================================

    def process_finished(
        self,
        exit_code,
        exit_status,
    ):

        self.read_process_output()

        self._set_running_ui(
            False
        )

        success = (
            exit_code == 0
            and
            self.output_path is not None
            and
            self.output_path.exists()
        )


        if success:

            self.progress.setValue(
                100
            )

            self.stage_text.setText(
                "Hoàn tất"
            )

            self.status_text.setText(
                "FULL VIDEO PIPELINE SUCCESS"
            )

            self.last_success_output = (
                self.output_path
            )

            self.open_video_button.setEnabled(
                True
            )

            self.open_folder_button.setEnabled(
                True
            )

            QMessageBox.information(
                self,
                "Hoàn tất",
                (
                    "Video đã được tạo thành công:\n\n"
                    + str(self.output_path)
                ),
            )

        else:

            self.stage_text.setText(
                "Chưa hoàn tất"
            )

            self.status_text.setText(
                "Pipeline đã dừng."
            )

            self.append_log("")

            self.append_log(
                f"Process exit code: {exit_code}"
            )

            QMessageBox.warning(
                self,
                "Pipeline chưa hoàn tất",
                (
                    "Pipeline đã dừng trước khi "
                    "tạo video cuối.\n\n"
                    "Hãy xem phần Log."
                ),
            )


    # ==================================================
    # ERROR
    # ==================================================

    def process_error(
        self,
        error,
    ):

        self.append_log(
            f"QProcess error: {error}"
        )


    # ==================================================
    # STOP
    # ==================================================

    def stop_pipeline(self):

        if self.process is None:

            return

        if (
            self.process.state()
            == QProcess.ProcessState.NotRunning
        ):

            return

        answer = QMessageBox.question(
            self,
            "Dừng pipeline",
            (
                "Bạn muốn dừng pipeline?\n\n"
                "Các scene đã lưu vẫn có thể resume."
            ),
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):

            return

        self.status_text.setText(
            "Đang dừng..."
        )

        self.process.terminate()

        if not self.process.waitForFinished(
            5000
        ):

            self.process.kill()


    # ==================================================
    # OPEN VIDEO
    # ==================================================

    def open_video(self):

        path = (
            self.last_success_output
            or self.output_path
        )

        if (
            path is None
            or
            not Path(path).exists()
        ):

            QMessageBox.warning(
                self,
                "Không tìm thấy video",
                "File video chưa tồn tại.",
            )

            return

        os.startfile(
            str(path)
        )


    # ==================================================
    # OPEN OUTPUT FOLDER
    # ==================================================

    def open_output_folder(self):

        path = (
            self.last_success_output
            or self.output_path
        )

        if path is None:

            return

        folder = Path(path).parent

        if folder.exists():

            os.startfile(
                str(folder)
            )


    # ==================================================
    # RUNNING UI
    # ==================================================

    def _set_running_ui(
        self,
        running,
    ):

        self.start_button.setEnabled(
            not running
        )

        self.audio_button.setEnabled(
            not running
        )

        self.output_button.setEnabled(
            not running
        )

        self.api_settings_button.setEnabled(
            not running
        )

        self.pexels_check.setEnabled(
            not running
        )

        self.pixabay_check.setEnabled(
            not running
        )

        self.audio_edit.setEnabled(
            not running
        )

        self.output_edit.setEnabled(
            not running
        )

        self.stop_button.setEnabled(
            running
        )


    # ==================================================
    # LOG
    # ==================================================

    def append_log(
        self,
        text,
    ):

        self.log.appendPlainText(
            str(text)
        )


    # ==================================================
    # CLOSE
    # ==================================================

    def closeEvent(
        self,
        event,
    ):

        self._save_gui_settings()

        if (
            self.process is not None
            and
            self.process.state()
            != QProcess.ProcessState.NotRunning
        ):

            answer = QMessageBox.question(
                self,
                "Pipeline đang chạy",
                (
                    "Pipeline vẫn đang chạy.\n\n"
                    "Bạn có muốn đóng chương trình?"
                ),
            )

            if (
                answer
                != QMessageBox.StandardButton.Yes
            ):

                event.ignore()
                return

            self.process.terminate()

            self.process.waitForFinished(
                3000
            )

            if (
                self.process.state()
                != QProcess.ProcessState.NotRunning
            ):

                self.process.kill()

        event.accept()


# ==================================================
# MAIN
# ==================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "AI Video Editor"
    )

    window = AIVideoEditorGUI()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":

    main()