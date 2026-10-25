# My AI Assistant

A small, self-hosted personal AI agent built in Python. The goal is to learn how an agent works from the ground up while keeping **all AI inference on hardware I control**.

The first version (v0.1) accepts messages through a private Telegram bot, uses a local model to decide when a tool is needed, fetches today's weather forecast for Kanata (Ottawa), and replies in natural language. It does not use OpenClaw, LangChain, cloud LLMs, or a web UI.

> **Privacy boundary:** *Local inference* does not mean *offline*. Model inference runs on the local machine. Telegram carries chat messages through its servers, and [Open-Meteo](https://open-meteo.com/en/docs) receives the configured weather coordinates when a forecast is requested. No chat messages are sent to a hosted AI model.

## Current capabilities

- Chat through a Telegram bot, without opening inbound ports on the home router (Telegram long polling).
- Restrict normal chat requests to one configured Telegram user ID.
- Run [Qwen3.5 4B](https://ollama.com/library/qwen3.5:4b) locally with [Ollama](https://ollama.com/).
- Allow the model to choose the narrowly defined `get_weather` tool.
- Retrieve a forecast for Kanata using the Open-Meteo API.
- Generate a concise, natural-language answer using the local model.

**Not implemented yet:** conversation history across messages, persistent memory, scheduled notifications, configurable locations, iMessage integration, background service management, and a comprehensive test suite.

## Architecture

```text
Telegram app
    |
    | Telegram Bot API (outbound long polling)
    v
assistant.py  [runs on my Mac]
    |-- Verify sender / route messages
    |-- Agent loop: prompt -> model -> optional tool -> model -> reply
    |       |
    |       +-- Ollama (localhost:11434) -> Qwen3.5 4B
    |       |
    |       +-- get_weather() -> Open-Meteo HTTPS API
    |
    +-- Send response through Telegram
```

The Python application controls which tools may execute. The model can *request* `get_weather`, but it cannot execute arbitrary shell commands, read arbitrary files, or call arbitrary external services through the tool registry.

## Requirements

- A Mac with Apple Silicon (initially developed for a **2022 M2 MacBook Air with 16 GB RAM**). A Linux machine may be supported later.
- Python **3.11 or later**.
- [Ollama for macOS](https://ollama.com/download/mac).
- Internet access for Telegram and live weather forecasts.
- A Telegram account and a bot created through [@BotFather](https://t.me/BotFather).

## Setup

### 1. Clone the project and create a Python environment

If you already have the project locally, open its directory instead of cloning:

```bash
cd ~/my-assistant
python3 --version        # Python 3.11+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For the current implementation, `requirements.txt` contains:

```text
python-dotenv
```

### 2. Install Ollama and download the model

Install Ollama and open the app, then run:

```bash
ollama pull qwen3.5:4b
ollama run qwen3.5:4b
```

Try a question, then enter `/bye` to exit the model's interactive chat. Ollama itself should remain running in the background while the assistant is running.

To confirm the local API is available:

```bash
curl http://127.0.0.1:11434/api/tags
```

### 3. Explicitly disable Ollama cloud features

Create or edit `~/.ollama/server.json` (preserve any settings already in the file) so it includes:

```json
{
  "disable_ollama_cloud": true
}
```

Restart Ollama afterward. This prevents the Ollama runtime from using its optional cloud model and web-search features. See the [official Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx#how-do-i-disable-ollama-cloud-features).

The assistant is configured to call the Ollama API at `127.0.0.1`, not a remote endpoint.

### 4. Create a Telegram bot

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` and follow the prompts.
3. Copy the bot token. Treat it as a password; anyone with it can control your bot.
4. Open a **private chat** with your new bot and send `/start`.

You also need your **numeric Telegram user ID**, not your username. See the bootstrap instructions below.

### 5. Set up local configuration and secrets

Copy the safe template into a private local file:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` with your own values:

```dotenv
# Telegram
TELEGRAM_BOT_TOKEN=replace_with_your_bot_token
TELEGRAM_ALLOWED_USER_ID=123456789

# Local AI
OLLAMA_URL=http://127.0.0.1:11434/api/chat
OLLAMA_MODEL=qwen3.5:4b

# Assistant
TIMEZONE=America/Toronto
```

**How to discover your Telegram user ID with the current v0.1 code:** the assistant requires a nonzero `TELEGRAM_ALLOWED_USER_ID` to start, but its `/id` command is available before the allowlist check. For the **first run only**, use `TELEGRAM_ALLOWED_USER_ID=1` as a temporary placeholder, start the assistant, and send `/id` in the private bot chat. It will reply with *your* numeric ID. Stop the program, replace `1` in `.env` with your actual ID, and restart. Other users cannot execute normal agent requests without matching the configured ID. (A future version should implement a cleaner setup command.)

**Do not commit `.env`.** It should be excluded in `.gitignore`; `.env.example` should be safe to commit because it contains placeholders only.

Note: `python-dotenv` does not overwrite variables already exported in your shell by default. If you previously used `export TELEGRAM_ALLOWED_USER_ID=...`, run `unset TELEGRAM_ALLOWED_USER_ID` so `.env` takes effect.

### 6. Run the assistant

In a terminal:

```bash
cd ~/my-assistant
source .venv/bin/activate
python assistant.py
```

You should see:

```text
Assistant is running. Press Ctrl+C to stop.
```

Message your Telegram bot:

> What's the weather like today? Should I bring an umbrella?

The bot should retrieve the weather and respond using the local model. Stop it with **Ctrl+C**.

The Mac must remain awake and connected while the bot is running. The initial prototype is not installed as an automatic background service.

## Project files

```text
my-assistant/
├── assistant.py       # Telegram polling, local LLM agent loop, weather tool
├── requirements.txt   # Python dependencies
├── .env.example       # Safe configuration template (committed)
├── .env               # Actual secrets/configuration (NEVER committed)
├── .gitignore         # Git exclusions
└── README.md          # Project overview and instructions
```

## Security and privacy

- **Local model:** The assistant sends AI prompts to Ollama at `http://127.0.0.1:11434/api/chat`. Ollama cloud features should be disabled as described above.
- **Telegram:** Telegram bot conversations are **not end-to-end encrypted**. Do not send sensitive secrets or private documents through this channel.
- **Weather:** Open-Meteo receives the preset coordinates for Kanata when weather is requested, not the full conversation.
- **Authorization:** Normal incoming text is processed only when its Telegram user ID matches `TELEGRAM_ALLOWED_USER_ID`. The `/id` setup command replies with the sender's own ID even before authorization.
- **Tools:** The current code allowlists only `get_weather`; it does not provide shell execution or general filesystem access.
- **Secrets:** Keep credentials in `.env`, never in source files, Git commits, screenshots, or issue reports. Rotate the bot token if it is exposed.
- **Home network:** Telegram long polling does not require forwarding router ports. Keep Ollama bound to localhost.

Before your first commit, verify:

```bash
git status --short
git check-ignore -v .env
```

If `.env` was already committed, `.gitignore` alone will not remove it from Git history; remove the tracked secret and rotate the exposed credentials.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `Missing TELEGRAM_BOT_TOKEN in .env` | Confirm `.env` is in the same directory as `assistant.py` and contains a token. |
| `Missing TELEGRAM_ALLOWED_USER_ID in .env` | Set a nonzero numeric ID (use the temporary bootstrap value `1` if needed). |
| Bot doesn't answer | Confirm `python assistant.py` is still running, you sent a private message, and your Telegram ID matches the allowlist. |
| Ollama connection error | Open Ollama; confirm `curl http://127.0.0.1:11434/api/tags` works. |
| Model not found | Run `ollama pull qwen3.5:4b`; check `OLLAMA_MODEL` in `.env`. |
| Slow answer | The first response may load the model into memory. Keep other memory-intensive apps closed. |
| Telegram polling error | Check internet access and the token. A bot can't use long polling while an incoming webhook is configured. |
| Weather unavailable | Check internet connectivity and availability of the Open-Meteo API. |

## Roadmap

- [x] Initial local Ollama integration
- [x] Telegram channel adapter
- [x] First tool: today's weather forecast
- [x] `.env`-based configuration
- [ ] Refactor into independent `agent/`, `channels/`, and `tools/` modules
- [ ] Unit tests and clearer error handling
- [ ] Optional location parameter and hourly weather forecasts
- [ ] Short-term conversation state and persistent local memory
- [ ] Local scheduling / morning weather alerts
- [ ] iMessage channel adapter
- [ ] Dedicated always-on home server

> The checked items indicate functionality in the **initial code**, not completed integration testing on every machine.

## Useful links

- [Ollama](https://ollama.com/) and [Qwen3.5 models](https://ollama.com/library/qwen3.5)
- [Ollama cloud settings FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx#how-do-i-disable-ollama-cloud-features)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Open-Meteo API](https://open-meteo.com/en/docs)

## License

No license has been selected yet. Add a `LICENSE` file before publicly inviting reuse or contributions.
