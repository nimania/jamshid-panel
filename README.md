# Jamshid Panel

A Streamlit-based production control panel for Persian media workflows.

Jamshid Panel brings together newsroom intake, source discovery, AI-assisted script generation, image workflow support, voice generation, and lightweight media-processing utilities in a single internal interface.

## Current capabilities

- Connects to a Google Sheets-based command center through a service account.
- Generates Persian scripts for different editorial formats with OpenAI models.
- Supports image-analysis-to-prompt workflows and image generation.
- Generates speech through ElevenLabs.
- Includes RSS/source-discovery helpers.
- Includes media download and processing dependencies such as `yt-dlp`, OpenCV, and MoviePy.
- Uses Streamlit as the operator interface.

## Architecture

The current version is intentionally compact:

```text
jamshid-panel/
├── app.py
├── requirements.txt
└── .devcontainer/
```

Most application logic currently lives in `app.py`. As the project grows, separating integrations, newsroom logic, media utilities, and UI components into modules would improve maintainability and testability.

## Setup

Python 3.11+ is recommended.

```bash
git clone https://github.com/nimania/jamshid-panel.git
cd jamshid-panel
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Required secrets

The application expects credentials through Streamlit secrets rather than hard-coded keys. Depending on the enabled workflows, configuration can include:

- Google Cloud service-account credentials
- OpenAI API key
- ElevenLabs API key

Keep all credentials outside version control. Do not commit `.streamlit/secrets.toml`, service-account private keys, or API tokens.

## Project status

**Internal tool / active development.** The repository currently represents a working operational panel rather than a polished end-user product. Interfaces, model choices, and third-party API integrations may change as the workflow evolves.

## Security notes

This application can access third-party APIs and a Google Sheets command center. Deploy it only in an environment where secrets are protected and access is appropriately restricted.

## Roadmap

Useful next steps include:

- split `app.py` into focused modules;
- add automated tests for pure helper functions;
- add CI for dependency installation and basic import checks;
- document the Streamlit secrets schema with placeholder-only examples;
- pin and periodically review third-party dependencies.

## License

No open-source license is currently declared. Unless a license is added, normal copyright rules apply.
