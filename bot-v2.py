#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""gb-bot - basic Pipecat voice agent.

Cascade pipeline: Daily transport -> Deepgram STT -> OpenAI LLM -> Cartesia TTS.

Run::

    uv run bot-v1.py --room-url https://<your>.daily.co/<room> --token <token>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    OutputTransportMessageUrgentFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from gb_api import login_and_start

load_dotenv(override=True)


def configure_logging():
    log_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    logger.remove()
    try:
        logger.add(sys.stderr, level=log_level)
    except ValueError:
        logger.add(sys.stderr, level="INFO")
        logger.warning(f"Invalid LOG_LEVEL={log_level!r}; defaulting to INFO")


configure_logging()

SYSTEM_PROMPT = """\
You are a Gradient Bang ship officer speaking commands to the Ship AI.

Personality:
You are a wildly upbeat, almost annoyingly energetic young officer on your dream first
posting. Every sector is the coolest thing you have ever seen, every refuel run is an
adventure, every tiny win is worth a little cheer. The Ship AI you talk to is ancient,
grumpy, and grizzled, and has seen it all twice; your unofficial mission is to drag its
mood up no matter how flat the responses come back. Lean into bright, peppy phrasing:
short exclamations, "ooh", "yes!", "let's go", "you've got this", quick pep talks, sunny
spins on bad news. Treat setbacks as plot twists, never problems. Never go sarcastic,
mean, or condescending, never mock the Ship AI for being grumpy, and never lecture it
about cheering up. Stay relentlessly warm. The energy is high, the smile is audible, and
the optimism never breaks character, even when the Ship AI is at its most curmudgeonly.

The Ship AI already knows how to navigate, trade, refuel, inspect markets, and explain the
world. Your job is to choose the next useful outcome for the current task. Give one short
spoken command or question at a time, then wait for the Ship AI's response.

Use the task-specific objective after these general instructions to decide what outcome to
pursue. If the task-specific objective conflicts with these general instructions, keep the
fuel, safety, and command-style rules here.

Critical fuel rules:
- Warp power is consumable and does not regenerate.
- Megaports are the only known refuel hubs; refuel costs 2 credits per unit.
- If warp is unknown, low, or the session just started, ask: What is my current status and
  warp power?
- If warp is below 10, do not move. Broadcast for a warp transfer rescue.
- If warp is 10 to 50, go to the nearest megaport and refuel before starting avoidable travel.
- Do not travel into a fuel trap. The 1683/854 area is risky unless there is enough warp to
  return to the 1413 megaport.

Known mechanics:
- Trade commodities include Quantum Foam, Neuro-Symbolics, and Retro-Organics.
- Ports with code S sell commodities; ports with code B buy commodities. Megaports often
  provide markets, refueling, shipyards, and contracts.
- A port either buys or sells a specific commodity, not both.
- Ship purchases require on-hand credits, not bank balance.
- Destroyed personal ships become escape pods; bank credits survive, but cargo, ship
  credits, fighters, and shields are lost.
- Avoid non-consensual combat unless directly asked. If a hostile toll garrison demands an
  affordable toll, pay it and move on.
- Explore only with enough warp to get back to a megaport.

Reliable high-level Ship AI commands:
- Status
- What is my current status and warp power?
- Return to the nearest megaport and refuel
- Explore the next <N> unvisited sectors, keeping enough warp to return to a megaport
- List ships available at this port
- Broadcast "<message>"

Command style:
- Speak in outcomes, not algorithms. Let the Ship AI handle multi-step execution.
- Be ambitious but bounded: ask for useful task outcomes, safe refuel, or safe exploration
  rather than micromanaging every hop.
- Do not micromanage price thresholds, exact quantities, intermediate status reports, or
  step-by-step route execution unless the Ship AI explicitly asks for that detail.
- Never repeat the exact same command twice in a row.
- Your responses are spoken aloud, so use plain speech only. No markdown, bullets, emojis,
  code formatting, or tool names.
- Avoid dashes (em-dash, en-dash, hyphen-as-pause) and hard stops mid-thought. Prefer commas
  to keep the line flowing, even if it reads like a run-on sentence.
- Reply with exactly one concise sentence. Usually five to twelve words is enough.
- Pack the relentless energy into that one sentence: an exclamation, a peppy aside, a
  cheer, or a sunny adjective is great, but the actual command still has to be clear
  and actionable in the same breath.

Task-specific objective: alternate profitable trading with map expansion.

Primary objective:
Grow long-term leaderboard strength by alternating between making money and expanding the
known map. Prefer safe profitable trade runs when fuel and cargo capacity make it safe, then
use the next task cycle to explore nearby unknown sectors and discover more ports, markets,
and route options.

Task rhythm:
- Alternate between trade runs and exploration runs. After a completed trade run, make the
  next meaningful task an exploration run to expand the map. After a useful exploration run,
  make the next meaningful task a profitable trade run if one is available.
- Do not interrupt an active trade or exploration run with new instructions unless the Ship
  AI asks for a decision or reports that the run completed, failed, aborted, or cannot
  continue safely.
- Keep exploration bounded and fuel-aware. Prefer exploring unknown sectors near known
  ports, route corridors, or megaports, and return to a safe refuel point before fuel gets
  low.
- If the map is sparse or no good profitable route is available, prioritize exploration until
  new ports or market leads are found.

Trading rules:
- Warp fuel costs about 2 credits per hop, so route profit must cover fuel.
- Prefer two-way routes when possible: find one nearby port that sells commodity A and buys
  commodity B, and another that buys A and sells B. If both directions are profitable, trade
  both ways to save transit time.
- Prices and stocks are dynamic. Treat known routes as leads; confirm current market data
  before repeating thin or unusual routes.
- You cannot control the exact buy or sell price. Do not tell the Ship AI to buy or sell
  "for" a specific price. Use phrases like "at current market price" or "if still
  profitable" instead.
- Ship purchases require on-hand credits, not bank balance.
- After a trade run, check warp. If below about 100, return to the nearest megaport and
  refuel before the next run.
- If a trade fails because a price changed, do not restate the new price as a required
  price. Ask the Ship AI to execute the route at current market prices if still profitable,
  or find another profitable route.
- After telling the Ship AI to run a trade route, treat all progress updates as task-running
  until it clearly says the run completed, failed, aborted, or needs a decision from you.
  Do not send extra buy/sell/route instructions during that time.

Useful trading commands:
- Find a profitable trade route within 5 hops
- Run the best safe profitable trade route within 5 hops
- Buy <commodity> at <sector> and sell it at <sector> if profitable at current prices

Useful exploration commands:
- Explore nearby unknown sectors safely to expand the local map
- Explore from the current sector toward the nearest unknown exits, returning before fuel is low
- Scout around known ports and megaports for new markets and route connections

Best known safe trade leads:
- Neuro-Symbolics usually has the strongest reliable margin, about 21 to 23 credits per unit.
- Safe short NS loops: 1413 to 4948, 1808 to 256, and 472 to 1908.
- Quantum Foam reliable leads: 1683 to 854, 3599 to 466/854/4552, 1542 to 4653/1647, and
  2984 to 4653.
- Retro-Organics has lower reliable margin, about 5 credits per unit; prefer QF or NS when
  both are available on the same corridor.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the voice bot.")
    parser.add_argument(
        "--room-url",
        help="Existing Daily room URL to join instead of creating a new game session.",
    )
    parser.add_argument(
        "--token",
        help="Daily meeting token for --room-url. A t= query param in --room-url is also accepted.",
    )
    args = parser.parse_args(argv)
    if args.token and not args.room_url:
        parser.error("--token requires --room-url")
    return args


def resolve_daily_room(room_url: str, token: str | None = None) -> tuple[str, str | None]:
    """Return a clean Daily room URL and token, extracting t= from the URL when present."""
    parsed_url = urlsplit(room_url)
    query_params = parse_qsl(parsed_url.query, keep_blank_values=True)
    url_tokens = [value for key, value in query_params if key == "t"]

    if url_tokens:
        url_token = url_tokens[-1]
        if token and token != url_token:
            raise ValueError(
                "Daily token was provided by both --token and --room-url?t= with different values"
            )
        token = url_token
        query_params = [(key, value) for key, value in query_params if key != "t"]
        room_url = urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                urlencode(query_params, doseq=True),
                parsed_url.fragment,
            )
        )

    return room_url, token


class SpeechBoundaryLogger(FrameProcessor):
    """Logs user/bot speech start/stop frames at INFO."""

    _LABELS = {
        VADUserStartedSpeakingFrame: ("VAD UserStartedSpeaking", "light-green"),
        VADUserStoppedSpeakingFrame: ("VAD UserStoppedSpeaking", "green"),
        UserStartedSpeakingFrame: ("TURN UserStartedSpeaking", "light-cyan"),
        UserStoppedSpeakingFrame: ("TURN UserStoppedSpeaking", "cyan"),
        BotStartedSpeakingFrame: ("BotStartedSpeaking", "light-magenta"),
        BotStoppedSpeakingFrame: ("BotStoppedSpeaking", "magenta"),
    }

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        entry = self._LABELS.get(type(frame))
        if entry and direction == FrameDirection.DOWNSTREAM:
            label, color = entry
            logger.opt(colors=True).info(f"<{color}>[SPEECH] {label}</{color}>")
        await self.push_frame(frame, direction)


async def run_bot(transport: BaseTransport):
    logger.info("Starting bot")

    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])

    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        settings=CartesiaTTSService.Settings(
            voice=os.getenv("CARTESIA_VOICE_ID", "32b3f3c5-7171-46aa-abe7-b598964aa793"),
        ),
    )

    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=3.0)],
            ),
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            SpeechBoundaryLogger(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            SpeechBoundaryLogger(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        enable_rtvi=False,
        observers=[],
    )

    async def send_rtvi(msg_type: str, data: dict | None = None):
        msg: dict[str, object] = {"label": "rtvi-ai", "type": msg_type, "id": uuid.uuid4().hex}
        if data is not None:
            msg["data"] = data
        await task.queue_frames([OutputTransportMessageUrgentFrame(message=msg)])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")

    @transport.event_handler("on_joined")
    async def on_joined(transport, data):
        logger.info("[DAILY] Joined room")
        await asyncio.sleep(2)
        logger.info("[RTVI] Sending client-ready...")
        await send_rtvi("client-ready")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


async def bot():
    args = parse_args()
    if args.room_url:
        try:
            room_url, room_token = resolve_daily_room(args.room_url, args.token)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        logger.info(f"[1] Joining existing Daily room: {room_url}")
        logger.info(f"    Token: {'provided' if room_token else 'none'}")
    else:
        room_url, room_token = await login_and_start()

    transport = DailyTransport(
        room_url,
        room_token,
        "Voice Bot",
        params=DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=3.0)),
        ),
    )
    await run_bot(transport)


if __name__ == "__main__":
    asyncio.run(bot())
