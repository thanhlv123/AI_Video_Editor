class ManualSelectorError(Exception):
    pass


class ManualSelector:

    def select(
        self,
        ranked,
        choice
    ):

        if not ranked:
            raise ManualSelectorError(
                "No candidates available."
            )

        try:
            choice = int(choice)

        except (TypeError, ValueError):
            raise ManualSelectorError(
                "Choice must be a number."
            )

        if choice < 1 or choice > len(ranked):
            raise ManualSelectorError(
                f"Choice must be between "
                f"1 and {len(ranked)}."
            )

        selected = dict(
            ranked[choice - 1]
        )

        return selected