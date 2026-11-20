import json
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import pytest
from prodigy.components.db import Database
from prodigy.structured_types import TextcatChoiceExample, TextcatExample

from ellf_recipes_sdk import Dataset, Input, LabelScheme
from mail_recipes.recipes import llm_to_dataset as module
from mail_recipes.recipes.llm_to_dataset import classify, llm_to_dataset, post_with_retry, read_reply


def _input(tmp_path: Path, texts: list[str]) -> Input:
    path = tmp_path / "texts.jsonl"
    path.write_text("".join(json.dumps({"text": t}) + "\n" for t in texts), encoding="utf-8")
    return Input(
        id=uuid.uuid4(),
        cluster_id=uuid.uuid4(),
        name="eval-texts",
        version="0.0.0",
        path=str(path),
        meta={"loader": "jsonl"},
    )


def _output() -> Dataset:
    return Dataset(id=uuid.uuid4(), name="eval_llm", cluster_id=uuid.uuid4())


def _answers(monkeypatch, answers: dict[str, Optional[list[str]]]) -> None:
    monkeypatch.setattr(module, "classify", lambda eg, scheme, exclusive, **kw: answers[eg["text"]])


def _sessions(db: Database, name: str) -> set[str]:
    return {session for session, _ in db.iter_st_dataset_session_examples(name)}


def test_saves_choice_answers_credited_to_the_llm(database: Database, tmp_path: Path, monkeypatch, capsys):
    _answers(monkeypatch, {"a": ["GREEN"], "b": ["RED"], "c": None})
    llm_to_dataset(input=_input(tmp_path, ["a", "b", "c"]), label=["GREEN", "RED"], output=_output(), labels_exclusive=True)
    saved = {eg.input.text: eg for eg in database.get_st_dataset_examples("eval_llm")}
    assert set(saved) == {"a", "b"}
    assert all(isinstance(eg, TextcatChoiceExample) for eg in saved.values())
    assert saved["b"].user_anns is not None and saved["b"].user_anns.accept == ["RED"]
    assert [o.id for o in saved["a"].server_anns.options] == ["GREEN", "RED"]
    assert _sessions(database, "eval_llm") == {"LLM"}
    assert "1 of 3 texts have no usable answer" in capsys.readouterr().out


def test_one_label_saves_accept_or_reject(database: Database, tmp_path: Path, monkeypatch):
    _answers(monkeypatch, {"a": ["FRAUD"], "b": []})
    llm_to_dataset(input=_input(tmp_path, ["a", "b"]), label=["FRAUD"], output=_output())
    saved = {eg.input.text: eg for eg in database.get_st_dataset_examples("eval_llm")}
    assert all(isinstance(eg, TextcatExample) for eg in saved.values())
    assert saved["a"].answer == "accept" and saved["b"].answer == "reject"


def test_annotator_name_can_be_changed(database: Database, tmp_path: Path, monkeypatch):
    _answers(monkeypatch, {"a": ["GREEN"]})
    llm_to_dataset(input=_input(tmp_path, ["a"]), label=["GREEN", "RED"], output=_output(), session="gpt-prompt-v2")
    assert _sessions(database, "eval_llm") == {"gpt-prompt-v2"}


