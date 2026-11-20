"""Save an LLM classifier's answers on texts as annotations.

The answers are saved the way the built-in text classification task saves a
person's, credited to their own session, so the LLM becomes one more
annotator: the built-in review compares it with people, and the annotation
dashboard shows where they agree.

The answers come from one of two places: the LLM's labels already in each
record's meta, e.g. logged production decisions, or `classify`, which calls
the LLM. Customise `classify` to match your LLM: its prompt, the API it calls
and how its reply is read.

Optionally, the action draws a sample separately within each label the LLM
gave, so rare labels can be measured, records each sampled answer's weight
(texts with its label over sampled texts with its label) in its meta, and
writes the sampled texts without the LLM's labels for people to annotate.

Without a sample or a blind asset, answers are saved in batches as they
come, and a text that already has this annotator's answer in the output
dataset is skipped, so a run that stops can be started again and carries
on. Failed requests are retried a few times before the action stops.
"""

import random
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, Iterator, Literal, Optional, Union, cast

import httpx
import prodigy.recipes.textcat
from prodigy.structured_types import TextcatChoiceExample, TextcatExample

from ellf_recipes_sdk import (
    BoolProps,
    Dataset,
    Input,
    IntProps,
    Labels,
    LabelScheme,
    OptionalProps,
    Output,
    Props,
    Secret,
    TextProps,
    action_recipe,
    props,
    save_examples,
)


RETRIES = 3
"""Attempts after the first for a request that times out, can't connect or
gets a 5xx reply. A 4xx reply (a bad key or model) is not retried."""
BACKOFF = 2.0
"""Seconds before the first retry, doubled for each after."""


def post_with_retry(client: httpx.Client, path: str, body: dict[str, Any]) -> httpx.Response:
    """POST `body`, retrying transport errors and 5xx replies with backoff."""
    for attempt in range(RETRIES + 1):
        try:
            response = client.post(path, json=body)
            if response.status_code < 500 or attempt == RETRIES:
                response.raise_for_status()
                return response
        except httpx.TransportError:
            if attempt == RETRIES:
                raise
        delay = BACKOFF * 2**attempt
        print(f"Request failed; retrying in {delay:.0f} s ({attempt + 1} of {RETRIES})")
        time.sleep(delay)
    raise AssertionError("unreachable")


def read_reply(reply: str, names: list[str], exclusive: bool) -> Optional[list[str]]:
    """The labels named in a reply, matched without regard to case, quotes or
    trailing punctuation; [] for NONE; None if it names no label, or several
    when one is wanted. Parts that name no label are ignored."""

    def clean(part: str) -> str:
        return part.strip().strip("`'\"*.").strip().upper()

    if clean(reply) == "NONE":
        return []
    by_upper = {name.upper(): name for name in names}
    chosen = list(dict.fromkeys(by_upper[c] for c in map(clean, reply.split(",")) if c in by_upper))
    if not chosen or (exclusive and len(chosen) > 1):
        return None
    return chosen


def label_definitions(scheme: LabelScheme, details: bool = False) -> str:
    """The labels as the prompt lists them: each name with its description,
    and with `details` what not to give it and its examples, a text with no
    label being one that doesn't get it. The result is the same for every
    text, so an endpoint that caches the start of a prompt reuses it."""

    def indent(text: str) -> str:
        return "\n".join(f"    {line}" for line in text.strip().splitlines())

    def entry(spec: Any) -> str:
        lines = [f"- {spec.name}: {spec.description}" if spec.description else f"- {spec.name}"]
        if details:
            if spec.do_not_mark:
                lines.append(f"  Not {spec.name}: " + "; ".join(spec.do_not_mark))
            for example in spec.examples:
                kind = "of" if example.get("label") == spec.name else "that is not"
                lines.append(f"  Example {kind} {spec.name}:\n{indent(example['text'])}")
        return "\n".join(lines)

    return "\n".join(entry(spec) for spec in scheme.labels)


