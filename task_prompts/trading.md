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