def _client(reply: str, seen: list[dict[str, Any]]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    return httpx.Client(base_url="https://llm.test/v1", transport=httpx.MockTransport(handle))


SCHEME = LabelScheme.from_json({"GREEN": {"description": "Clearly yes."}, "RED": {"description": "Clearly no."}})


@pytest.mark.parametrize(
    "reply,exclusive,expected",
    [
        ("GREEN", True, ["GREEN"]),
        (" RED ", True, ["RED"]),
        ("GREEN, RED", False, ["GREEN", "RED"]),
        ("GREEN, RED", True, None),
        ("NONE", False, []),
        ("Probably green", True, None),
        ("green", True, ["GREEN"]),
        ("`Red`.", True, ["RED"]),
        ("None.", False, []),
        ("GREEN, PURPLE", True, ["GREEN"]),
        ("green, GREEN", True, ["GREEN"]),
    ],
)
def test_default_classify_reads_the_reply(reply, exclusive, expected):
    seen: list[dict[str, Any]] = []
    eg = {"text": "Do you have a licence? Yes."}
    got = classify(eg, SCHEME, exclusive, client=_client(reply, seen), model="m", instructions="Grade the reply.")
    assert got == expected
    prompt = seen[0]["messages"][0]["content"]
    assert seen[0]["model"] == "m"
    assert "Grade the reply." in prompt and "- GREEN: Clearly yes." in prompt and eg["text"] in prompt
    assert "reasoning_effort" not in seen[0]


def test_classify_can_turn_thinking_off():
    seen: list[dict[str, Any]] = []
    eg = {"text": "Do you have a licence? Yes."}
    client = _client("GREEN", seen)
    got = classify(eg, SCHEME, True, client=client, model="m", instructions="", reasoning_effort="none")
    assert got == ["GREEN"]
    assert seen[0]["reasoning_effort"] == "none"


class FakeOutput:
    """Stands in for an Output asset: keeps what the action writes."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.rows: list[dict[str, Any]] = []

    def write_jsonl(self, rows) -> int:
        self.rows = list(rows)
        return len(self.rows)


def _records(tmp_path: Path, labels: list[Any]) -> Input:
    path = tmp_path / "records.jsonl"
    rows = [{"text": f"t{i}", "meta": {"id": i, "reference_label": label}} for i, label in enumerate(labels)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return Input(
        id=uuid.uuid4(),
        cluster_id=uuid.uuid4(),
        name="eval-records",
        version="0.0.0",
        path=str(path),
        meta={"loader": "jsonl"},
    )


def _no_calls(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("classify shouldn't be called for logged labels")

    monkeypatch.setattr(module, "classify", fail)


def test_reads_logged_labels_without_calling_the_llm(database: Database, tmp_path: Path, monkeypatch, capsys):
    _no_calls(monkeypatch)
    records = _records(tmp_path, ["GREEN", "RED", "PURPLE", None])
    llm_to_dataset(input=records, label=["GREEN", "RED"], output=_output(), labels_exclusive=True, llm_label_key="reference_label")
    saved = {eg.input.text: eg.user_anns.accept for eg in database.get_st_dataset_examples("eval_llm")}
    assert saved == {"t0": ["GREEN"], "t1": ["RED"]}
    out = capsys.readouterr().out
    assert "2 of 4 texts have no usable answer" in out
    assert "annotators will see them" in out


def test_logged_labels_for_one_label(database: Database, tmp_path: Path, monkeypatch):
    _no_calls(monkeypatch)
    records = _records(tmp_path, ["FRAUD", "OK", ["FRAUD", "OTHER"]])
    llm_to_dataset(input=records, label=["FRAUD"], output=_output(), llm_label_key="reference_label")
    saved = {eg.input.text: eg.answer for eg in database.get_st_dataset_examples("eval_llm")}
    assert saved == {"t0": "accept", "t1": "reject", "t2": "accept"}


def test_samples_by_label_with_weights_and_a_blind_asset(database: Database, tmp_path: Path, monkeypatch):
    _no_calls(monkeypatch)
    records = _records(tmp_path, ["RED"] * 10 + ["GREEN"] * 90)
    blind = FakeOutput("eval-blind")
    llm_to_dataset(
        input=records,
        label=["GREEN", "RED"],
        output=_output(),
        labels_exclusive=True,
        llm_label_key="reference_label",
        sample_size=20,
        min_per_label=5,
        blind=blind,  # type: ignore[arg-type]
    )
    saved = database.get_st_dataset_examples("eval_llm")
    by_label: dict[str, list[float]] = {}
    for eg in saved:
        by_label.setdefault(eg.user_anns.accept[0], []).append(eg.meta["weight"])
    assert {k: len(v) for k, v in by_label.items()} == {"GREEN": 18, "RED": 5}
    assert by_label["GREEN"] == pytest.approx([90 / 18] * 18)
    assert by_label["RED"] == pytest.approx([10 / 5] * 5)
    assert sum(w for ws in by_label.values() for w in ws) == pytest.approx(100)
    assert {r["text"] for r in blind.rows} == {eg.input.text for eg in saved}
    assert all("reference_label" not in r["meta"] and "weight" not in r["meta"] for r in blind.rows)
    assert all("id" in r["meta"] for r in blind.rows)


def test_without_sampling_every_text_is_saved_unweighted(database: Database, tmp_path: Path, monkeypatch):
    _no_calls(monkeypatch)
    llm_to_dataset(input=_records(tmp_path, ["GREEN", "RED"]), label=["GREEN", "RED"], output=_output(), llm_label_key="reference_label")
    assert all("weight" not in eg.meta for eg in database.get_st_dataset_examples("eval_llm"))


def test_refuses_when_no_text_has_an_answer(database: Database, tmp_path: Path, monkeypatch):
    _no_calls(monkeypatch)
    with pytest.raises(ValueError, match="No text has a usable answer"):
        llm_to_dataset(input=_records(tmp_path, ["PURPLE"]), label=["GREEN", "RED"], output=_output(), llm_label_key="reference_label")


@pytest.mark.parametrize(
    "reply,expected",
    [("**RED**", ["RED"]), ("'green'", ["GREEN"]), ("", None), ("PURPLE", None)],
)
def test_read_reply(reply, expected):
    assert read_reply(reply, ["GREEN", "RED"], True) == expected


def _flaky(outcomes: list[Any]) -> tuple[httpx.Client, list[int]]:
    """A client whose replies follow `outcomes`: a status code, or an exception to raise."""
    calls: list[int] = []

    def handle(request: httpx.Request) -> httpx.Response:
        outcome = outcomes[len(calls)]
        calls.append(1)
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, json={"choices": [{"message": {"content": "GREEN"}}]})

    return httpx.Client(base_url="https://llm.test/v1", transport=httpx.MockTransport(handle)), calls


@pytest.fixture()
def no_backoff(monkeypatch):
    monkeypatch.setattr(module.time, "sleep", lambda s: None)


def test_retries_timeouts_and_server_errors(no_backoff):
    client, calls = _flaky([httpx.ReadTimeout("slow"), 503, 200])
    assert post_with_retry(client, "/chat/completions", {}).status_code == 200
    assert len(calls) == 3


def test_gives_up_after_the_retries(no_backoff):
    client, calls = _flaky([503] * (module.RETRIES + 1))
    with pytest.raises(httpx.HTTPStatusError):
        post_with_retry(client, "/chat/completions", {})
    assert len(calls) == module.RETRIES + 1


def test_a_client_error_is_not_retried(no_backoff):
    client, calls = _flaky([404, 200])
    with pytest.raises(httpx.HTTPStatusError):
        post_with_retry(client, "/chat/completions", {})
    assert len(calls) == 1


def test_a_stopped_run_keeps_its_batches_and_a_rerun_carries_on(database: Database, tmp_path: Path, monkeypatch):
    texts = [f"t{i}" for i in range(7)]
    asked: list[str] = []

    def fails_after_five(eg, scheme, exclusive, **kw):
        if len(asked) == 5:
            raise httpx.ConnectError("gone")
        asked.append(eg["text"])
        return ["GREEN"]

    monkeypatch.setattr(module, "classify", fails_after_five)
    with pytest.raises(httpx.ConnectError):
        llm_to_dataset(input=_input(tmp_path, texts), label=["GREEN", "RED"], output=_output(), batch_size=2)
    first = {eg.input.text for eg in database.get_st_dataset_examples("eval_llm")}
    assert len(first) == 4  # two full batches; the third failed part-way

    asked.clear()
    _answers(monkeypatch, {t: ["RED"] for t in texts})
    llm_to_dataset(input=_input(tmp_path, texts), label=["GREEN", "RED"], output=_output(), batch_size=2)
    saved = database.get_st_dataset_examples("eval_llm")
    assert sorted(eg.input.text for eg in saved) == texts
    assert {eg.input.text for eg in saved if eg.user_anns.accept == ["GREEN"]} == first


def test_requests_can_run_at_once(database: Database, tmp_path: Path, monkeypatch):
    texts = [f"t{i}" for i in range(20)]
    _answers(monkeypatch, {t: ["GREEN"] if int(t[1:]) % 2 else ["RED"] for t in texts})
    llm_to_dataset(input=_input(tmp_path, texts), label=["GREEN", "RED"], output=_output(), workers=4, batch_size=6)
    saved = {eg.input.text: eg.user_anns.accept for eg in database.get_st_dataset_examples("eval_llm")}
    assert saved == {t: ["GREEN"] if int(t[1:]) % 2 else ["RED"] for t in texts}
