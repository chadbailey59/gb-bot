# Pipecat / Gradient Bang Transcription Crosstalk Notes

## Summary

The transcription mixing issue is not purely a Gradient Bang bug. A simpler
Pipecat-only test reproduced the same class of problem: multiple Pipecat bots in
one Daily room receive each other's microphone tracks by default.

Gradient Bang appears to amplify that base behavior with participant handling,
global mute/unmute state, and app-message assumptions.

## Pipecat Reproduction

Test scenario:

- Ran `~/Code/pipecat/examples/voice/voice-deepgram.py` in one terminal.
- Started a second copy in the same Daily room by passing the first run's room URL
  through `DAILY_ROOM_URL`.
- Then also joined the room from a headless Chromium browser.

Important logs:

- `/home/chad/Code/pipecat/logs/voice-deepgram-a-filtered-20260512-221730.log`
- `/home/chad/Code/pipecat/logs/voice-deepgram-b-filtered-20260512-221741.log`
- `/home/chad/Code/pipecat/logs/voice-deepgram-onebot-browser-20260512-221804.log`

The two-bot run showed crosstalk before the browser joined. Each bot received
`UserAudioRawFrame` frames from the other bot participant's microphone track.

Example pattern:

```text
UserAudioRawFrame(... user: <other-bot-participant-id>, source: microphone ...)
```

This means Pipecat's Daily transport is subscribing to other bot participants'
audio by default.

## Pipecat Daily Behavior

The stock voice example uses:

```python
DailyParams(audio_in_enabled=True, audio_out_enabled=True)
```

It does not filter participants.

Relevant Pipecat source:

- `/home/chad/Code/pipecat/examples/voice/voice-deepgram.py`
- `/home/chad/Code/pipecat/src/pipecat/transports/daily/transport.py`

`DailyParams.audio_in_user_tracks` defaults to `True`.

When a participant joins, Daily transport captures that participant's microphone:

```python
if self._input and self._params.audio_in_enabled and self._params.audio_in_user_tracks:
    await self._input.capture_participant_audio(
        id, "microphone", self._client.in_sample_rate
    )
```

So with `audio_in_enabled=True`, each participant can become STT input unless the
application explicitly filters participants or disables per-user audio capture.

## Browser Join Behavior

A headless Chromium browser joined with fake media devices using a URL of the
form:

```text
<room_url>
```

For Gradient Bang rooms, the equivalent pattern is:

```text
<room_url>?t=<token>
```

Useful Chromium flags:

```sh
chromium \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --remote-debugging-port=9224 \
  --user-data-dir=/tmp/pipecat-onebot-browser-profile \
  --use-fake-ui-for-media-stream \
  --use-fake-device-for-media-stream \
  --autoplay-policy=no-user-gesture-required \
  --no-first-run \
  --no-default-browser-check \
  '<room_url>'
```

The browser did not need to be acoustically echoing audio to affect the room.
With fake media devices, Chromium still published a synthetic microphone track.
The bot continuously received:

```text
UserAudioRawFrame(... user: <browser-participant-id>, source: microphone ...)
```

This proves the browser participant was an active audio source from Pipecat's
point of view. It does not prove that the browser produced meaningful transcript
text, only that raw microphone frames were being captured continuously.

## RTVI App Message Feedback

There is also a Pipecat-level app-message issue when multiple Pipecat bots are in
the same room.

One bot broadcasts RTVI-style output messages such as:

```text
bot-transcription
bot-llm-text
metrics
```

The other bot receives those as `DailyInputTransportMessageFrame` messages with
label `rtvi-ai`.

Pipecat's RTVI processor then tries to validate those as inbound RTVI client
messages. Since the bot-originated output messages are not valid inbound client
commands, validation fails and the receiving bot sends an error message. Another
bot can receive that error and repeat the cycle.

Relevant source:

- `/home/chad/Code/pipecat/src/pipecat/processors/frameworks/rtvi/processor.py`

This caused very large logs in the two-bot Pipecat test and is independent of
Gradient Bang.

## No-RTVI Participant Test

To test whether the second Pipecat participant was causing the issue by acting
like an RTVI server, I created a local diagnostic variant:

- `/home/chad/Code/pipecat/examples/voice/voice-deepgram-no-rtvi.py`

