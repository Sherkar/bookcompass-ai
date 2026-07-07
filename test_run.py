import asyncio
from google.adk.runners import InMemoryRunner
from app.agent import app
from google.genai import types

async def main():
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="user"
    )
    print(f"=== Session Created: {session.id} ===")
    
    print("\n--- Sending Learning Goal ---")
    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="I want to learn Java backend development")]),
    ):
        # Print intermediate outputs
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(part.text, end="")
        if event.output:
            print(f"\n[Output Event]: {event.output}")
            
    # Check if there are active interrupts (human-in-the-loop)
    active_session = await runner.session_service.get_session(app_name="app", session_id=session.id, user_id="user")
    if active_session.active_interrupts:
        print("\n\n--- Workflow Paused for Human-in-the-Loop Review ---")
        interrupt = active_session.active_interrupts[0]
        print(f"Interrupt ID: {interrupt.id}")
        
        # Approve the proposal
        print("\n--- Sending Human Approval (Reply 'yes') ---")
        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            resume_inputs={interrupt.id: "yes"}
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="")
            if event.output:
                print(f"\n[Final Output]: {event.output}")

if __name__ == "__main__":
    asyncio.run(main())
