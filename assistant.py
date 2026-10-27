"""Run with python assistant.py; importing this module never loads credentials."""
from personal_assistant.app import main

if __name__ == "__main__":
    raise SystemExit(main())
