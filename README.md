# LiveTutorials

Hands-on LangChain / LLM tutorials, built live against the **GWDG Chat AI**
(hosted, OpenAI-compatible) endpoint — no local GPU or model weights needed, just
an API key.

▶️ **Watch the series on YouTube:**
[LiveTutorials playlist](https://www.youtube.com/playlist?list=PLP_bRITriPUk)

## Setup

```bash
pip install -e .          # installs every dependency the tutorials need
cp .env.example .env      # then fill in your keys/endpoints (your responsibility)
```

`.env` is loaded automatically by python-dotenv; it is gitignored, the template
is not. At minimum set `GWDG_API_KEY` (and `GWDG_BASE_URL` if yours differs from
the default). Run tutorial `00` first to confirm your key works and to see which
model ids it can use.

## Tutorials

Each script builds on the previous one. They all import the shared helpers from
the `livetutorials` package, so there are no hardcoded keys or endpoints.

| # | File | What it adds |
|---|------|--------------|
| 00 | `tutorials/00_key_and_secrets.py` (+ `.ipynb`) | The foundation: load your GWDG key from `.env` (auto, via python-dotenv), **list the models** your key can use, send one prompt, print the reply. |
| 01 | `tutorials/01_gwdg_prompt_template.py` | Wrap the model in a `ChatPromptTemplate` (system + human), build an **LCEL chain** `prompt \| model \| StrOutputParser()`, and **stream** the answer token-by-token. |
| 02 | `tutorials/02_gwdg_memory_chat.py` | Add **conversation memory**: `RunnableWithMessageHistory` + `MessagesPlaceholder("history")` keyed by `session_id`, so the bot remembers earlier turns in a REPL loop. |

Run any of them from the repo root, e.g.:

```bash
python tutorials/00_key_and_secrets.py
```

> Each `main(idx=...)` picks a model by index from the list your key allows; run
> `00` to see that list, then change `idx` to the model you want.

## The `livetutorials` package

Shared helpers live in `src/livetutorials/chatbot.py` and are re-exported from the
package, so every tutorial just does `from livetutorials import ...`:

- `get_gwdg_base_url()` / `get_gwdg_api_key()` — endpoint + key from `.env`
- `list_gwdg_models()` — the model ids your key is allowed to use
- `get_gwdg_chat_model(model)` — a LangChain chat model on the GWDG endpoint
- `get_session_history(session_id)` — per-session memory store (used in 02)

## Docling (PDF → markdown)

The tutorials that convert PDFs to markdown/RAG input use
[Docling](https://github.com/docling-project/docling). It is listed in
`install_requires` (`docling>=2.0.0`), so `pip install -e .` already installs it.

First-run notes:

- **Models download on first use.** Docling fetches its layout/table models from
  HuggingFace the first time `DocumentConverter().convert(...)` runs — needs
  internet, a few hundred MB, cached under `HF_HOME` (`~/.cache/huggingface` by
  default). Later runs are offline.
- **HuggingFace token.** Set `HF_API_KEY=<your token>` in `.env` (the converter
  reads it and sets `HF_TOKEN`) to avoid download rate-limits.
- **Faster downloads (optional):** `pip install hf_transfer` — the tutorials set
  `HF_HUB_ENABLE_HF_TRANSFER=1`.
- **Deps / GPU.** Docling pulls in `torch`; on Apple Silicon it uses the **MPS**
  GPU automatically. Docling 2.x needs **Python 3.9+** (the package metadata
  still allows 3.8).

## Layout

```
LiveTutorials/
├── setup.cfg               # package metadata + install_requires (the deps)
├── pyproject.toml          # build backend + setuptools_scm versioning
├── tox.ini                 # test matrix
├── .env.example            # copy to .env, fill in (fields left empty)
├── .github/workflows/      # CI (manual trigger)
├── src/livetutorials/      # installable package
│   ├── __init__.py         # re-exports the GWDG helpers
│   ├── chatbot.py          # get_gwdg_chat_model, list_gwdg_models, ...
│   ├── kapoorlab.yaml
│   └── _tests/
├── tutorials/              # the tutorial scripts (00, 01, 02, ...)
└── data/                   # local data / vector DBs (gitignored as needed)
```
