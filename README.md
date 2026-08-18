# LiveTutorials

LangChain / LLM tutorials. .

## Setup

```bash
pip install -e .          # installs every dependency the tutorials need
cp .env.example .env      # then fill in your keys/endpoints (your responsibility)
```

`.env` is loaded automatically by python-dotenv; it is gitignored, the template
is not.

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
├── src/livetutorials/      # installable package (currently just scaffolding)
│   ├── __init__.py
│   ├── kapoorlab.yaml
│   └── _tests/
├── tutorials/              # <- put your tutorial scripts here
└── data/                   # <- local data / vector DBs (gitignored as needed)
```

Add tutorial scripts to `tutorials/` and shared helpers to
`src/livetutorials/`.
