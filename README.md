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

## Project Structure

```
gb-bot/
├── bot.py                  # Main bot implementation
├── system_prompt.md        # General Gradient Bang instructions
├── task_prompts/
│   └── trading.md          # Default task-specific instructions
├── pyproject.toml          # Python dependencies
├── Dockerfile              # Container image for Pipecat Cloud
├── pcc-deploy.toml         # Pipecat Cloud deployment config
├── uv.lock                 # Locked Python dependencies
├── .gitignore           # Git ignore patterns
└── README.md            # This file
```

## Deploying to Pipecat Cloud

This project is configured for deployment to Pipecat Cloud. You can learn how to deploy to Pipecat Cloud in the [Pipecat Quickstart Guide](https://docs.pipecat.ai/getting-started/quickstart#step-2-deploy-to-production).

Refer to the [Pipecat Cloud Documentation](https://docs.pipecat.ai/deployment/pipecat-cloud/introduction) to learn more about configuring, deploying, and managing your agents in Pipecat Cloud.

## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)
