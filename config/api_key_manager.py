from pathlib import Path
import json
import uuid

import keyring


class APIKeyManager:

    SERVICE_NAME = "AI_Video_Editor"

    STORYBLOCKS_FIELDS = [
        {
            "key": "public_key",
            "label": "Public Key",
            "env_var": "STORYBLOCKS_PUBLIC_KEY",
            "required": True,
        },
        {
            "key": "secret_key",
            "label": "Secret Key",
            "env_var": "STORYBLOCKS_SECRET_KEY",
            "required": True,
        },
        {
            "key": "project_id",
            "label": "Project ID",
            "env_var": "STORYBLOCKS_PROJECT_ID",
            "required": True,
        },
        {
            "key": "user_id",
            "label": "User ID",
            "env_var": "STORYBLOCKS_USER_ID",
            "required": True,
        },
    ]


    def __init__(self, root):

        self.root = Path(root).resolve()

        self.config_dir = (
            self.root
            / "config"
        )

        self.config_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.config_path = (
            self.config_dir
            / "api_providers.json"
        )

        self._ensure_config()

        self._upgrade_config()


    # ==================================================
    # DEFAULT PROFILES
    # ==================================================

    def _default_profiles(self):

        return [
            {
                "id": "kie_ai",
                "name": "KIE AI",
                "env_var": "KIE_API_KEY",
                "base_url": "",
                "model": "gpt-6-luna",
                "enabled": True,
            },
            {
                "id": "pexels",
                "name": "Pexels",
                "env_var": "PEXELS_API_KEY",
                "base_url": "",
                "model": "",
                "enabled": True,
            },
            {
                "id": "pixabay",
                "name": "Pixabay",
                "env_var": "PIXABAY_API_KEY",
                "base_url": "",
                "model": "",
                "enabled": True,
            },
            {
                "id": "youtube_data",
                "name": "YouTube Data API",
                "env_var": "YOUTUBE_API_KEY",
                "base_url": "https://www.googleapis.com/youtube/v3",
                "model": "",
                "enabled": True,
            },
            {
                "id": "storyblocks",
                "name": "Storyblocks",
                "env_var": "",
                "base_url": (
                    "https://api.storyblocks.com"
                ),
                "model": "",
                "enabled": False,
                "fields": [
                    dict(field)
                    for field
                    in self.STORYBLOCKS_FIELDS
                ],
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "env_var": "OPENAI_API_KEY",
                "base_url": "",
                "model": "",
                "enabled": False,
            },
            {
                "id": "anthropic",
                "name": "Anthropic",
                "env_var": "ANTHROPIC_API_KEY",
                "base_url": "",
                "model": "",
                "enabled": False,
            },
            {
                "id": "gemini",
                "name": "Google Gemini",
                "env_var": "GEMINI_API_KEY",
                "base_url": "",
                "model": "",
                "enabled": False,
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "env_var": "DEEPSEEK_API_KEY",
                "base_url": "",
                "model": "",
                "enabled": False,
            },
        ]


    # ==================================================
    # CONFIG
    # ==================================================

    def _ensure_config(self):

        if self.config_path.exists():
            return

        self.save_profiles(
            self._default_profiles()
        )


    def _upgrade_config(self):

        profiles = (
            self.load_profiles()
        )

        defaults = {
            profile["id"]: profile
            for profile
            in self._default_profiles()
        }

        changed = False

        existing_ids = {
            profile.get("id")
            for profile
            in profiles
        }


        # Add missing built-in profiles.

        for profile_id, default in defaults.items():

            if profile_id not in existing_ids:

                profiles.append(
                    default
                )

                changed = True


        # Upgrade Storyblocks from old
        # single-key profile to multi-field profile.

        for profile in profiles:

            if (
                profile.get("id")
                != "storyblocks"
            ):
                continue


            desired_fields = [
                dict(field)
                for field
                in self.STORYBLOCKS_FIELDS
            ]


            if (
                profile.get("fields")
                != desired_fields
            ):

                profile["fields"] = (
                    desired_fields
                )

                changed = True


            if profile.get(
                "env_var",
                "",
            ):

                profile["env_var"] = ""

                changed = True


            if not profile.get(
                "base_url"
            ):

                profile["base_url"] = (
                    "https://api.storyblocks.com"
                )

                changed = True


        if changed:

            self.save_profiles(
                profiles
            )


    def load_profiles(self):

        try:

            with open(
                self.config_path,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

        except Exception:

            data = {
                "providers":
                    self._default_profiles()
            }


        return data.get(
            "providers",
            [],
        )


    def save_profiles(
        self,
        profiles,
    ):

        data = {
            "version": 2,
            "providers": profiles,
        }

        with open(
            self.config_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )


    # ==================================================
    # PROFILE
    # ==================================================

    def get_profile(
        self,
        profile_id,
    ):

        for profile in self.load_profiles():

            if (
                profile.get("id")
                == profile_id
            ):

                return profile

        return None


    def add_profile(
        self,
        name="New Provider",
        env_var="",
    ):

        profiles = (
            self.load_profiles()
        )

        profile = {
            "id":
                str(uuid.uuid4()),

            "name":
                name,

            "env_var":
                env_var,

            "base_url":
                "",

            "model":
                "",

            "enabled":
                True,
        }

        profiles.append(
            profile
        )

        self.save_profiles(
            profiles
        )

        return profile


    def update_profile(
        self,
        updated_profile,
    ):

        profiles = (
            self.load_profiles()
        )

        new_profiles = []

        found = False


        for profile in profiles:

            if (
                profile.get("id")
                == updated_profile.get("id")
            ):

                new_profiles.append(
                    updated_profile
                )

                found = True

            else:

                new_profiles.append(
                    profile
                )


        if not found:

            new_profiles.append(
                updated_profile
            )


        self.save_profiles(
            new_profiles
        )


    def delete_profile(
        self,
        profile_id,
    ):

        profile = self.get_profile(
            profile_id
        )


        self.delete_secret(
            profile_id
        )


        if profile:

            for field in profile.get(
                "fields",
                [],
            ):

                field_key = field.get(
                    "key"
                )

                if field_key:

                    self.delete_field_secret(
                        profile_id,
                        field_key,
                    )


        profiles = [
            profile
            for profile
            in self.load_profiles()

            if (
                profile.get("id")
                != profile_id
            )
        ]


        self.save_profiles(
            profiles
        )


    # ==================================================
    # LEGACY SINGLE SECRET
    # ==================================================

    def _secret_username(
        self,
        profile_id,
    ):

        return (
            "provider:"
            + str(profile_id)
        )


    def set_secret(
        self,
        profile_id,
        secret,
    ):

        secret = str(
            secret
            or ""
        )


        if not secret:

            self.delete_secret(
                profile_id
            )

            return


        keyring.set_password(
            self.SERVICE_NAME,
            self._secret_username(
                profile_id
            ),
            secret,
        )


    def get_secret(
        self,
        profile_id,
    ):

        try:

            value = keyring.get_password(
                self.SERVICE_NAME,
                self._secret_username(
                    profile_id
                ),
            )

            return value or ""

        except Exception:

            return ""


    def delete_secret(
        self,
        profile_id,
    ):

        try:

            keyring.delete_password(
                self.SERVICE_NAME,
                self._secret_username(
                    profile_id
                ),
            )

        except Exception:

            pass


    # ==================================================
    # MULTI-FIELD SECRETS
    # ==================================================

    def _field_secret_username(
        self,
        profile_id,
        field_key,
    ):

        return (
            "provider:"
            + str(profile_id)
            + ":field:"
            + str(field_key)
        )


    def set_field_secret(
        self,
        profile_id,
        field_key,
        value,
    ):

        value = str(
            value
            or ""
        )


        if not value:

            self.delete_field_secret(
                profile_id,
                field_key,
            )

            return


        keyring.set_password(
            self.SERVICE_NAME,
            self._field_secret_username(
                profile_id,
                field_key,
            ),
            value,
        )


    def get_field_secret(
        self,
        profile_id,
        field_key,
    ):

        try:

            value = keyring.get_password(
                self.SERVICE_NAME,
                self._field_secret_username(
                    profile_id,
                    field_key,
                ),
            )

            return value or ""

        except Exception:

            return ""


    def delete_field_secret(
        self,
        profile_id,
        field_key,
    ):

        try:

            keyring.delete_password(
                self.SERVICE_NAME,
                self._field_secret_username(
                    profile_id,
                    field_key,
                ),
            )

        except Exception:

            pass


    # ==================================================
    # PROFILE TYPE
    # ==================================================

    def profile_fields(
        self,
        profile_or_id,
    ):

        if isinstance(
            profile_or_id,
            dict,
        ):

            profile = profile_or_id

        else:

            profile = self.get_profile(
                profile_or_id
            )


        if not profile:

            return []


        return profile.get(
            "fields",
            [],
        ) or []


    def is_multi_field_profile(
        self,
        profile_or_id,
    ):

        return bool(
            self.profile_fields(
                profile_or_id
            )
        )


    # ==================================================
    # CREDENTIAL STATUS
    # ==================================================

    def profile_is_configured(
        self,
        profile_or_id,
    ):

        if isinstance(
            profile_or_id,
            dict,
        ):

            profile = profile_or_id

        else:

            profile = self.get_profile(
                profile_or_id
            )


        if not profile:

            return False


        fields = profile.get(
            "fields",
            [],
        ) or []


        if fields:

            for field in fields:

                if not field.get(
                    "required",
                    True,
                ):

                    continue


                value = (
                    self.get_field_secret(
                        profile.get("id"),
                        field.get("key"),
                    )
                )


                if not value:

                    return False


            return True


        return bool(
            self.get_secret(
                profile.get("id")
            )
        )


    # ==================================================
    # RUNTIME ENVIRONMENT
    # ==================================================

    def runtime_environment(self):

        result = {}


        for profile in self.load_profiles():

            if not profile.get(
                "enabled",
                False,
            ):

                continue


            fields = profile.get(
                "fields",
                [],
            ) or []


            # ------------------------------------------
            # MULTI FIELD PROFILE
            # ------------------------------------------

            if fields:

                for field in fields:

                    env_var = str(
                        field.get(
                            "env_var",
                            "",
                        )
                        or ""
                    ).strip()


                    field_key = str(
                        field.get(
                            "key",
                            "",
                        )
                        or ""
                    ).strip()


                    if (
                        not env_var
                        or
                        not field_key
                    ):

                        continue


                    value = (
                        self.get_field_secret(
                            profile.get("id"),
                            field_key,
                        )
                    )


                    if value:

                        result[
                            env_var
                        ] = value


                continue


            # ------------------------------------------
            # LEGACY SINGLE FIELD PROFILE
            # ------------------------------------------

            env_var = str(
                profile.get(
                    "env_var",
                    "",
                )
                or ""
            ).strip()


            if not env_var:

                continue


            secret = self.get_secret(
                profile.get("id")
            )


            if not secret:

                continue


            result[
                env_var
            ] = secret


        return result


    # ==================================================
    # NON-SECRET PROVIDER SETTINGS
    # ==================================================

    def runtime_provider_settings(self):

        settings = {}


        for profile in self.load_profiles():

            if not profile.get(
                "enabled",
                False,
            ):

                continue


            settings[
                profile["id"]
            ] = {

                "name":
                    profile.get(
                        "name",
                        "",
                    ),

                "env_var":
                    profile.get(
                        "env_var",
                        "",
                    ),

                "base_url":
                    profile.get(
                        "base_url",
                        "",
                    ),

                "model":
                    profile.get(
                        "model",
                        "",
                    ),

                "fields": [
                    dict(field)
                    for field
                    in (
                        profile.get(
                            "fields",
                            [],
                        )
                        or []
                    )
                ],
            }


        return settings