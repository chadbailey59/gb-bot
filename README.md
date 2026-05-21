# gb-bot

A Pipecat AI voice agent built with a cascade pipeline (STT → LLM → TTS).

## Configuration

- **Bot Type**: Web
- **Transport(s)**: Daily (WebRTC)
- **Pipeline**: Cascade
  - **STT**: Deepgram
  - **LLM**: OpenAI
  - **TTS**: Cartesia

## Setup

### Server

1. **Navigate to server directory**:

   ```bash
   cd server
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Run the bot**:

   - Daily: `uv run bot.py --transport daily`

   To join an existing Daily room instead of creating a new game session:

   ```bash
   uv run bot.py --room-url "https://your-domain.daily.co/room-name" --token "DAILY_TOKEN"
   ```

   A Daily join URL with `?t=` also works; the bot extracts the token and joins the
   room URL without the token query parameter:

   ```bash
   uv run bot.py --room-url "https://your-domain.daily.co/room-name?t=DAILY_TOKEN"
   ```

## Prompt Structure

The bot composes its LLM system instruction from two files:

- `system_prompt.md`: reusable game rules, safety guidance, and command style.
- `task_prompts/trading.md`: the default task-specific prompt for trading profitably.

Set `GB_TASK_PROMPT_PATH` to use a different task prompt, such as exploration or combat:

```bash
GB_TASK_PROMPT_PATH=task_prompts/exploration.md uv run bot.py --transport daily
```

## Implementation history

The `bot-vN.py` files are progressive snapshots of how the bot evolved from a
stock Pipecat voice agent into something that can actually converse with
another bot. `bot.py` is the live entrypoint and tracks the newest version.

- **`bot-v1.py` — naive audio.** As close as possible to a generated Pipecat
  example: Daily transport, mic in, Silero VAD, Deepgram STT, OpenAI LLM,
  Cartesia TTS. No accommodations for the fact that the "user" on the other end
  is itself a TTS bot.
- **`bot-v2.py` — naive audio, tolerant turn-taking.** The minimum changes to
  `bot-v1` needed to compensate for listening to another bot instead of a
  human. Extends `SileroVADAnalyzer` `stop_secs` to 3.0 and adds a
  `SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=3.0)` so the Ship AI's
  natural inter-sentence pauses don't get mistaken for end-of-turn.
- **`bot-v3.py` — smart audio.** Drops audio input entirely
  (`audio_in_enabled=False`) and instead reconstructs the Ship AI's turns from
  Daily app-messages (`bot-transcription` / `bot-output` / `ship.speech_stopped`).
  Adds the `<wait>` protocol: the LLM emits a literal `<wait>` token when it has
  nothing to say, and `WaitTagFilter` suppresses it before TTS. This is what
  `bot.py` currently runs.

## Project Structure

```
gb-bot/
├── bot.py                  # Live bot (currently == bot-v3.py)
├── bot-v1.py               # Naive audio baseline
├── bot-v2.py               # v1 + extended turn-end timeouts
├── bot-v3.py               # Smart audio: app-messages + <wait>
├── system_prompt.md        # General Gradient Bang instructions
├── task_prompts/
│   └── trading.md          # Default task-specific instructions
├── pyproject.toml          # Python dependencies
├── Dockerfile              # Container image for Pipecat Cloud
├── pcc-deploy.toml         # Pipecat Cloud deployment config
├── uv.lock                 # Locked Python dependencies
├── .gitignore              # Git ignore patterns
└── README.md               # This file
```

## Deploying to Pipecat Cloud

This project is configured for deployment to Pipecat Cloud. You can learn how to deploy to Pipecat Cloud in the [Pipecat Quickstart Guide](https://docs.pipecat.ai/getting-started/quickstart#step-2-deploy-to-production).

Refer to the [Pipecat Cloud Documentation](https://docs.pipecat.ai/deployment/pipecat-cloud/introduction) to learn more about configuring, deploying, and managing your agents in Pipecat Cloud.

## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)
