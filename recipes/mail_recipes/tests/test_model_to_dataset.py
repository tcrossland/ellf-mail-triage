import json
import uuid
from pathlib import Path

import pytest
import spacy
from prodigy.components.db import Database
from prodigy.structured_types import TextcatChoiceExample
from spacy.training import Example

from ellf_recipes_sdk import Dataset, Input, Model
from mail_recipes.recipes.model_to_dataset import model_answer, model_to_dataset

TRAIN = [("pay the invoice", "ADMIN"), ("dinner on friday", "PERSONAL")] * 10


def _input(tmp_path: Path, texts: list[str]) -> Input:
    path = tmp_path / "texts.jsonl"
    rows = [{"text": t, "meta": {"id": str(i)}} for i, t in enumerate(texts)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return Input(
        id=uuid.uuid4(),
        cluster_id=uuid.uuid4(),
        name="eval-texts",
        version="0.0.0",
        path=str(path),
        meta={"loader": "jsonl"},
    )


def _output() -> Dataset:
    return Dataset(id=uuid.uuid4(), name="eval_model", cluster_id=uuid.uuid4())


def _model(tmp_path: Path, component: str = "textcat", labels: tuple[str, ...] = ("ADMIN", "PERSONAL")) -> Model:
    nlp = spacy.blank("en")
    textcat = nlp.add_pipe(component)
    for name in labels:
        textcat.add_label(name)
    examples = [
        Example.from_dict(nlp.make_doc(text), {"cats": {name: float(name == gold) for name in labels}})
        for text, gold in TRAIN
    ]
    optimizer = nlp.initialize(lambda: examples)
    for _ in range(20):
        nlp.update(examples, sgd=optimizer)
    path = tmp_path / "model"
    nlp.to_disk(path)
    return Model(id=uuid.uuid4(), cluster_id=uuid.uuid4(), name="kinds", version="0.1.0", path=str(path), meta={})


def test_model_answer_takes_the_top_label_when_exclusive():
    assert model_answer({"A": 0.2, "B": 0.7, "C": 0.1}, exclusive=True) == (["B"], 0.7)


def test_model_answer_takes_every_label_over_the_threshold_otherwise():
    assert model_answer({"A": 0.6, "B": 0.7, "C": 0.1}, exclusive=False) == (["A", "B"], 0.7)
    assert model_answer({"A": 0.2, "B": 0.3}, exclusive=False) == ([], 0.3)


def test_saves_one_answer_per_text_credited_to_the_model(database: Database, tmp_path: Path, capsys):
    model_to_dataset(
        input=_input(tmp_path, ["pay the invoice", "dinner on friday"]),
        model=_model(tmp_path),
        label=["ADMIN", "PERSONAL", "WORK"],
        output=_output(),
    )
    saved = {eg.input.text: eg for eg in database.get_st_dataset_examples("eval_model")}
    assert all(isinstance(eg, TextcatChoiceExample) for eg in saved.values())
    assert saved["pay the invoice"].user_anns.accept == ["ADMIN"]
    assert saved["dinner on friday"].user_anns.accept == ["PERSONAL"]
    # Options are the scheme's, as in the annotation task, not only the model's
    assert [o.id for o in saved["pay the invoice"].server_anns.options] == ["ADMIN", "PERSONAL", "WORK"]
    assert 0.5 < saved["pay the invoice"].meta["score"] <= 1.0
    assert saved["pay the invoice"].meta["id"] == "0"
    assert {s for s, _ in database.iter_st_dataset_session_examples("eval_model")} == {"model"}
    assert "s per 1,000" in capsys.readouterr().out


def test_a_rerun_skips_texts_already_answered(database: Database, tmp_path: Path, capsys):
    model = _model(tmp_path)
    kwargs = {"model": model, "label": ["ADMIN", "PERSONAL"], "output": _output(), "session": "spacy"}
    model_to_dataset(input=_input(tmp_path, ["pay the invoice"]), **kwargs)
    model_to_dataset(input=_input(tmp_path, ["pay the invoice", "dinner on friday"]), **kwargs)
    assert len(database.get_st_dataset_examples("eval_model")) == 2
    assert "1 of 2 texts already have spacy's answer" in capsys.readouterr().out


def test_refuses_a_model_with_labels_the_scheme_lacks(database: Database, tmp_path: Path):
    with pytest.raises(ValueError, match="PERSONAL"):
        model_to_dataset(input=_input(tmp_path, ["a"]), model=_model(tmp_path), label=["ADMIN"], output=_output())


def test_refuses_a_pipeline_without_a_text_classifier(database: Database, tmp_path: Path):
    path = tmp_path / "blank"
    spacy.blank("en").to_disk(path)
    model = Model(id=uuid.uuid4(), cluster_id=uuid.uuid4(), name="blank", version="0.1.0", path=str(path), meta={})
    with pytest.raises(ValueError, match="no text classifier"):
        model_to_dataset(input=_input(tmp_path, ["a"]), model=model, label=["ADMIN"], output=_output())
