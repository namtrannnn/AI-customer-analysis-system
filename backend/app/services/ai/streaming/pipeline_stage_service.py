from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass(slots=True)
class StageContext:
    session_id: str
    job_id: str
    frame_index: int
    data: Dict[str, Any] = field(default_factory=dict)


class PipelineStage(ABC):
    name: str

    @abstractmethod
    def process(self, context: StageContext) -> StageContext:
        raise NotImplementedError


class CallableStage(PipelineStage):
    def __init__(self, name: str, handler) -> None:
        self.name = name
        self._handler = handler

    def process(self, context: StageContext) -> StageContext:
        result = self._handler(context)
        if result is None:
            return context
        if not isinstance(result, StageContext):
            raise TypeError(f"stage {self.name} must return StageContext")
        return result


class IndependentStagePipeline:
    """AI-03: chạy các stage độc lập, dễ test/thay thế từng stage."""

    def __init__(self, stages: Iterable[PipelineStage]) -> None:
        self.stages: List[PipelineStage] = list(stages)

    def process(self, context: StageContext) -> StageContext:
        for stage in self.stages:
            try:
                context = stage.process(context)
            except Exception as exc:
                context.data["failed_stage"] = stage.name
                context.data["stage_error"] = f"{type(exc).__name__}: {exc}"
                raise
        return context