def classify(
    eg: dict[str, Any],
    scheme: LabelScheme,
    exclusive: bool,
    *,
    client: httpx.Client,
    model: str,
    instructions: str,
    reasoning_effort: Optional[str] = None,
    details: bool = False,
) -> Optional[list[str]]:
    """The labels the LLM gives a text, or None if it gave no usable answer.

    Customise this to match your LLM. The default asks an OpenAI-compatible
    chat endpoint to reply with label names. If the decisions are logged,
    return them instead, e.g. `return [eg["meta"]["llm_label"]]`.

    eg (dict): The example, with the text in `eg["text"]` and any meta.
    scheme (LabelScheme): The labels, with their definitions.
    exclusive (bool): Whether exactly one label applies.
    reasoning_effort (Optional[str]): Sent as `reasoning_effort` when set, e.g.
        "none" to turn off a model's thinking (Qwen3 through Ollama).
    details (bool): Also send each label's `do_not_mark` list and examples.
    RETURNS (Optional[list[str]]): The labels that apply, from `scheme`.
    """
    task = "the one label" if exclusive else "every label"
    prompt = (
        f"{instructions}\n\nLabels:\n{label_definitions(scheme, details)}\n\n"
        f"Reply with {task} that applies to the text, by name, separated by "
        f"commas, and nothing else. Reply NONE if none applies.\n\nText:\n{eg['text']}"
    )
    body: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    response = post_with_retry(client, "/chat/completions", body)
    reply = response.json()["choices"][0]["message"]["content"]
    return read_reply(reply, scheme.names(), exclusive)


def logged_labels(eg: dict[str, Any], key: str, names: list[str]) -> Optional[list[str]]:
    """The labels the LLM gave, from `eg["meta"][key]`: a label or a list of
    them. With one label X, any other value means X doesn't apply. None if the
    record has none, or none from the scheme."""
    value = (eg.get("meta") or {}).get(key)
    if value is None:
        return None
    values = [str(v) for v in (value if isinstance(value, list) else [value])]
    if len(names) == 1:
        return names if names[0] in values else []
    chosen = [v for v in values if v in names]
    return chosen or None


def stratum(chosen: list[str], names: list[str]) -> str:
    if len(names) == 1:
        return names[0] if chosen else f"NOT_{names[0]}"
    return "+".join(sorted(chosen)) or "NONE"


def draw_sample(
    answered: list[tuple[dict[str, Any], list[str]]],
    names: list[str],
    *,
    size: int,
    min_per_label: int,
    seed: int,
) -> list[tuple[dict[str, Any], list[str], float]]:
    """A sample drawn separately within each label the LLM gave: each gets its
    share of `size`, and at least `min_per_label`. Each sampled answer's
    weight is the number of texts with its label over the number sampled."""
    rng = random.Random(seed)
    strata: defaultdict[str, list[tuple[dict[str, Any], list[str]]]] = defaultdict(list)
    for eg, chosen in answered:
        strata[stratum(chosen, names)].append((eg, chosen))
    total = len(answered)
    sampled = []
    print("LLM label: texts, sampled, weight")
    for key in sorted(strata, key=lambda k: -len(strata[k])):
        group = strata[key]
        n = min(len(group), max(min_per_label, round(size * len(group) / total)))
        weight = len(group) / n
        sampled.extend((eg, chosen, weight) for eg, chosen in rng.sample(group, n))
        print(f"  {key}: {len(group)}, {n}, {weight:.2f}")
    rng.shuffle(sampled)
    return sampled


def answer_in_batches(
    rows: list[dict[str, Any]],
    answer: Callable[[dict[str, Any]], Optional[list[str]]],
    *,
    batch_size: int,
    workers: int,
) -> Iterator[list[tuple[dict[str, Any], Optional[list[str]]]]]:
    """Each batch of rows with its answers, in order, `workers` at a time."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            yield list(zip(batch, pool.map(answer, batch)))


def already_answered(dataset: str, session: str) -> set[str]:
    """The texts that already have `session`'s answer in `dataset`."""
    from prodigy.components.db import connect

    db = connect()
    if dataset not in db:
        return set()
    # Filtered here: with prodigy 2.0.0a18, session_ids=[session] matched none
    pairs = db.iter_st_dataset_session_examples(dataset)
    return {cast(Any, eg.input).text for name, eg in pairs if name == session}


def save_answers(
    picked: list[tuple[dict[str, Any], list[str], Optional[float]]],
    names: list[str],
    *,
    output: str,
    session: str,
) -> None:
    """Build the examples as the text classification task would and save them."""
    binary = len(names) == 1
    texts = [eg for eg, _, _ in picked]
    if binary:
        built = list(prodigy.recipes.textcat.add_labels_to_stream(texts, names))
    else:
        built = list(prodigy.recipes.textcat.add_label_options(texts, names))
    examples = []
    for eg, (_, chosen, weight) in zip(built, picked):
        if binary:
            eg["answer"] = "accept" if chosen else "reject"
        else:
            eg["accept"] = chosen
            eg["answer"] = "accept"
        if weight is not None:
            eg["meta"] = {**(eg.get("meta") or {}), "weight": weight}
        examples.append(eg)
    save_examples(
        output,
        examples,
        session_id=session,
        parse_as=TextcatExample if binary else TextcatChoiceExample,
        view_id="classification" if binary else "choice",
    )


