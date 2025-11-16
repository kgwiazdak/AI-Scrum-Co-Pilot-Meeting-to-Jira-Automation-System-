from __future__ import annotations

import pytest

from backend.application.services.push_to_jira import PushTasksToJiraService
from backend.infrastructure.jira import JiraClientError, JiraIssue


class FakeRepo:
    def __init__(self, tasks: list[dict]) -> None:
        self._tasks = tasks
        self.marked: list[tuple[str, str, str | None]] = []

    def get_tasks_by_ids(self, ids):
        return [task for task in self._tasks if task["id"] in ids]

    def mark_task_pushed_to_jira(self, task_id: str, *, issue_key: str, issue_url: str | None) -> None:
        self.marked.append((task_id, issue_key, issue_url))


class FakeJiraClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.counter = 0

    def create_issue(self, **payload):
        self.counter += 1
        self.calls.append(payload)
        key = f"SCRUM-{self.counter}"
        return JiraIssue(key=key, url=f"https://example.atlassian.net/browse/{key}")


def test_pushes_tasks_and_marks_repository():
    task = {
        "id": "task-1",
        "summary": "Implement login",
        "description": "Need SSO",
        "issueType": "Story",
        "priority": "High",
        "labels": ["backend"],
        "storyPoints": 5,
        "assigneeAccountId": "user-123",
        "sourceQuote": "We must finish login",
    }
    repo = FakeRepo([task])
    jira = FakeJiraClient()
    service = PushTasksToJiraService(repo=repo, jira_client=jira)

    result = service.push([task["id"]])

    assert result.pushed == 1
    assert result.skipped == 0
    assert repo.marked == [("task-1", "SCRUM-1", "https://example.atlassian.net/browse/SCRUM-1")]
    assert jira.calls[0]["summary"] == "Implement login"
    assert jira.calls[0]["assignee_account_id"] == "user-123"


def test_skips_tasks_already_linked_to_jira():
    task = {
        "id": "task-1",
        "summary": "Done task",
        "jiraIssueKey": "SCRUM-9",
    }
    repo = FakeRepo([task])
    jira = FakeJiraClient()
    service = PushTasksToJiraService(repo=repo, jira_client=jira)

    result = service.push([task["id"]])

    assert result.pushed == 0
    assert result.skipped == 1
    assert repo.marked == []
    assert jira.calls == []


def test_raises_when_jira_rejects_request():
    class FailJiraClient(FakeJiraClient):
        def create_issue(self, **payload):
            raise JiraClientError("boom")

    task = {"id": "task-1", "summary": "Broken"}
    repo = FakeRepo([task])
    jira = FailJiraClient()
    service = PushTasksToJiraService(repo=repo, jira_client=jira)

    with pytest.raises(JiraClientError):
        service.push([task["id"]])
    assert repo.marked == []


def test_sanitizes_labels_before_pushing():
    task = {
        "id": "task-1",
        "summary": "Label cleanup",
        "labels": ["Data ingestion", " model drift ", "QA&Ops"],
    }
    repo = FakeRepo([task])
    jira = FakeJiraClient()
    service = PushTasksToJiraService(repo=repo, jira_client=jira)

    service.push([task["id"]])

    assert jira.calls[0]["labels"] == ["data-ingestion", "model-drift", "qa-ops"]
