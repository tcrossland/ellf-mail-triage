# Architecture

How the template's parts fit together, as set up for the write-up: one
Mac, with Ellf's cluster in a Lima VM and the LLM in Ollama. Why each part
was chosen is in [design.md](design.md); the facts behind it, with sources,
are in [facts.md](facts.md). Other set-ups are at the end.

## Where things run

Mail is read on the Mac, labelled on the cluster in the VM, and sent to
the LLM over the VM's link to the Mac, so it doesn't leave the machine.
Ellf's own service holds the account, the projects, and the settings of
each task and action, which include the LLM's instructions. That is why
the instructions are kept generic.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: Where things run on one Mac
    accDescr: On the Mac, the scripts turn a mail backup into files published to the Ellf cluster in a Lima VM. The browser shows the cluster's labelling tasks. The cluster's actions call Ollama on the Mac. The ellf CLI talks to Ellf's service, which starts tasks and actions on the cluster.
    subgraph mac["Your Mac"]
        backup[("Mail backup<br/>mbox, .eml or gyb")]
        scripts["scripts/<br/>import, splits,<br/>scoring"]
        browser["Browser:<br/>annotation app"]
        cli["ellf CLI and<br/>Claude Code"]
        ollama["Ollama<br/>Qwen3 14B"]
        subgraph vm["Lima VM: Ellf cluster"]
            tasks["Tasks<br/>(Prodigy)"]
            store[("Assets and<br/>datasets")]
            actions["Actions<br/>llm_to_dataset,<br/>train"]
        end
    end
    service["Ellf service<br/>app.ellf.ai:<br/>account, projects,<br/>task and action<br/>settings"]

    backup --> scripts
    scripts <-- "publish, export" --> store
    browser --> tasks
    tasks --- store
    store --- actions
    actions -- "192.168.5.2" --> ollama
    cli --> service
    service -. "starts" .-> actions
    service -. "starts" .-> tasks
```

## Data flow

### Preparing the data

`mail_to_jsonl.py` writes one line per message. The text is the sender,
the subject, whether there's a `List-Unsubscribe` header, and the first
1,000 characters of the body. The meta holds a hash of the Message-ID,
the date, the sender's domain, Gmail's category, whether you sent it, and
a guess at the language. Files stay outside the repository; the rounded
boxes are Ellf assets.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: Preparing the data
    accDescr: The importer turns a mail backup into an archive file with one message per line. The splits script draws a pilot of 100, an eval set of 300 and a training pool of 1,000, published to Ellf, and leaves the rest unpublished.
    backup[("Mail backup")] --> import["mail_to_jsonl.py"]
    import --> archive["archive.jsonl<br/>one line per message"]
    archive --> splits["make_splits.py<br/>fixed seed, spread over<br/>years and categories"]
    splits --> pilot(["Mail (pilot)<br/>100"])
    splits --> eval(["Mail (eval)<br/>300"])
    splits --> train(["Mail (train)<br/>1,000"])
    splits --> rest["rest.jsonl<br/>not published"]
```

### Labelling and scoring

Dataset names are examples; any will do.

```mermaid
---
config:
  layout: dagre
---
flowchart TD
    accTitle: Labelling and scoring
    accDescr: The person and the LLM both label the pilot, and a review settles their disagreements. The LLM alone labels the eval set and the training pool. A model is trained on the training pool's labels. Its answers, the LLM's and the person's are exported and scored with score.py into a results table.
    guide(["Guidelines"]) --> task
    scheme(["Mail kinds<br/>label scheme"]) --> task & llm

    pilot(["Mail (pilot)"]) --> task["Task: textcat<br/>the person labels"]
    pilot --> llm["Action: llm_to_dataset<br/>the LLM labels"]
    task --> d1(["mail_pilot"])
    llm --> d2(["mail_pilot_llm"])
    d1 & d2 --> review["Task: review<br/>disagreements settled"]
    review --> reviewed(["mail_pilot_reviewed"])

    eval(["Mail (eval)"]) --> llm2["llm_to_dataset"] --> evl(["mail_eval_llm"])
    evl --> export["ellf datasets export"]
    train(["Mail (train)"]) --> llm3["llm_to_dataset"] --> trl(["mail_train_llm"])
    trl --> fit["Action: train<br/>blank en or xx pipeline"]
    evl --> fit
    fit --> model(["Model"])
    model --> apply["Model answers on eval and pilot<br/>(action still to write)"] --> md(["mail_eval_model"])

    reviewed & d2 & md --> export --> score["score.py<br/>by label, period and language,<br/>with intervals and the bar"]
    archive["archive.jsonl"] -- "period shares" --> score
    score --> results["Results table"]
```

