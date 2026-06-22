"""cli.py — the terminal face of SERENE (handy for quick testing).
The GUI is the main face; both share the same Session logic."""
import serene.router as router
from serene.session import Session


def run():
    session = Session()
    print("SERENE ready. 'quit' to exit. '/switch <brain>' to change brain. "
          "'/memory on|off' for private chat.\n")

    while True:
        user_msg = input("You: ")

        if user_msg.lower() in ("quit", "exit"):
            print("SERENE: Let me remember our chat...")
            report = session.end()
            if report:
                print(report)
            break

        if user_msg.startswith("/switch"):
            router.switch(user_msg.split(" ")[1])
            print(f"SERENE: Switched to {router.active_brain}.")
            continue

        if user_msg.startswith("/memory"):
            parts = user_msg.split()
            if len(parts) > 1 and parts[1].lower() in ("on", "off"):
                on = session.set_memory(parts[1].lower() == "on")
                print("SERENE: Memory ON — I'll remember this chat." if on
                      else "SERENE: Memory OFF — this chat won't be saved.")
            else:
                state = "ON" if session.memory_on else "OFF"
                print(f"SERENE: Memory is {state}. Use '/memory on' or '/memory off'.")
            continue

        print("SERENE:", session.send(user_msg))


if __name__ == "__main__":
    run()
