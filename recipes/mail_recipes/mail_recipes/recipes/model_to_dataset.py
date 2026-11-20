"""Save a trained spaCy text classifier's answers on texts as annotations.

The answers are saved the way `llm_to_dataset` saves an LLM's: as the
built-in text classification task saves a person's, credited to their own
session. So the model becomes one more annotator, and the built-in review,
the annotation dashboard and exports compare it with the LLM and people
text by text, which the train action's overall scores don't.

Each answer's score, the probability the model gave its top label, goes in
the example's meta, so a threshold can be chosen later from the saved
answers.
"""

import time
from typing import Any, Iterable, Literal, Union, cast

from ellf_recipes_sdk import (
    Dataset,
    Input,
    IntProps,
    Labels,
    LabelScheme,
    Model,
    Props,
    TextProps,
    action_recipe,
    props,
)

from .llm_to_dataset import already_answered, save_answers


def model_answer(cats: dict[str, float], exclusive: bool, threshold: float = 0.5) -> tuple[list[str], float]:
    """The labels the model gives and the top label's score.

    With exclusive labels the answer is the top label alone. Otherwise it is
    every label scored at `threshold` or above, which may be none.
    """
    if not cats:
        return [], 0.0
    top = max(cats, key=lambda name: cats[name])
    if exclusive:
        return [top], cats[top]
    return [name for name, score in cats.items() if score >= threshold], cats[top]


@action_recipe(
    title="Label Texts with a Trained Model",
    description="Save a trained spaCy text classifier's answers on texts to a dataset as another annotator's, to compare with an LLM's and people's in the built-in review, the annotation dashboard and exports.",
    category="data",
    field_props={
        # fmt: off
        "input": TextProps(
            title="Input data",
            description="The texts, as people annotate them.",
        ),
        "model": Props(
            title="Trained model",
            description="A model asset from the train action, with a text classifier.",
        ),
        "label": props.label_scheme_for("BILLING, TECHNICAL, ..."),
        "output": Props(
            title="Output dataset",
            description="Dataset to save the model's answers to.",
        ),
        "session": TextProps(
            title="Annotator name",
            description="Who the answers are credited to in the review and the dashboard.",
        ),
        "batch_size": IntProps(
            title="Save every",
            description="Answers are saved after this many texts, and a rerun skips texts that already have this annotator's answer.",
            min=1,
        ),
        # fmt: on
    },
    cli_names={"label-list": "label", "label-labels": "label-scheme"},
)
def model_to_dataset(
    *,
    input: Input[Literal["text"]],
    model: Model,
    label: Union[list[str], Labels],
    output: Dataset[Literal["textcat"]],
    session: str = "model",
    batch_size: int = 1000,
) -> None:
    """Save the model's answer on every text to ``output``.

    The examples are built for the labels in ``label``, the same as the
    annotation task's, so the model's answer and a person's on the same text
    are versions of one example. The model's labels must all be among them.
    A pipeline with ``textcat`` gives one label per text; one with only
    ``textcat_multilabel`` gives every label scored 0.5 or above.

    Contract:
        Raises:
            ValueError: If there are no labels, the pipeline has no text
                classifier, or the model has a label that ``label`` lacks.
            Errors from ``Model.load()`` and database errors from
                ``save_examples()`` (not caught).
    """
    names = LabelScheme.resolve(label).names()
    if not names:
        raise ValueError("No labels to save answers with.")
    nlp = model.load()
    if "textcat" in nlp.pipe_names:
        exclusive, component = True, "textcat"
    elif "textcat_multilabel" in nlp.pipe_names:
        exclusive, component = False, "textcat_multilabel"
    else:
        raise ValueError(f"The model's pipeline {nlp.pipe_names} has no text classifier.")
    unknown = sorted(set(cast(Any, nlp.get_pipe(component)).labels) - set(names))
    if unknown:
        raise ValueError(f"The model has labels the scheme lacks: {', '.join(unknown)}")
    rows = list(cast(Iterable[dict[str, Any]], input.load(rehash=True, dedup=True, input_key="text")))
    done = already_answered(output.name, session)
    todo = [eg for eg in rows if eg["text"] not in done]
    if done:
        print(f"{len(rows) - len(todo)} of {len(rows)} texts already have {session}'s answer and are skipped")
    seconds = 0.0
    for start in range(0, len(todo), batch_size):
        batch = todo[start : start + batch_size]
        began = time.perf_counter()
        docs = list(nlp.pipe(eg["text"] for eg in batch))
        seconds += time.perf_counter() - began
        picked = []
        for eg, doc in zip(batch, docs):
            chosen, score = model_answer(doc.cats, exclusive)
            eg["meta"] = {**(eg.get("meta") or {}), "score": round(score, 4)}
            picked.append((eg, chosen, None))
        save_answers(picked, names, output=output.name, session=session)
        print(f"Saved {start + len(batch)} of {len(todo)} answers")
    if todo:
        print(f"The model labelled {len(todo)} texts in {seconds:.1f} s ({1000 * seconds / len(todo):.1f} s per 1,000)")
    print(f"Saved {len(todo)} of the model's answers to '{output.name}'")