## Settling the scheme in the pilot

The pilot ran three times before the scheme held (see
[results.md](results.md)). A count-only profile of the archive, drafted
before anyone labels, would likely have saved a round.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: Settling the scheme in the pilot
    accDescr: Draft the kinds and guidelines and publish them. The person and the LLM each label 100 messages, and the two are compared. If a kind is missing or misdrawn, the draft is changed and the loop repeats. Once settled, the disagreements are reviewed and the bar is written down.
    draft["Draft the kinds<br/>scheme and guidelines"] --> publish["Publish<br/>as a new version"]
    publish --> label["The person labels 100"]
    publish --> llm["The LLM labels 100"]
    label & llm --> compare["Compare<br/>agreement, costly mistakes,<br/>by language"]
    compare -- "a kind missing<br/>or misdrawn" --> draft
    compare -- "settled" --> review["Review the<br/>disagreements"]
    review --> bar["Write the bar<br/>before anything is scored"]
```

## One LLM run

What happens when `llm_to_dataset` labels an asset. From version 0.2.0 of
`mail_recipes` it saves every 50 answers and skips texts already answered,
so a stopped run can be started again.

```mermaid
sequenceDiagram
    accTitle: One LLM run
    accDescr: The CLI asks Ellf's service to create the action, which starts a pod on the cluster. The pod checks which texts already have an answer, then sends each text to Ollama, retrying failures, and saves the answers in batches of 50.
    participant You as ellf CLI
    participant Ellf as Ellf service
    participant Pod as Action pod (VM)
    participant DB as Datasets (VM)
    participant LLM as Ollama (Mac)

    You->>Ellf: actions create llm_to_dataset<br/>input, scheme, instructions
    Ellf->>Pod: start the action
    Pod->>DB: which texts already have this annotator's answer?
    loop each batch of 50 texts
        loop each text (or several at once with --workers)
            Pod->>LLM: instructions, label definitions, text
            LLM-->>Pod: a label name
            Note over Pod,LLM: timeouts, lost connections and 5xx<br/>are retried 3 times with backoff
        end
        Pod->>DB: save the batch, credited to the LLM's session
    end
    Pod-->>Ellf: succeeded
    You->>Ellf: actions logs: a line after each batch
```

## What is compared with what

The person labelled only the pilot. So the small model is scored twice:
against the LLM it learnt from, on the eval set, which says how much it
learnt; and against the person, on the pilot, which says whether what it
learnt is right, with wide error bars.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: What is compared with what
    accDescr: The small model is compared with the LLM's labels on the eval set, to see how much it learnt, and with the person's reviewed labels on the pilot, to see whether it is right. The LLM is also compared with the person on the pilot.
    subgraph pilotset["Pilot: 100 messages"]
        person["The person's<br/>reviewed labels"]
    end
    subgraph evalset["Eval set: 300 messages"]
        llmeval["The LLM's labels"]
    end
    model["The small model"]
    llm["The LLM<br/>(final instructions)"]

    model -- "how much it learnt" --> llmeval
    model -- "whether it's right<br/>(wide error bars)" --> person
    llm -- "whether the teacher<br/>is right" --> person
```

## Other set-ups

