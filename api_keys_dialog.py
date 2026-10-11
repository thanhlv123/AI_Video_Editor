from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class APIKeysDialog(QDialog):

    def __init__(
        self,
        manager,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.manager = manager

        self.current_profile_id = None

        self.multi_field_edits = {}

        self.setWindowTitle(
            "API Keys / Providers"
        )

        self.resize(
            900,
            600,
        )

        self._build_ui()

        self.reload_profiles()


    # ==================================================
    # UI
    # ==================================================

    def _build_ui(self):

        main_layout = QVBoxLayout(
            self
        )


        title = QLabel(
            "API KEY MANAGER"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )


        description = QLabel(
            "Quản lý API Key của Stock Providers "
            "và AI Providers.\n"
            "Thông tin xác thực được lưu trong "
            "Windows Credential Manager."
        )

        description.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )


        main_layout.addWidget(
            title
        )

        main_layout.addWidget(
            description
        )


        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )


        # ==================================================
        # LEFT
        # ==================================================

        left = QWidget()

        left_layout = QVBoxLayout(
            left
        )


        self.provider_list = QListWidget()

        self.provider_list.currentRowChanged.connect(
            self.provider_selected
        )


        left_layout.addWidget(
            QLabel("Providers")
        )

        left_layout.addWidget(
            self.provider_list
        )


        add_button = QPushButton(
            "+ Add Provider"
        )

        add_button.clicked.connect(
            self.add_provider
        )


        delete_button = QPushButton(
            "Delete Provider"
        )

        delete_button.clicked.connect(
            self.delete_provider
        )


        left_layout.addWidget(
            add_button
        )

        left_layout.addWidget(
            delete_button
        )


        # ==================================================
        # RIGHT
        # ==================================================

        right = QWidget()

        right_layout = QVBoxLayout(
            right
        )


        # ==================================================
        # COMMON FORM
        # ==================================================

        common_form = QFormLayout()


        self.enabled_check = QCheckBox(
            "Enabled"
        )

        self.name_edit = QLineEdit()

        self.base_url_edit = QLineEdit()

        self.base_url_edit.setPlaceholderText(
            "Optional API Base URL"
        )

        self.model_edit = QLineEdit()

        self.model_edit.setPlaceholderText(
            "Optional AI model"
        )


        common_form.addRow(
            "Enabled:",
            self.enabled_check,
        )

        common_form.addRow(
            "Provider name:",
            self.name_edit,
        )

        common_form.addRow(
            "Base URL:",
            self.base_url_edit,
        )

        common_form.addRow(
            "Model:",
            self.model_edit,
        )


        right_layout.addLayout(
            common_form
        )


        # ==================================================
        # SINGLE KEY WIDGET
        # ==================================================

        self.single_widget = QWidget()

        single_form = QFormLayout(
            self.single_widget
        )


        self.env_edit = QLineEdit()

        self.env_edit.setPlaceholderText(
            "PEXELS_API_KEY"
        )


        self.key_edit = QLineEdit()

        self.key_edit.setEchoMode(
            QLineEdit.EchoMode.Password
        )


        self.show_key_check = QCheckBox(
            "Show API Key"
        )

        self.show_key_check.toggled.connect(
            self.toggle_key_visibility
        )


        single_form.addRow(
            "Environment variable:",
            self.env_edit,
        )

        single_form.addRow(
            "API Key:",
            self.key_edit,
        )

        single_form.addRow(
            "",
            self.show_key_check,
        )


        right_layout.addWidget(
            self.single_widget
        )


        # ==================================================
        # MULTI FIELD WIDGET
        # ==================================================

        self.multi_widget = QWidget()

        multi_layout = QVBoxLayout(
            self.multi_widget
        )

        multi_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )


        multi_title = QLabel(
            "Provider Credentials"
        )

        multi_layout.addWidget(
            multi_title
        )


        self.multi_form = QFormLayout()

        multi_layout.addLayout(
            self.multi_form
        )


        self.show_multi_check = QCheckBox(
            "Show credential values"
        )

        self.show_multi_check.toggled.connect(
            self.toggle_multi_visibility
        )

        multi_layout.addWidget(
            self.show_multi_check
        )


        right_layout.addWidget(
            self.multi_widget
        )


        # ==================================================
        # INFO
        # ==================================================

        self.info_label = QLabel()

        self.info_label.setWordWrap(
            True
        )

        right_layout.addWidget(
            self.info_label
        )


        save_button = QPushButton(
            "SAVE PROVIDER"
        )

        save_button.setMinimumHeight(
            42
        )

        save_button.clicked.connect(
            self.save_current
        )


        right_layout.addStretch()

        right_layout.addWidget(
            save_button
        )


        splitter.addWidget(
            left
        )

        splitter.addWidget(
            right
        )

        splitter.setSizes(
            [
                260,
                640,
            ]
        )


        main_layout.addWidget(
            splitter,
            1,
        )


        close_row = QHBoxLayout()

        close_row.addStretch()


        close_button = QPushButton(
            "Close"
        )

        close_button.clicked.connect(
            self.accept
        )


        close_row.addWidget(
            close_button
        )

        main_layout.addLayout(
            close_row
        )


    # ==================================================
    # LIST
    # ==================================================

    def reload_profiles(
        self,
        select_id=None,
    ):

        profiles = (
            self.manager.load_profiles()
        )

        self.provider_list.clear()


        selected_row = 0


        for index, profile in enumerate(
            profiles
        ):

            configured = (
                self.manager.profile_is_configured(
                    profile
                )
            )


            if profile.get(
                "enabled"
            ):

                prefix = (
                    "✓ "
                    if configured
                    else "⚠ "
                )

            else:

                prefix = "○ "


            self.provider_list.addItem(
                prefix
                + profile.get(
                    "name",
                    "Unnamed",
                )
            )


            if (
                select_id
                and
                profile.get("id")
                == select_id
            ):

                selected_row = index


        if profiles:

            self.provider_list.setCurrentRow(
                selected_row
            )


    # ==================================================
    # CLEAR MULTI FORM
    # ==================================================

    def _clear_multi_fields(self):

        self.multi_field_edits = {}


        while (
            self.multi_form.rowCount()
            > 0
        ):

            self.multi_form.removeRow(
                0
            )


    # ==================================================
    # BUILD MULTI FIELDS
    # ==================================================

    def _build_multi_fields(
        self,
        profile,
    ):

        self._clear_multi_fields()


        fields = (
            profile.get(
                "fields",
                [],
            )
            or []
        )


        for field in fields:

            field_key = str(
                field.get(
                    "key",
                    "",
                )
            )


            if not field_key:

                continue


            label = str(
                field.get(
                    "label",
                    field_key,
                )
            )


            env_var = str(
                field.get(
                    "env_var",
                    "",
                )
            )


            edit = QLineEdit()

            edit.setEchoMode(
                QLineEdit.EchoMode.Password
            )


            if env_var:

                edit.setPlaceholderText(
                    env_var
                )


            value = (
                self.manager.get_field_secret(
                    profile.get("id"),
                    field_key,
                )
            )

            edit.setText(
                value
            )


            self.multi_field_edits[
                field_key
            ] = edit


            display_label = label


            if field.get(
                "required",
                True,
            ):

                display_label += " *"


            self.multi_form.addRow(
                display_label + ":",
                edit,
            )


        self.show_multi_check.setChecked(
            False
        )

        self.toggle_multi_visibility(
            False
        )


    # ==================================================
    # SELECT PROVIDER
    # ==================================================

    def provider_selected(
        self,
        row,
    ):

        profiles = (
            self.manager.load_profiles()
        )


        if (
            row < 0
            or
            row >= len(profiles)
        ):

            return


        profile = profiles[
            row
        ]


        self.current_profile_id = (
            profile["id"]
        )


        self.enabled_check.setChecked(
            profile.get(
                "enabled",
                False,
            )
        )


        self.name_edit.setText(
            profile.get(
                "name",
                "",
            )
        )


        self.base_url_edit.setText(
            profile.get(
                "base_url",
                "",
            )
        )


        self.model_edit.setText(
            profile.get(
                "model",
                "",
            )
        )


        fields = (
            profile.get(
                "fields",
                [],
            )
            or []
        )


        # ==================================================
        # MULTI FIELD PROVIDER
        # ==================================================

        if fields:

            self.single_widget.hide()

            self.multi_widget.show()

            self._build_multi_fields(
                profile
            )


            if (
                profile.get("id")
                == "storyblocks"
            ):

                self.info_label.setText(
                    "Storyblocks API v2 cần "
                    "Public Key, Secret Key, Project ID "
                    "và User ID.\n"
                    "Các giá trị này được lưu trong "
                    "Windows Credential Manager."
                )

            else:

                self.info_label.setText(
                    "Provider này sử dụng nhiều "
                    "credential fields."
                )


        # ==================================================
        # SINGLE KEY PROVIDER
        # ==================================================

        else:

            self.multi_widget.hide()

            self.single_widget.show()


            self.env_edit.setText(
                profile.get(
                    "env_var",
                    "",
                )
            )


            secret = (
                self.manager.get_secret(
                    self.current_profile_id
                )
            )


            self.key_edit.setText(
                secret
            )


            self.show_key_check.setChecked(
                False
            )


            self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Password
            )


            self.info_label.setText(
                "Ví dụ:\n"
                "Pexels → PEXELS_API_KEY\n"
                "Pixabay → PIXABAY_API_KEY\n"
                "KIE AI → KIE_API_KEY"
            )


    # ==================================================
    # SHOW SINGLE KEY
    # ==================================================

    def toggle_key_visibility(
        self,
        checked,
    ):

        if checked:

            self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal
            )

        else:

            self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Password
            )


    # ==================================================
    # SHOW MULTI VALUES
    # ==================================================

    def toggle_multi_visibility(
        self,
        checked,
    ):

        mode = (
            QLineEdit.EchoMode.Normal
            if checked
            else QLineEdit.EchoMode.Password
        )


        for edit in (
            self.multi_field_edits.values()
        ):

            edit.setEchoMode(
                mode
            )


    # ==================================================
    # SAVE
    # ==================================================

    def save_current(self):

        if not self.current_profile_id:

            return


        existing = (
            self.manager.get_profile(
                self.current_profile_id
            )
        )


        if not existing:

            return


        name = (
            self.name_edit.text().strip()
        )


        if not name:

            QMessageBox.warning(
                self,
                "Missing name",
                "Provider name is required.",
            )

            return


        fields = (
            existing.get(
                "fields",
                [],
            )
            or []
        )


        profile = dict(
            existing
        )


        profile.update(
            {
                "id":
                    self.current_profile_id,

                "name":
                    name,

                "base_url":
                    self.base_url_edit.text().strip(),

                "model":
                    self.model_edit.text().strip(),

                "enabled":
                    self.enabled_check.isChecked(),
            }
        )


        # ==================================================
        # MULTI FIELD
        # ==================================================

        if fields:

            profile["env_var"] = ""

            profile["fields"] = fields


            missing_fields = []


            for field in fields:

                field_key = (
                    field.get("key")
                )


                edit = (
                    self.multi_field_edits.get(
                        field_key
                    )
                )


                value = (
                    edit.text().strip()
                    if edit
                    else ""
                )


                if (
                    field.get(
                        "required",
                        True,
                    )
                    and
                    not value
                    and
                    self.enabled_check.isChecked()
                ):

                    missing_fields.append(
                        field.get(
                            "label",
                            field_key,
                        )
                    )


            if missing_fields:

                QMessageBox.warning(
                    self,
                    "Missing credentials",
                    (
                        "Provider đang Enabled nhưng "
                        "thiếu:\n\n"
                        + "\n".join(
                            "• " + item
                            for item
                            in missing_fields
                        )
                    ),
                )

                return


            self.manager.update_profile(
                profile
            )


            for field in fields:

                field_key = (
                    field.get("key")
                )

                edit = (
                    self.multi_field_edits.get(
                        field_key
                    )
                )


                self.manager.set_field_secret(
                    self.current_profile_id,
                    field_key,
                    (
                        edit.text().strip()
                        if edit
                        else ""
                    ),
                )


        # ==================================================
        # SINGLE FIELD
        # ==================================================

        else:

            env_var = (
                self.env_edit.text().strip()
            )


            if not env_var:

                QMessageBox.warning(
                    self,
                    "Missing variable",
                    (
                        "Environment variable "
                        "name is required."
                    ),
                )

                return


            profile["env_var"] = (
                env_var
            )


            self.manager.update_profile(
                profile
            )


            self.manager.set_secret(
                self.current_profile_id,
                self.key_edit.text().strip(),
            )


        saved_id = (
            self.current_profile_id
        )


        self.reload_profiles(
            select_id=saved_id
        )


        QMessageBox.information(
            self,
            "Saved",
            name + " đã được lưu.",
        )


    # ==================================================
    # ADD
    # ==================================================

    def add_provider(self):

        profile = (
            self.manager.add_profile(
                name="New Provider",
                env_var="CUSTOM_API_KEY",
            )
        )


        self.reload_profiles(
            select_id=profile.get("id")
        )


    # ==================================================
    # DELETE
    # ==================================================

    def delete_provider(self):

        if not self.current_profile_id:

            return


        profile = (
            self.manager.get_profile(
                self.current_profile_id
            )
        )


        if not profile:

            return


        answer = QMessageBox.question(
            self,
            "Delete Provider",
            (
                "Xóa provider:\n\n"
                + profile.get(
                    "name",
                    "",
                )
                + " ?"
            ),
        )


        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):

            return


        self.manager.delete_profile(
            self.current_profile_id
        )


        self.current_profile_id = None

        self.reload_profiles()