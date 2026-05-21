# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`gb-bot` is a Pipecat voice agent that plays the Gradient Bang game. It joins a Daily WebRTC room and runs a cascade pipeline (Daily transport → LLM → Cartesia TTS). Audio input is disabled (`audio_in_enabled=False`); the bot's "user" turns come exclusively from in-game app-messages sent by the Ship AI, not from microphone audio.

## Commands

Package manager is `uv` (not pip). Use `uv` for all Python operations.

- Install deps: `uv sync`
- Run against a fresh game session: `uv run bot.py --transport daily` (logs in with `GB_EMAIL`/`GB_PASSWORD`, creates/selects `GB_CHARACTER`, starts a session, joins the returned Daily room)
- Run against an existing Daily room: `uv run bot.py --room-url "https://…daily.co/room" --token "TOKEN"` (or pass `?t=TOKEN` inside `--room-url`)
- Switch the task prompt: `GB_TASK_PROMPT_PATH=task_prompts/<file>.md uv run bot.py …`
- Lint/format: `uv run ruff check .` / `uv run ruff format .`
- Typecheck: `uv run pyright`
- Deploy: built and deployed to Pipecat Cloud via `Dockerfile` + `pcc-deploy.toml` (agent name `gb-bot`, secrets set `gb-bot-secrets`). The Dockerfile only copies `bot.py` — anything `bot.py` imports at runtime (e.g. prompt files, `gb_api.py`) must also be copied in.

## Environment

`GB_ENV` (`prod` | `local`) selects which `GB_API_BASE_*` to call. Real keys live in `.env`; `.env.example` lists everything required. `GB_LOG_DAILY_JOIN_URL=true` is a local-only debug switch — it prints room tokens to logs, do not enable in deployed environments.

## Architecture

There are two parallel concerns the code juggles: **the Pipecat pipeline** (how the bot talks) and **the Gradient Bang session protocol** (what the bot hears and says back).

### Session bootstrap (`gb_api.py` / `bot.py:login_and_start`)

`login_and_start()` does a three-step dance against the Gradient Bang Functions API: `POST /login` → find-or-`POST /user_character_create` → `POST /start` with `createDailyRoom: true`. The response yields a Daily room URL and meeting token that the bot then joins. When `--room-url` is passed, this whole flow is skipped (useful for debugging against a room someone else created). `resolve_daily_room()` extracts a `?t=` token out of a join URL so users can paste a single Daily share link.

Note: `gb_api.py` is a standalone copy of the same logic that lives inside `bot.py`. `bot.py` does **not** import it — they have drifted in the past. If you change the API flow, update both, or refactor `bot.py` to import from `gb_api.py` (and then make sure the Dockerfile copies it).

### The pipeline (`bot.py:run_bot`)

Frame order:

```
transport.input → input timing logger → user_aggregator → llm → wait_tag_filter
                → bot_speech_logger → tts → transport.output → output timing logger → assistant_aggregator
```

Game-context injection (`GameContextStore` + `GameContextInjector`) is wired but **currently commented out** in both the pipeline and the `on_app_message` handler. The store classes still exist because the design is to re-enable structured game-state summarization in the LLM context once the prompt strategy stabilizes. Don't delete them.

### How the bot "hears" the game

Audio input is off. Instead, `on_app_message` receives JSON messages over the Daily app-message channel from the Gradient Bang Ship AI participant. `GameTurnBuffer` accumulates several message shapes per spoken turn:

- `bot-transcription` (preferred — actual STT of the Ship AI)
- `bot-output` with `aggregated_by=sentence` (fallback — TTS sentences)
- `bot-output`/`bot-tts-text` word stream (last-resort fallback)

A turn flushes when `bot-stopped-speaking` arrives or the server emits `ship.speech_stopped`. The flushed text is queued into the LLM as a user message via `LLMMessagesAppendFrame(run_llm=True)`. The fallback ordering matters — don't reorder it without re-reading the buffer's flush logic.

### `<wait>` protocol

The system prompt teaches the LLM to emit a literal `<wait>` token when it has nothing to say (Ship AI is still working on the previous command). `WaitTagFilter` intercepts the *complete* response between `LLMFullResponseStartFrame` and `LLMFullResponseEndFrame`, and if it normalizes to `<wait>` / `<wait/>` / `<wait></wait>`, it suppresses the text from reaching TTS and resets pending speech-timing state. Anything else passes through as a single `LLMTextFrame`. This buffering is why `LLMTextFrame`s during a response are *not* forwarded individually downstream of `wait_tag_filter`.

### Prompt composition (`load_system_prompt`)

The LLM system instruction is concatenated from `system_prompt.md` (game rules, command style, `<wait>` semantics) + the task prompt at `GB_TASK_PROMPT_PATH` (defaults to `task_prompts/trading.md`). Both are read from disk on every bot start.

### Speech timing instrumentation

`SpeechTimingState` + `TransportSpeechTimingLogger` exist only for latency observability (logs `elapsed_since_bot_stopped` when the user starts speaking). They don't gate pipeline behavior; safe to ignore unless investigating turn-taking latency.

## Multi-bot / crosstalk caveat

See `PROBLEMS.md` — multiple Pipecat bots in the same Daily room subscribe to each other's microphone tracks by default. This bot sidesteps it by running with `audio_in_enabled=False`, but if you ever enable audio input, you must filter participants or you will get crosstalk.

## Files of note

- `bot.py` — the live bot, currently identical to `bot-v3.py`. New work goes in `bot.py`.
- `bot-v1.py` — naive audio baseline, closest to a generated Pipecat example (mic in, Silero VAD, Deepgram STT). No bot-to-bot accommodations.
- `bot-v2.py` — `bot-v1` plus the minimum changes needed to listen to another bot instead of a human: `SileroVADAnalyzer(params=VADParams(stop_secs=3.0))` and `SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=3.0)`.
- `bot-v3.py` — smart-audio version: drops audio input, reconstructs Ship AI turns from Daily app-messages, and adds the `<wait>` protocol described above.
- `PROBLEMS.md` — investigation notes on Pipecat/Daily participant-audio behavior.
- `docs/headless-daily-join.md` — notes on joining a Daily room headlessly for testing.

## Pipecat docs

For any Pipecat framework question (frames, services, transports, examples), use the `pipecat-context-hub` MCP tools instead of reading `.venv/` source.
