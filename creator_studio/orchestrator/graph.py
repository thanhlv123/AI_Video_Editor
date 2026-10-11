"""Validated dependency graph with lexical, registration-independent ordering."""
from dataclasses import dataclass
from types import MappingProxyType
import heapq
import re
from .contracts import Stage
from .repository import PreflightError


class StageDeclarationError(PreflightError):
    """Controlled run abort; never an engine result or retryable failure."""
    def __init__(self, stage_id, field):
        super().__init__("stage_declaration_changed")
        self.diagnostic.stage_id = stage_id
        self.diagnostic.context = [field]


@dataclass(frozen=True)
class RegisteredStage:
    stage_id: str
    stage_version: str
    dependencies: tuple[str, ...]
    engine: Stage

    def __getattr__(self, name):
        return getattr(self.engine, name)


class StageGraph:
    def __init__(self):
        self._stages = {}
        self._active = False

    @property
    def stages(self):
        return MappingProxyType(self._stages)

    def preflight(self):
        for descriptor in self._stages.values():
            for field in ("stage_id", "stage_version", "dependencies"):
                try:
                    live = getattr(descriptor.engine, field)
                    if field == "dependencies":
                        live = tuple(live)
                    matches = live == getattr(descriptor, field)
                    if matches:
                        continue
                except Exception:
                    pass
                raise StageDeclarationError(descriptor.stage_id, field) from None

    def register(self, stage: Stage):
        if self._active:
            raise ValueError("Cannot register during execution")
        if (not re.fullmatch(r"[A-Za-z0-9_.:-]+", stage.stage_id)
                or not re.fullmatch(r"[A-Za-z0-9_.:+-]+", stage.stage_version)):
            raise ValueError("Stable stage ID and nonempty version required")
        if stage.stage_id in self.stages:
            raise ValueError("Duplicate stage")
        if len(set(stage.dependencies)) != len(stage.dependencies):
            raise ValueError("Duplicate dependency")
        self._stages[stage.stage_id] = RegisteredStage(stage.stage_id, stage.stage_version, tuple(stage.dependencies), stage)

    def order(self) -> tuple[str, ...]:
        degrees = {}
        children = {key: [] for key in self.stages}
        for key, stage in self.stages.items():
            degrees[key] = len(stage.dependencies)
            for dep in stage.dependencies:
                if dep not in self.stages:
                    raise ValueError("Missing dependency")
                children[dep].append(key)
        ready = [key for key, degree in degrees.items() if not degree]
        heapq.heapify(ready)
        result = []
        while ready:
            key = heapq.heappop(ready)
            result.append(key)
            for child in children[key]:
                degrees[child] -= 1
                if not degrees[child]:
                    heapq.heappush(ready, child)
        if len(result) != len(self.stages):
            raise ValueError("Dependency cycle")
        return tuple(result)
