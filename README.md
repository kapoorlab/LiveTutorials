# LiveTutorials

LangChain / LLM tutorials. .

## Setup

```bash
pip install -e .          # installs every dependency the tutorials need
cp .env.example .env      # then fill in your keys/endpoints (your responsibility)
```

`.env` is loaded automatically by python-dotenv; it is gitignored, the template
is not.

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
