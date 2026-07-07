import asyncio
from google.adk.runners import InMemoryRunner
from app.agent import app
from google.genai import types
from google.genai.errors import ServerError

async def run_with_retry(runner, user_id, session_id, new_message=None, resume_inputs=None, max_retries=5):
    for attempt in range(1, max_retries + 1):
        events = []
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
                resume_inputs=resume_inputs
            ):
                events.append(event)
            return events
        except ServerError as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"\n[Warning]: Gemini server under high demand (503). Retrying attempt {attempt}/{max_retries} in 10s...")
                await asyncio.sleep(10)
                if attempt == max_retries:
                    raise e
            else:
                raise e

async def main():
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="user"
    )
    print(f"=== Session Created: {session.id} ===")
    
    print("\n--- Sending Learning Goal ---")
    events = await run_with_retry(
        runner,
        user_id="user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="I want to learn Java backend development")])
    )
    
    for event in events:
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
        events2 = await run_with_retry(
            runner,
            user_id="user",
            session_id=session.id,
            resume_inputs={interrupt.id: "yes"}
        )
        
        for event in events2:
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="")
            if event.output:
                print(f"\n[Final Output]: {event.output}")

if __name__ == "__main__":
    asyncio.run(main())
