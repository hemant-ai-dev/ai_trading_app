# Paper workers and internal tasks

The Workers portal consumes the same internal task API as chat.

Typical intents: monitor a symbol, notify on a price trigger, prepare a paper buy/sell that still requires approval.

Lifecycle: queued → planning → monitoring → awaiting_approval → executing (paper) → completed.

Nothing in this path is a live exchange order. Broker integration, if added later, must stay on separate execution endpoints with stronger authorization.
