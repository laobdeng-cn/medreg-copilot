from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from medreg.modules.agent.schemas import ModelDraft, ModelMode


@dataclass(frozen=True)
class DraftGeneration:
    draft: ModelDraft
    provider: str
    model: str
    mode: ModelMode
    error: str | None = None


class DraftModel(Protocol):
    provider: str
    model: str
    configured: bool

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: ModelDraft,
    ) -> DraftGeneration: ...


class DeterministicDraftModel:
    provider = "deterministic"
    model = "controlled-template-v1"
    configured = False

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: ModelDraft,
    ) -> DraftGeneration:
        return DraftGeneration(
            draft=fallback,
            provider=self.provider,
            model=self.model,
            mode=ModelMode.DETERMINISTIC,
        )


class DeepSeekDraftModel:
    provider = "deepseek"
    configured = True

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: ModelDraft,
    ) -> DraftGeneration:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "thinking": {"type": "disabled"},
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                        "max_tokens": 2600,
                        "stream": False,
                    },
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            draft = ModelDraft.model_validate(json.loads(self._strip_fence(content)))
            if not draft.title.strip() or not draft.sections:
                raise ValueError("Model returned an empty draft")
            return DraftGeneration(
                draft=draft,
                provider=self.provider,
                model=self.model,
                mode=ModelMode.LIVE,
            )
        except Exception as exc:
            return DraftGeneration(
                draft=fallback,
                provider=self.provider,
                model=self.model,
                mode=ModelMode.FALLBACK,
                error=f"{type(exc).__name__}: {exc}"[:1000],
            )

    @staticmethod
    def _strip_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return stripped
