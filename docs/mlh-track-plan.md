# Watchcat sponsor-track plan

Watchcat's judging story starts with the Alice & Bob Introductory Track. The
other integrations are attached to real user actions instead of being badges:

| Track | Product use | Status |
| --- | --- | --- |
| Alice & Bob | Full two-mode cat-qubit simulation, truncation checks, convergence report | Core |
| Best Use of Gemini | Explain the measured evidence in plain language without changing the numerical verdict | Implemented, optional key |
| Best Use of Backboard | Remember experiment summaries across runs and teams | Implemented, optional key |
| Best Use of Tiger Data | Store run history as queryable PostgreSQL/Timescale time-series data | Implemented, optional database URL |
| Best Use of ElevenLabs | Read a worried warning aloud as an accessibility/demo mode | Implemented, optional key |
| SpaceXSI | Development workflow prize; use Cursor/Grok to accelerate the build and document that workflow | Process, not runtime |
| Best Use of Vultr | A credible next step for remote high-dimensional sweeps | Future extension |
| Best Use of Solana | Not a natural fit for a local scientific diagnostics tool | Intentionally skipped |
| DEV Writing Challenge | Publish the technical story and the measured convergence result | Submission step |

## Optional environment variables

Copy `.env.example` to `.env`, fill in the services you are using, and Watchcat
loads that file automatically for Python commands and the VS Code sweep button.

```bash
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-2.5-flash"
export BACKBOARD_API_KEY="..."
export BACKBOARD_ASSISTANT_ID="..."
export WATCHCAT_TIGER_DATABASE_URL="postgresql://..."
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="your-own-or-API-eligible-voice-id"
export ELEVENLABS_MODEL_ID="eleven_v4" # expressive delivery tags
```

For a generic AI explanation backend, use the provider-neutral variables below;
the popup only exposes an **Explain** action and never displays the secret:

```bash
export WATCHCAT_AI_PROVIDER="openai"
export WATCHCAT_AI_API_KEY="..."
export WATCHCAT_AI_MODEL="gpt-5-mini"
```

Document the actual backend accurately in the submission. No key is required
for the core product. Without credentials, Watchcat still runs the real
physics, saves local history, gives a deterministic evidence-based explanation,
and never pretends an integration worked.

## Commands

```bash
# Explain the current report; uses the configured AI backend or local fallback.
.venv/bin/python -m qpet.integrations explain

# Save local history and mirror to configured Backboard/Tiger Data services.
.venv/bin/python -m qpet.integrations remember

# Generate an ElevenLabs alert and play it on macOS when configured.
.venv/bin/python -m qpet.integrations speak --play
```

Install optional dependencies only when using those services:

```bash
.venv/bin/python -m pip install -e ".[physics,visualization,gemini,data]"
```
