# Telegram multi-bot word chain

Hermes Telegram now treats Telegram as a transport only. Each Telegram bot calls into Hermes core; model providers such as 9router remain below Hermes.

## Full mentions only

Use full Telegram usernames:

- `@Swain_SubAgent_bot`
- `@Shen_SubAgent_bot`
- `@Garen_SubAgent_bot`
- `@Kayn_SubAgent_bot`

Short aliases such as `@Swain` are intentionally not accepted.

## Environment

Configure the local `.env`; do not commit tokens.

```env
TELEGRAM_ALLOWED_CHAT_ID=-5414474882
TELEGRAM_BOT_USERNAMES=Swain_SubAgent_bot,Shen_SubAgent_bot,Garen_SubAgent_bot,Kayn_SubAgent_bot
TELEGRAM_SWAIN_BOT_TOKEN=
TELEGRAM_SHEN_BOT_TOKEN=
TELEGRAM_GAREN_BOT_TOKEN=
TELEGRAM_KAYN_BOT_TOKEN=
```

`TELEGRAM_BOT_TOKEN` remains a legacy fallback for Swain only.

## Word-chain game

Start a 10-turn English word-chain with:

```text
@Swain_SubAgent_bot /chain apple
```

Rules:

- the next English word starts with the previous word's last letter;
- the chain length is 10 turns;
- the turn selector prioritizes bots that have not spoken yet, so all four bots are used before random cycling continues;
- the local runner sends each turn through that bot's own token;
- messages from bots are ignored by the poller to prevent recursive loops.

Telegram bot-to-bot delivery is not relied on. Hermes orchestrates the chain and emits the per-bot messages itself.
