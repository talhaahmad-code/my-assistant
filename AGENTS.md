# Repository instructions

- Keep responses concise and explain meaningful design decisions. This is a learning project.
- Preserve Telegram long polling, authorized private chats, local Ollama inference and Kanata weather behavior.
- All inference must run locally. Never introduce cloud inference or fallback services. Keep loopback validation, verified HTTPS, and bounded execution.
- Never open, read, print, search or otherwise access `.env`, credentials, secret stores, or sensitive shell environment values. Use `.env.example` only. Avoid broad hidden-file searches. Never run the live bot or credential-dependent tests.
- Never log secrets, user/chat identifiers, raw prompts/conversations, API URLs containing tokens, or raw exception text. Use safe event categories.
- Prefer standard-library Python, type hints and small concrete modules. Keep python-dotenv as the only third-party dependency unless a clear need is discussed. Avoid agent frameworks and unused future-feature placeholders.
- Validate model output, tool names and arguments. Never add arbitrary shell execution or unrestricted filesystem tools. Sensitive actions require separately designed permissions and approvals.
- Use `python3 -m unittest discover -v`; tests must remain offline and use placeholder settings. Run focused tests after meaningful increments and the full suite before completion.
- Keep README, docs/architecture.md and .env.example aligned with actual behavior. Distinguish implemented features from plans and offline verification from live testing.
- Preserve existing Git history and user changes. Do not create commits, tags or branches without explicit approval; never amend the baseline. Keep .env ignored.
