import json
import logging
import os
from difflib import SequenceMatcher
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import ValidationError

from backend.schemas import ExtractionResult

logger = logging.getLogger(__name__)


def _fuzzy_match_speaker(name: str, valid_speakers: list[str], threshold: float = 0.6) -> str | None:
    """Find the best matching speaker using fuzzy string matching.

    Returns the matched speaker name if similarity exceeds threshold, otherwise None.
    """
    if not name or not valid_speakers:
        return None

    name_lower = name.lower().strip()
    best_match = None
    best_score = 0.0

    for speaker in valid_speakers:
        speaker_lower = speaker.lower()
        # Exact match (case-insensitive)
        if name_lower == speaker_lower:
            return speaker

        # Check if name is a substring (e.g., "Adrian" matches "Adrian Puchacki")
        if name_lower in speaker_lower or speaker_lower in name_lower:
            score = len(name_lower) / max(len(speaker_lower), 1)
            if score > best_score:
                best_score = score
                best_match = speaker
                continue

        # Fuzzy matching
        score = SequenceMatcher(None, name_lower, speaker_lower).ratio()
        if score > best_score:
            best_score = score
            best_match = speaker

    if best_score >= threshold:
        return best_match
    return None


class LLMExtractor:
    @staticmethod
    def _llm_chain(transcript: str, valid_speakers: list[str] | None = None) -> ExtractionResult:
        provider = os.getenv("LLM_PROVIDER", "azure").lower()

        if provider == "azure":
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

            if not azure_deployment:
                raise RuntimeError(
                    "AZURE_OPENAI_DEPLOYMENT environment variable must be set to use Azure OpenAI."
                )
            if not azure_endpoint:
                raise RuntimeError(
                    "AZURE_OPENAI_ENDPOINT environment variable must be set to use Azure OpenAI."
                )

            llm = AzureChatOpenAI(
                api_version=api_version,
                azure_deployment=azure_deployment,
                azure_endpoint=azure_endpoint,
                temperature=0.1,
            )
        else:
            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.1)

        # Build speaker constraint for the prompt
        speaker_constraint = ""
        if valid_speakers:
            speaker_list = ", ".join(f'"{s}"' for s in valid_speakers)
            speaker_constraint = (
                f"\n\nIMPORTANT: The only valid assignees are the identified speakers from the meeting: [{speaker_list}]. "
                "assignee_name MUST be exactly one of these names or null. Do NOT use any other names."
            )

        system = (
            "You are an Agile Product Owner. Extract Jira-ready tasks from meeting transcripts. "
            "Return STRICT JSON following the schema:\n"
            "{{\n  \"tasks\": [\n    {{\n      \"summary\": str, \"description\": str, "
            "\"issue_type\": one of [\"Story\",\"Task\",\"Bug\",\"Spike\"], "
            "\"assignee_name\": str|null, \"priority\": one of [\"Low\",\"Medium\",\"High\"], "
            "\"story_points\": int|null, \"labels\": [str], \"links\": [str], \"quotes\": [str]\n    }}\n  ]\n}}"
            "\nIf no assignee, set null. Use quotes to include short verbatim snippets from the transcript that justify each task."
            f"{speaker_constraint}"
        )
        human = f"Transcript:\n{transcript}\n---\nReturn only JSON, no prose."
        messages = [SystemMessage(content=system), HumanMessage(content=human)]

        raw_response = llm.invoke(messages).content
        result = LLMExtractor._parse_or_repair_response(llm, raw_response)
        # Post-process to validate and normalize assignee names
        return LLMExtractor._validate_assignees(result, valid_speakers)

    @staticmethod
    def _validate_assignees(result: ExtractionResult, valid_speakers: list[str] | None) -> ExtractionResult:
        """Ensure all assignee_name values are valid speakers or set to None."""
        if not valid_speakers:
            return result

        for task in result.tasks:
            if task.assignee_name:
                matched = _fuzzy_match_speaker(task.assignee_name, valid_speakers)
                if matched:
                    task.assignee_name = matched
                else:
                    logger.warning(
                        "Assignee '%s' not found in valid speakers %s, setting to None",
                        task.assignee_name,
                        valid_speakers,
                    )
                    task.assignee_name = None
        return result

    @staticmethod
    def _parse_or_repair_response(llm, payload: str) -> ExtractionResult:
        try:
            data = json.loads(payload)
            return ExtractionResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("LLM payload failed validation. Attempting repair.", exc_info=exc)
            repair_messages = [
                SystemMessage(
                    content=(
                        "You repair JSON to satisfy a strict Pydantic schema. "
                        "Return valid JSON only, no prose."
                    )
                ),
                HumanMessage(
                    content=(
                        "Original completion:\n```"
                        f"{payload}"
                        "```"
                        "\nValidation error:\n```"
                        f"{exc}"
                        "```"
                        "\nReturn JSON matching the schema that passes validation."
                    )
                ),
            ]
            repaired = llm.invoke(repair_messages).content
            data = json.loads(repaired)
            return ExtractionResult.model_validate(data)

    def extract(self, transcript: str) -> ExtractionResult:
        return self._llm_chain(transcript)