This variant changes the stock Deepgram voice example in two ways:

- `PipelineTask(..., enable_rtvi=False)`
- A `DropDailyInputMessages` processor immediately after `transport.input()` that
  drops incoming `DailyInputTransportMessageFrame` app-message frames before they
  reach STT/LLM processors.

Test run:

- Normal bot log:
  `/home/chad/Code/pipecat/logs/voice-deepgram-normal-rtvi-filtered-20260512-224440.log`
- No-RTVI/dropper bot log:
  `/home/chad/Code/pipecat/logs/voice-deepgram-no-rtvi-drop-filtered-20260512-224450.log`
- Room:
  `https://cloud-87dd58fc03bf474aba6eabe6cc90165f.daily.co/pipecat-6db68184`
- Normal bot participant:
  `5e98e90b-aafa-4d0f-80d5-bdcb3ee08377`
- No-RTVI bot participant:
  `647933ef-210c-4ef6-8dbe-49a386d5d76f`

Observed:

- The no-RTVI bot had no `RTVIProcessor` in its pipeline.
- The no-RTVI bot emitted no `OutputTransportMessageUrgentFrame(... rtvi-ai ...)`
  messages.
- The no-RTVI bot received and dropped incoming Daily app messages from the
  normal bot.
- No RTVI validation/error feedback loop appeared.
- Audio crosstalk still happened in both directions.

Evidence:

```text
normal log:    UserAudioRawFrame(... user: 647933ef-210c-4ef6-8dbe-49a386d5d76f, source: microphone ...)
no-RTVI log:   UserAudioRawFrame(... user: 5e98e90b-aafa-4d0f-80d5-bdcb3ee08377, source: microphone ...)
```

Counts from the filtered logs:

```text
normal bot:
  RTVIProcessor                              409
  OutputTransportMessageUrgentFrame rtvi-ai 700
  UserAudioRawFrame from no-RTVI participant 5808
  Invalid/validation errors                 0

no-RTVI bot:
  RTVIProcessor                              0
  OutputTransportMessageUrgentFrame rtvi-ai 0
  Dropped Daily input messages              95
  UserAudioRawFrame from normal participant 5652
  Invalid/validation errors                 0
```

Conclusion from this test:

- Disabling RTVI on one participant prevents the RTVI validation/error feedback
  loop.
- It does not prevent Daily audio crosstalk.
- The audio crosstalk is caused by Daily transport participant audio capture, not
  by the second participant acting as an RTVI server.

## Gradient Bang-Specific Amplifiers

Gradient Bang likely adds additional causes or amplifiers:

- It uses Daily audio input with default participant audio behavior.
- It appears to add agents on every `on_client_connected` participant event.
- Its mute strategy is global rather than scoped to the intended participant.
- Browser/listener participants can be treated as active input participants.
- App-message and transcription handling may assume there is only one active
  user-like participant.

Earlier Gradient Bang tests showed:

- No-browser control: transcriptions came from one participant and responses were
  usually around 2-4 seconds.
- Browser/headless joined: transcriptions split across the bot participant and
  the browser participant, with observed delays up to tens of seconds.

## Current Working Theory

This is probably not acoustic echo.

The more likely cause is that multiple Daily participants are being treated as
active audio/STT participants:

- The game bot captures audio from our bot.
- The game bot may also capture audio from browser/listener participants.
- Fake browser devices still publish microphone frames.
- Turn detection and user aggregation can be delayed or confused by multiple
  simultaneous audio sources.
- RTVI app-message broadcasts can add extra room-level message noise when more
  than one Pipecat bot is present.

## Candidate Fixes / Tests

1. Test `DailyParams(audio_in_user_tracks=False)`.
2. Explicitly subscribe to or capture audio from only the intended controlling
   participant.
3. In Gradient Bang, choose one controlling participant and ignore or unsubscribe
   all listener/browser participants.
4. Do not add game/user agents on every `on_client_connected`; gate that behavior
   to the intended participant.
5. Make mute/unmute state participant-scoped instead of global.
6. Target RTVI/app messages to a specific participant where possible.
7. Filter inbound `rtvi-ai` app messages so bot-originated output messages are
   not parsed as inbound client commands by other bots.
