from abc import ABC, abstractmethod


class AIProviderError(Exception):
    pass


class BaseAIProvider(ABC):

    @abstractmethod
    def analyze_scene(
        self,
        scene,
        system_prompt
    ):
        """
        Analyze one scene.

        Must return a Python dictionary
        matching the required scene-analysis schema.
        """

        raise NotImplementedError