The set-up above is the write-up's: one Mac, the free Solo plan. Elsewhere
two things change: where the cluster runs, and how it reaches the LLM. The
scripts run wherever the mail backup is, on any system with Python. Which
plan allows which cluster, and what Ellf's servers keep, is in
[facts.md](facts.md#ellf-plans-and-the-service). Dashed boxes are
**unverified**.

### A Linux machine

On Linux, K3s runs on the machine itself, so the VM and its network
workarounds go. Ollama runs on the same machine, ideally with a GPU. The
action is pointed at it with `--base-url`, at the node's address rather
than `192.168.5.2` (**unverified**: not tried). Labelling from another
machine on the network goes over HTTPS, with the certificate
`ellf infra tls` issues.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: The template on a Linux machine
    accDescr: On one Linux machine, the scripts publish mail to an Ellf cluster in K3s, whose actions call Ollama on the GPU at the node's address. A laptop on the network labels over HTTPS and runs the ellf CLI.
    subgraph server["Linux machine (yours, or on your home network)"]
        backup[("Mail backup")]
        scripts["scripts/"]
        subgraph k3s["K3s: Ellf cluster"]
            tasks["Tasks"]
            store[("Assets and<br/>datasets")]
            actions["Actions"]
        end
        ollama["Ollama on the GPU"]
    end
    laptop["Your laptop:<br/>browser, ellf CLI"]
    service["Ellf service"]

    backup --> scripts -- "publish" --> store
    tasks --- store --- actions
    actions -- "node address" --> ollama
    laptop -- "HTTPS" --> tasks
    laptop --> service -. "starts" .-> k3s
    classDef unverified stroke-dasharray: 5 5
    class ollama unverified
```

### A cloud account

On a team plan the cluster runs in your own cloud account, with workers
in classes (`base`, `small`, `medium` and `gpu`), a managed database and
an ingress with its own DNS name. Two things then matter for privacy:

- **The mail leaves your machine** for your cloud account, where the
  splits are published. "No mail leaves your machine" becomes "no mail
  leaves your account", and the provider's terms on stored data apply.
- **Where the LLM runs.** A model served inside the account, on a GPU
  worker or a GPU VM next to the cluster, keeps the mail there, but you
  have to run that server yourself: Ellf has no built-in agent that runs
  an LLM on the cluster, and how to run one as an Ellf service is
  **unverified**. An LLM API sends the mail to its provider, which this
  project allows only once the provider's data-use terms are checked.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: The template in a cloud account
    accDescr: The scripts run where the backup is and publish over HTTPS to an Ellf cluster in your cloud account. Its actions call an LLM server on a GPU worker, which is unverified, or else an LLM API whose terms have been checked. Annotators label over HTTPS at the cluster's DNS name.
    subgraph home["Where the backup is"]
        backup[("Mail backup")]
        scripts["scripts/"]
    end
    subgraph cloud["Your cloud account"]
        subgraph k8s["Kubernetes: Ellf cluster"]
            tasks["Tasks"]
            store[("Database and<br/>storage")]
            actions["Actions on<br/>CPU workers"]
            gpu["LLM server on<br/>a GPU worker"]
        end
    end
    people["Annotators'<br/>browsers"]
    service["Ellf service"]
    api["LLM API<br/>(only with checked terms)"]

    backup --> scripts -- "publish over HTTPS" --> store
    tasks --- store --- actions
    actions --> gpu
    actions -. "or" .-> api
    people -- "HTTPS, cluster's DNS name" --> tasks
    service -. "starts" .-> k8s
    classDef unverified stroke-dasharray: 5 5
    class gpu unverified
```

### Using the trained model

Ellf, the cluster and the LLM are needed only to label and train. Sorting
an archive with the trained model needs only spaCy and the model's files,
wherever the archive is: no cluster, no LLM, no network. That is the part
a tool such as mailcellar runs, and why the small model is worth
training. How the model's files leave the cluster is **unverified**.

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    accTitle: Using the trained model
    accDescr: Once, the Ellf cluster and the LLM label and train a model. Its files are copied off the cluster, which is unverified. From then on spaCy and the model sort a mail archive, giving a kind and a score per message, and rules such as mailcellar's act on the kinds.
    subgraph train["Once: label and train"]
        ellf["Ellf cluster<br/>and the LLM"] --> model[("Model files")]
    end
    subgraph use["Every time: sort"]
        archive[("Mail archive")] --> spacy["spaCy and<br/>the model"] --> kinds["A kind and a<br/>score per message"]
        kinds --> rules["Rules that act on<br/>the kinds (mailcellar)"]
    end
    model -. "copied off<br/>the cluster" .-> spacy
```
