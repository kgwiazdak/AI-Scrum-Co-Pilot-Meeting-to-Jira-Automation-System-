import json
import logging
import os
from typing import Any, Dict

from openai import OpenAI

from .schemas import ExtractionResult


LOGGER = logging.getLogger(__name__)


class Extractor:
    """Generate Jira-ready tasks using OpenAI's gpt-oss-safeguard-20b model."""

    _DEFAULT_MODEL = "gpt-oss-safeguard-20b"

    def __init__(self) -> None:
        self._client = OpenAI()
        self._model = os.getenv("OPENAI_EXTRACTION_MODEL", self._DEFAULT_MODEL)

    @staticmethod
    def _response_schema() -> Dict[str, Any]:
        return {
            "name": "meeting_tasks",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "minLength": 3,
                                    "maxLength": 300,
                                },
                                "description": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                                "issue_type": {
                                    "type": "string",
                                    "enum": ["Story", "Task", "Bug", "Spike"],
                                },
                                "assignee_name": {
                                    "type": ["string", "null"],
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["Low", "Medium", "High"],
                                },
                                "story_points": {
                                    "type": ["integer", "null"],
                                    "minimum": 0,
                                    "maximum": 100,
                                },
                                "labels": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "links": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "quotes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "summary",
                                "description",
                                "issue_type",
                                "assignee_name",
                                "priority",
                                "story_points",
                                "labels",
                                "links",
                                "quotes",
                            ],
                        },
                    }
                },
                "required": ["tasks"],
            },
        }

    def _build_prompt(self, transcript: str) -> list[dict[str, Any]]:
        system_message = (
            "You are an Agile Product Owner assisting with Jira backlog preparation. "
            "Extract actionable work items from the meeting transcript. "
            "For each task, craft a concise summary, detailed description, and include "
            "supporting direct quotes from the transcript. Only emit JSON that fits the schema."
        )
        user_message = (
            "Return Jira tasks for the following meeting transcript."
            "\n\nTranscript:\n"
            f"{transcript}"
        )
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

    def _invoke_model(self, transcript: str) -> Dict[str, Any]:
        messages = self._build_prompt(transcript)
        response = self._client.responses.create(
            model=self._model,
            input=messages,
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "json_schema": self._response_schema(),
            },
        )

        try:
            content = response.output[0].content[0].text
        except (AttributeError, IndexError, KeyError) as exc:
            LOGGER.exception("Unexpected response structure from OpenAI: %s", response)
            raise RuntimeError("Failed to extract tasks from model response") from exc

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            LOGGER.exception("Model returned invalid JSON: %s", content)
            raise RuntimeError("Model did not return valid JSON") from exc

    def extract_tasks_llm(self, transcript: str) -> ExtractionResult:
        data = self._invoke_model(transcript)
        return ExtractionResult(**data)
