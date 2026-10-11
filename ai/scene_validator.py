class SceneValidationError(Exception):
    pass


class SceneAnalysisValidator:

    VALID_MEDIA_TYPES = {
        "video",
        "image",
        "either"
    }

    VALID_SHOTS = {
        "wide",
        "medium",
        "close_up",
        "aerial",
        "detail",
        "any"
    }

    VALID_MOTIONS = {
        "static",
        "slow",
        "normal",
        "fast",
        "any"
    }


    def validate(self, scene):

        self._validate_time(
            scene
        )

        self._validate_analysis(
            scene
        )

        self._validate_search(
            scene
        )

        self._validate_media(
            scene
        )

        return True


    def _validate_time(self, scene):

        if not scene.scene_id:

            raise SceneValidationError(
                "scene_id is required."
            )


        if scene.start < 0:

            raise SceneValidationError(
                f"{scene.scene_id}: "
                "start cannot be negative."
            )


        if scene.end <= scene.start:

            raise SceneValidationError(
                f"{scene.scene_id}: "
                "end must be greater than start."
            )


        calculated_duration = (
            scene.end
            - scene.start
        )


        if abs(
            calculated_duration
            - scene.duration
        ) > 0.01:

            raise SceneValidationError(
                f"{scene.scene_id}: "
                "duration does not match "
                "start/end."
            )


        if not scene.dialogue.strip():

            raise SceneValidationError(
                f"{scene.scene_id}: "
                "dialogue is empty."
            )


    def _validate_analysis(
        self,
        scene
    ):

        analysis = scene.analysis


        required_fields = {

            "context": analysis.context,

            "subject": analysis.subject,

            "action": analysis.action,

            "location": analysis.location,

            "mood": analysis.mood
        }


        for field_name, value in (
            required_fields.items()
        ):

            if not value.strip():

                raise SceneValidationError(
                    f"{scene.scene_id}: "
                    f"{field_name} is empty."
                )


        if (
            analysis.shot
            not in self.VALID_SHOTS
        ):

            raise SceneValidationError(
                f"{scene.scene_id}: "
                f"invalid shot: "
                f"{analysis.shot}"
            )


        if (
            analysis.motion
            not in self.VALID_MOTIONS
        ):

            raise SceneValidationError(
                f"{scene.scene_id}: "
                f"invalid motion: "
                f"{analysis.motion}"
            )


    def _validate_search(
        self,
        scene
    ):

        search = scene.search


        if not search.primary_keyword.strip():

            raise SceneValidationError(
                f"{scene.scene_id}: "
                "primary_keyword is empty."
            )


        if not search.keywords:

            raise SceneValidationError(
                f"{scene.scene_id}: "
                "keywords list is empty."
            )


        cleaned_keywords = []


        for keyword in search.keywords:

            keyword = keyword.strip()

            if (
                keyword
                and keyword
                not in cleaned_keywords
            ):

                cleaned_keywords.append(
                    keyword
                )


        if (
            search.primary_keyword
            not in cleaned_keywords
        ):

            cleaned_keywords.insert(
                0,
                search.primary_keyword
            )


        search.keywords = (
            cleaned_keywords
        )


    def _validate_media(
        self,
        scene
    ):

        media_type = (
            scene.media.preferred_type
        )


        if (
            media_type
            not in self.VALID_MEDIA_TYPES
        ):

            raise SceneValidationError(
                f"{scene.scene_id}: "
                f"invalid media type: "
                f"{media_type}"
            )