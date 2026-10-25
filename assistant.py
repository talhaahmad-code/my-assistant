
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load environment variables from project directory
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# Local AI configuration
MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat",
)

# Telegram configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

# Assistant configuration
TIMEZONE = os.getenv("TIMEZONE", "America/Toronto")

# Validate required configuration
if not TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")

if not ALLOWED_USER:
    raise ValueError("Missing TELEGRAM_ALLOWED_USER_ID in .env")

def request_json(url, payload=None, timeout=45):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def telegram(method, payload):
    result = request_json(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        payload,
        timeout=45,
    )
    if not result.get("ok"):
        raise RuntimeError("Telegram API request failed")
    return result["result"]


def send_message(chat_id, text):
    telegram("sendMessage", {
        "chat_id": chat_id,
        "text": text[:4000],
    })


# Our first tool: weather forecast
def get_weather():
    params = urlencode({
        "latitude": 45.31,
        "longitude": -75.90,
        "timezone": TIMEZONE,
        "forecast_days": 1,
        "daily": (
            "weather_code,temperature_2m_max,"
            "temperature_2m_min,precipitation_sum,"
            "precipitation_probability_max"
        ),
    })

    data = request_json(
        "https://api.open-meteo.com/v1/forecast?" + params
    )["daily"]

    return {
        "location": "Kanata, Ottawa",
        "date": data["time"][0],
        "high_c": data["temperature_2m_max"][0],
        "low_c": data["temperature_2m_min"][0],
        "precipitation_mm": data["precipitation_sum"][0],
        "peak_hourly_rain_or_snow_probability_pct":
            data["precipitation_probability_max"][0],
        "wmo_weather_code": data["weather_code"][0],
    }


# Describe available tools to the model
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "Get today's weather forecast for Kanata, Ottawa. "
            "Use this for weather, temperature, rain, snow, "
            "clothing, or umbrella questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}]


def ollama_chat(messages, tools):
    result = request_json(OLLAMA_URL, {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "think": False,
        "stream": False,
    }, timeout=180)
    return result["message"]


# Our agent's reasoning and tool-execution loop
def run_agent(user_message):
    now = datetime.now(ZoneInfo(TIMEZONE)).isoformat()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a concise personal AI assistant. "
                f"The current local time is {now}. "
                "Use tools for information requiring live data. "
                "Never invent weather observations. "
                "The precipitation probability returned by the "
                "weather tool is the maximum hourly probability, "
                "not an all-day probability. "
                "If a tool fails, acknowledge the failure."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    response = ollama_chat(messages, TOOLS)

    if not response.get("tool_calls"):
        return response.get("content") or "I couldn't answer that."

    messages.append(response)

    # Only explicitly approved tool names can execute.
    for call in response["tool_calls"][:2]:
        name = call["function"]["name"]

        if name == "get_weather":
            try:
                result = get_weather()
            except Exception:
                result = {"error": "Weather service unavailable"}
        else:
            result = {"error": "Unknown or unauthorized tool"}

        messages.append({
            "role": "tool",
            "tool_name": name,
            "content": json.dumps(result),
        })

    # Ask the model to interpret the tool result
    final = ollama_chat(messages, [])
    return final.get("content") or "No response generated."


def main():
    print("Assistant is running. Press Ctrl+C to stop.")
    offset = None

    while True:
        try:
            updates = telegram("getUpdates", {
                "offset": offset,
                "timeout": 25,
                "allowed_updates": ["message"],
            })

            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat = message.get("chat", {})
                sender = message.get("from", {})
                text = message.get("text", "")

                if chat.get("type") != "private" or not text:
                    continue

                chat_id = chat["id"]
                user_id = sender.get("id")

                # Reject every unauthorized sender before processing commands
                if not ALLOWED_USER or user_id != ALLOWED_USER:
                    continue

                if text.startswith("/start"):
                    send_message(chat_id, "Hello! Ask me about the weather.")
                    continue

                try:
                    answer = run_agent(text[:2000])
                except Exception:
                    answer = (
                        "Something went wrong. Check Ollama "
                        "and the local terminal."
                    )

                send_message(chat_id, answer)

        except KeyboardInterrupt:
            print("\nAssistant stopped.")
            break
        except Exception as error:
            print(f"Connection or processing error: {type(error).__name__}")
            time.sleep(5)


if __name__ == "__main__":
    main()
