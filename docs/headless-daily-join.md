# Headless Daily Join Runbook

Use this when reproducing the performance issue with an extra Daily participant.
Each game run creates a new Daily room, so always extract the room URL and token
from the current bot process before joining.

## Start the bot and capture logs

From the `gb-bot` repo:

```bash
mkdir -p logs
LOGFILE="logs/bot-debug-$(date +%Y%m%d-%H%M%S).log"
LOG_LEVEL=DEBUG GB_LOG_DAILY_JOIN_URL=true uv run bot.py 2>&1 | tee "$LOGFILE"
```

For local reproduction only, `GB_LOG_DAILY_JOIN_URL=true` prints the Daily join
token into logs. Keep those logs private. The game bot service logs usually
include a line like:

```text
Bot started with runner_args: ... room_url='https://your-domain.daily.co/pipecat-...' token='...'
```

Build the join URL as:

```text
<room_url>?t=<token>
```

## Join the room in headless Chromium

Use the fresh `ROOM_URL` and `TOKEN` values from the current run:

```bash
ROOM_URL='https://your-domain.daily.co/pipecat-...'
TOKEN='...'

rm -rf /tmp/gb-daily-headless-profile
chromium \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --remote-debugging-port=9223 \
  --user-data-dir=/tmp/gb-daily-headless-profile \
  --use-fake-ui-for-media-stream \
  --use-fake-device-for-media-stream \
  --autoplay-policy=no-user-gesture-required \
  --no-first-run \
  --no-default-browser-check \
  "$ROOM_URL?t=$TOKEN"
```

Leave this process running. Closing it removes the headless Daily participant.

## Verify the headless participant joined

In another shell, query Chromium over the DevTools protocol:

```bash
node <<'NODE'
const http = require("http");

function getJson(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: "127.0.0.1", port: 9223, path }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => resolve(JSON.parse(data)));
    }).on("error", reject);
  });
}

(async () => {
  const targets = await getJson("/json");
  const page = targets.find((target) => target.type === "page");
  if (!page) throw new Error("no page target");

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
  };

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const message = { id: ++id, method, params };
      pending.set(message.id, { resolve, reject });
      ws.send(JSON.stringify(message));
    });
  }

  await new Promise((resolve) => (ws.onopen = resolve));
  await send("Runtime.enable");
  await new Promise((resolve) => setTimeout(resolve, 8000));
  const result = await send("Runtime.evaluate", {
    expression: "document.body.innerText",
    returnByValue: true,
  });
  console.log(result.result.value);
  ws.close();
})();
NODE
```

Expected output includes text like:

```text
2 people in call
Guest (You)
```

The Daily prebuilt UI may join directly without a visible join button. If the
page stops at the get-ready screen, inspect `document.body.innerText` and click
the visible join button through DevTools.

## Capture game service logs

To compare against the bot log:

```bash
LOGFILE="logs/gradient-bang-service-$(date +%Y%m%d-%H%M%S).log"
journalctl --user -u gradient-bang-bot.service --since now -f --no-pager 2>&1 | tee "$LOGFILE"
```

Useful checks:

```bash
rg "type': 'user-transcription'" logs/bot-debug-*.log | rg -o "user_id': '[^']+'" | sort | uniq -c
rg "Participant joined|Client connected|already has parent" logs/gradient-bang-service-*.log
```