@action_recipe(
    title="Label Texts with Your LLM",
    description="Save your LLM classifier's answers on texts to a dataset as another annotator's, to compare with people's in the built-in review and annotation dashboard. Takes logged LLM labels or calls the LLM, and can draw a sample by the LLM's label.",
    category="data",
    field_props={
        # fmt: off
        "input": TextProps(
            title="Input data",
            description="The texts, as people annotate them, optionally with the LLM's label in their meta.",
        ),
        "label": props.label_scheme_for("BILLING, TECHNICAL, ..."),
        "output": Props(
            title="Output dataset",
            description="Dataset to save the LLM's answers to.",
        ),
        "labels_exclusive": BoolProps(
            title="Mutually exclusive labels",
            description="Every text has exactly one correct label. Use the same setting as the annotation task.",
        ),
        "llm_label_key": TextProps(
            title="Logged LLM label",
            optional_title="Read the LLM's labels from the input",
            description="The meta key that holds the LLM's label, e.g. reference_label. Without it, the action calls the LLM.",
        ),
        "sample_size": IntProps(
            title="Sample size",
            optional_title="Draw a sample by the LLM's label",
            description="Texts to sample in all, shared between the LLM's labels by how often it gives each, with each answer's weight in its meta.",
            min=1,
        ),
        "min_per_label": IntProps(
            title="Minimum per label",
            description="When sampling, texts to take at least for each label the LLM gives, so rare labels can be measured.",
            min=1,
        ),
        "blind": OptionalProps(
            title="Texts to annotate",
            optional_title="Save the texts without the LLM's labels",
            description="A new input asset with the texts in random order and the LLM's label removed, for the annotation tasks.",
        ),
        "seed": IntProps(
            title="Random seed",
            description="The same seed and input give the same sample and order.",
            min=0,
        ),
        "api_key": OptionalProps(
            title="API key",
            optional_title="Use an API key",
            description="The LLM provider's API key, stored as an Ellf secret.",
        ),
        "model": TextProps(
            title="Model",
            description="The model name the endpoint expects.",
        ),
        "base_url": TextProps(
            title="API base URL",
            description="An OpenAI-compatible endpoint. The default is Ollama on the Mac that runs the cluster in a Lima VM.",
        ),
        "instructions": TextProps(
            title="Instructions",
            description="What the LLM is told about the task: your production prompt, without its output format.",
        ),
        "reasoning_effort": TextProps(
            title="Reasoning effort",
            optional_title="Set the reasoning effort",
            description="Sent as reasoning_effort, e.g. none to turn off a model's thinking (Qwen3 through Ollama). Leave it unset for endpoints that don't take it.",
        ),
        "label_details": BoolProps(
            title="Send the full label definitions",
            description="Also send each label's list of what not to give it and its examples, not only its description. The start of the prompt is the same for every text, so an endpoint that caches it adds little time.",
        ),
        "session": TextProps(
            title="Annotator name",
            description="Who the answers are credited to in the review and the dashboard.",
        ),
        "workers": IntProps(
            title="Requests at once",
            description="Requests sent to the LLM at the same time. More than 1 helps only if the endpoint serves several at once (for Ollama, OLLAMA_NUM_PARALLEL).",
            min=1,
        ),
        "batch_size": IntProps(
            title="Save every",
            description="Without a sample or a blind asset, answers are saved after this many texts, so a stopped run keeps them and a rerun skips them.",
            min=1,
        ),
        # fmt: on
    },
    cli_names={"label-list": "label", "label-labels": "label-scheme"},
)
def llm_to_dataset(
    *,
    input: Input[Literal["text"]],
    label: Union[list[str], Labels],
    output: Dataset[Literal["textcat"]],
    labels_exclusive: bool = False,
    llm_label_key: Optional[str] = None,
    sample_size: Optional[int] = None,
    min_per_label: int = 20,
    blind: Optional[Output] = None,
    seed: int = 0,
    api_key: Optional[Secret] = None,
    model: str = "qwen3:14b",
    base_url: str = "http://192.168.5.2:11434/v1",
    instructions: str = "",
    reasoning_effort: Optional[str] = "none",
    label_details: bool = False,
    session: str = "LLM",
    workers: int = 1,
    batch_size: int = 50,
) -> None:
    """Save the LLM's answer on every text, or on a sample, to ``output``.

    The examples are built as the built-in text classification task builds
    them for the same labels, so the LLM's answer and a person's on the same
    text are versions of one example in the review: one label is an accept or
    reject question, several are a choice. Each distinct text counts once.

    Without a sample or a blind asset, answers are saved every
    ``batch_size`` texts, in a random order fixed by ``seed``, and texts that
    already have ``session``'s answer in ``output`` are skipped.

    Contract:
        Raises:
            ValueError: If there are no labels, or no text has a usable
                answer (and none had one from an earlier run).
            httpx errors from ``classify`` (not caught) once its retries are
                spent, or at once for a 4xx reply: the action stops, so a bad
                key or model fails fast. Answers saved before then are kept.
            Database errors from ``save_examples()``, and errors from
                ``Output.write_jsonl`` if the asset name is taken (not caught).
    """
    scheme = LabelScheme.resolve(label)
    names = scheme.names()
    if not names:
        raise ValueError("No labels to classify with.")
    exclusive = labels_exclusive or len(names) == 1
    rows = list(cast(Iterable[dict[str, Any]], input.load(rehash=True, dedup=True, input_key="text")))
    incremental = not sample_size and blind is None
    done = already_answered(output.name, session) if incremental else set()
    todo = [eg for eg in rows if eg["text"] not in done]
    if done:
        print(f"{len(rows) - len(todo)} of {len(rows)} texts already have {session}'s answer and are skipped")
    random.Random(seed).shuffle(todo)
    headers = {"Authorization": f"Bearer {api_key.value()}"} if api_key is not None else {}
    answered: list[tuple[dict[str, Any], list[str]]] = []
    saved = unusable = 0
    with httpx.Client(base_url=base_url, headers=headers, timeout=120) as client:

        def answer(eg: dict[str, Any]) -> Optional[list[str]]:
            if llm_label_key:
                return logged_labels(eg, llm_label_key, names)
            return classify(
                eg,
                scheme,
                exclusive,
                client=client,
                model=model,
                instructions=instructions.strip(),
                reasoning_effort=reasoning_effort,
                details=label_details,
            )

        for batch in answer_in_batches(todo, answer, batch_size=batch_size, workers=workers):
            good = [(eg, chosen) for eg, chosen in batch if chosen is not None]
            unusable += len(batch) - len(good)
            if incremental and good:
                save_answers([(eg, chosen, None) for eg, chosen in good], names, output=output.name, session=session)
                saved += len(good)
                print(f"Saved {saved} answers so far ({saved + unusable} of {len(todo)} texts done)")
            elif not incremental:
                answered.extend(good)
    if unusable:
        print(f"{unusable} of {len(todo)} texts have no usable answer and are left out")
    if incremental:
        if not saved and not done:
            raise ValueError("No text has a usable answer from the LLM.")
        print(f"Saved {saved} of the LLM's answers to '{output.name}'")
        if llm_label_key:
            print(
                f"The input holds the LLM's labels in meta.{llm_label_key}: annotate the "
                "texts from a blind asset, not the input, or annotators will see them."
            )
        return
    if not answered:
        raise ValueError("No text has a usable answer from the LLM.")
    if sample_size:
        picked = draw_sample(answered, names, size=sample_size, min_per_label=min_per_label, seed=seed)
    else:
        picked = [(eg, chosen, None) for eg, chosen in answered]
    # Before the examples are built: building adds to the same dicts
    hidden = {llm_label_key} if llm_label_key else set()
    unlabelled = [
        {
            "text": eg["text"],
            "meta": {k: v for k, v in (eg.get("meta") or {}).items() if k not in hidden},
        }
        for eg, _, _ in picked
    ]
    save_answers(picked, names, output=output.name, session=session)
    print(f"Saved {len(picked)} of the LLM's answers to '{output.name}'")
    if blind is not None:
        n = blind.write_jsonl(unlabelled)
        print(f"Wrote {n} texts to annotate, without the LLM's labels, to '{blind.name}'")
    elif llm_label_key:
        print(
            f"The input holds the LLM's labels in meta.{llm_label_key}: annotate the "
            "texts from a blind asset, not the input, or annotators will see them."
        )
