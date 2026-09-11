import sys
import os

# Set stdout/stderr to utf-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marketplace.agent import root_agent

if __name__ == "__main__":
    import asyncio
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    async def main():
        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name="marketplace", user_id="user_cli")
        runner = Runner(agent=root_agent, app_name="marketplace", session_service=session_service)

        print("\n" + "=" * 65)
        print("DevOps Multi-Agent Marketplace Interactive Terminal")
        print("Specialists: git_specialist | jenkins_specialist | sonar_specialist")
        print("Type your message and press Enter. (Type 'exit' or 'quit' to quit)")
        print("=" * 65 + "\n")

        # If arguments passed, e.g.: python run.py "List my repos"
        if len(sys.argv) > 1:
            initial_query = " ".join(sys.argv[1:])
            print(f"User > {initial_query}\n\nAgent > ", end="", flush=True)
            msg = Content(role="user", parts=[Part.from_text(text=initial_query)])
            async for event in runner.run_async(session_id=session.id, user_id="user_cli", new_message=msg):
                if hasattr(event, "content") and event.content:
                    for p in event.content.parts:
                        if getattr(p, "text", None):
                            print(p.text, end="", flush=True)
                if hasattr(event, "actions") and event.actions and event.actions.transfer_to_agent:
                    print(f"\n[-> Delegating to {event.actions.transfer_to_agent}...]\n", flush=True)
            print("\n")
            return

        while True:
            try:
                user_input = input("User > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    print("Goodbye!")
                    break

                msg = Content(role="user", parts=[Part.from_text(text=user_input)])
                print("\nAgent > ", end="", flush=True)
                async for event in runner.run_async(session_id=session.id, user_id="user_cli", new_message=msg):
                    if hasattr(event, "content") and event.content:
                        for p in event.content.parts:
                            if getattr(p, "text", None):
                                print(p.text, end="", flush=True)
                    if hasattr(event, "actions") and event.actions and event.actions.transfer_to_agent:
                        print(f"\n[-> Delegating to {event.actions.transfer_to_agent}...]\n", flush=True)
                print("\n")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                break

    asyncio.run(main())
