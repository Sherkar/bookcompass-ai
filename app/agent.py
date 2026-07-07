# ruff: noqa
import os
import re
import json
import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from google.adk.agents import Agent, LlmAgent
from google.adk.workflow import Workflow, node, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import AgentTool
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.genai import types

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .config import config

# ----------------------------------------------------------------------
# 1. Pydantic Schemas
# ----------------------------------------------------------------------
class BookDetails(BaseModel):
    title: str = Field(description="Title of the book")
    author: str = Field(description="Author of the book")
    difficulty: str = Field(description="Difficulty level (Beginner/Intermediate/Advanced)")
    reading_time: str = Field(description="Estimated reading time (e.g. '12 Hours')")
    why_recommended: str = Field(description="Brief reason why this book is recommended")

class RecommendationOutput(BaseModel):
    books: List[BookDetails] = Field(description="List of 3 to 5 recommended books")

class RoadmapOutput(BaseModel):
    roadmap: List[str] = Field(description="List of book titles in the recommended reading order")
    skills_learned: List[str] = Field(description="List of skills that will be acquired")
    estimated_completion_time: str = Field(description="Estimated completion time (e.g. '6 Weeks')")
    recommendation_score: int = Field(description="Overall match score from 0 to 100")

class OrchestratorOutput(BaseModel):
    books_summary: str = Field(description="Friendly markdown summary of the recommended books and reading roadmap")
    books_json: str = Field(description="The raw JSON string returned by recommender_agent")
    roadmap_json: str = Field(description="The raw JSON string returned by roadmap_agent")

# ----------------------------------------------------------------------
# 2. MCP Server Configuration & Integration
# ----------------------------------------------------------------------
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", os.path.join(project_dir, "app", "mcp_server.py")],
        )
    )
)

# ----------------------------------------------------------------------
# 3. Specialized LLM Sub-Agents
# ----------------------------------------------------------------------
recommender_agent = LlmAgent(
    name="recommender_agent",
    model=Gemini(model=config.model),
    instruction="""You are a book recommendation specialist.
Use the search_books_by_topic tool to find curated books on the user's topic.
If you need details on a specific book, use get_book_details_by_title.
Provide details matching the output schema.
Rely on the tool results for book names, authors, difficulties, and reading times.""",
    tools=[mcp_toolset],
    output_schema=RecommendationOutput,
)

roadmap_agent = LlmAgent(
    name="roadmap_agent",
    model=Gemini(model=config.model),
    instruction="""You are a reading curriculum planner.
Given the list of books, sequence them logically (from easiest to hardest, or foundational to advanced).
Use the calculate_reading_pace tool to estimate the daily pace and completion timeline (assume the user has 10 study hours per week).
Return the roadmap, skills learned, estimated completion time, and match score according to the output schema.""",
    tools=[mcp_toolset],
    output_schema=RoadmapOutput,
)

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=Gemini(model=config.model),
    instruction="""You are the BookCompass AI Reading Concierge.
The user wants to learn a specific topic. Your task is:
1. Call the `recommender_agent` tool to get recommended books for the user's goal.
2. Call the `roadmap_agent` tool with the recommended books to get the reading roadmap.
3. Populate the output schema.
- `books_summary`: A beautiful markdown summary showing the list of books, difficulties, reasons, reading order, skills, and overall score.
- `books_json`: The exact raw JSON output from `recommender_agent` (serialize it as a string if needed).
- `roadmap_json`: The exact raw JSON output from `roadmap_agent` (serialize it as a string if needed).

Never make up your own recommendations; always call the sub-agents.
""",
    output_schema=OrchestratorOutput,
    tools=[AgentTool(recommender_agent), AgentTool(roadmap_agent)],
)

# ----------------------------------------------------------------------
# 4. Workflow Nodes
# ----------------------------------------------------------------------
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    text = ""
    if hasattr(node_input, "parts") and node_input.parts:
        text = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, str):
        text = node_input
    
    audit_log = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "event": "security_checkpoint_scan",
        "input_length": len(text),
        "pii_scrubbed": False,
        "injection_detected": False,
        "domain_violation": False,
        "severity": "INFO"
    }
    
    # 1. PII Scrubbing
    scrubbed_text = text
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    phone_pattern = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    
    if re.search(email_pattern, scrubbed_text):
        scrubbed_text = re.sub(email_pattern, "[EMAIL_REDACTED]", scrubbed_text)
        audit_log["pii_scrubbed"] = True
    if re.search(phone_pattern, scrubbed_text):
        scrubbed_text = re.sub(phone_pattern, "[PHONE_REDACTED]", scrubbed_text)
        audit_log["pii_scrubbed"] = True
        
    # 2. Prompt Injection detection
    injection_keywords = [
        "ignore instructions", "ignore previous instructions", "system prompt", 
        "dan mode", "ignore rules", "you are now a", "bypass security"
    ]
    for kw in injection_keywords:
        if kw in text.lower():
            audit_log["injection_detected"] = True
            audit_log["severity"] = "CRITICAL"
            print(json.dumps(audit_log))
            return Event(output=f"Prompt injection pattern detected: '{kw}'", route="unsafe")
            
    # 3. Domain-specific rule (e.g. Block command injections or system attacks)
    domain_block_keywords = ["rm -rf", "format c:", "drop table", "shutdown", "eval("]
    for kw in domain_block_keywords:
        if kw in text.lower():
            audit_log["domain_violation"] = True
            audit_log["severity"] = "WARNING"
            print(json.dumps(audit_log))
            return Event(output=f"Unallowed system command keyword detected: '{kw}'", route="unsafe")
            
    # Output Audit Log
    if audit_log["pii_scrubbed"]:
        audit_log["severity"] = "WARNING"
    print(json.dumps(audit_log))
    
    return Event(output=scrubbed_text, route="clean", state={"goal": scrubbed_text})

def security_event(ctx: Context, node_input: str) -> Event:
    msg = f"### ⚠️ Security Checkpoint Violation\n\nYour request was flagged by the BookCompass security filter. Reason: {node_input}"
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=msg)]))
    yield Event(output=msg)

@node(rerun_on_resume=True)
async def orchestrator_node(ctx: Context, node_input: str) -> OrchestratorOutput:
    goal = ctx.state.get("goal")
    feedback = ctx.state.get("user_feedback", "")
    
    prompt = f"Goal: {goal}"
    if feedback:
        prompt += f"\nUser feedback/requested changes: {feedback}\nPlease adjust the recommendations accordingly."
        
    result = await ctx.run_node(orchestrator_agent, node_input=prompt)
    return result

@node(rerun_on_resume=True)
async def human_review(ctx: Context, node_input: dict) -> Event:
    summary = node_input.get("books_summary", "No summary generated.")
    
    if not ctx.resume_inputs:
        # Store in state
        ctx.state["books_summary"] = summary
        ctx.state["raw_books_json"] = node_input.get("books_json", "{}")
        ctx.state["raw_roadmap_json"] = node_input.get("roadmap_json", "{}")
        
        message = (
            f"### Proposed Learning Roadmap\n\n"
            f"{summary}\n\n"
            f"✋ **Human Review Required**\n"
            f"Do you approve this reading roadmap? (Reply 'yes' to confirm and generate the final output, "
            f"or describe any changes you would like to make.)"
        )
        yield RequestInput(interrupt_id="approve_books", message=message)
        return
        
    # User responded
    user_response = ctx.resume_inputs.get("approve_books", "").strip()
    ctx.state["user_feedback"] = user_response
    
    if user_response.lower() in ["yes", "y", "approve", "confirm", "ok"]:
        yield Event(output="approved", route="approved")
    else:
        yield Event(output="modify", route="modify")

def final_generation(ctx: Context, node_input: str) -> Event:
    books_summary = ctx.state.get("books_summary", "")
    raw_books = ctx.state.get("raw_books_json", "{}")
    raw_roadmap = ctx.state.get("raw_roadmap_json", "{}")
    
    try:
        books_data = json.loads(raw_books) if isinstance(raw_books, str) else raw_books
        roadmap_data = json.loads(raw_roadmap) if isinstance(raw_roadmap, str) else raw_roadmap
    except Exception:
        books_data = {}
        roadmap_data = {}
        
    books_list = books_data.get("books", []) if isinstance(books_data, dict) else []
    roadmap_list = roadmap_data.get("roadmap", []) if isinstance(roadmap_data, dict) else []
    skills = roadmap_data.get("skills_learned", []) if isinstance(roadmap_data, dict) else []
    est_time = roadmap_data.get("estimated_completion_time", "N/A") if isinstance(roadmap_data, dict) else "N/A"
    score = roadmap_data.get("recommendation_score", 100) if isinstance(roadmap_data, dict) else 100
    
    formatted_books = ""
    for i, book in enumerate(books_list, 1):
        formatted_books += (
            f"**{i}. {book.get('title')}** by *{book.get('author')}*\n"
            f"  * **Difficulty:** {book.get('difficulty')}\n"
            f"  * **Reading Time:** {book.get('reading_time')}\n"
            f"  * **Why Recommended:** {book.get('why_recommended')}\n\n"
        )
        
    formatted_roadmap = " ➔ ".join(f"`{title}`" for title in roadmap_list)
    formatted_skills = "\n".join(f"✓ {skill}" for skill in skills)
    
    final_text = (
        f"# 🧭 BookCompass AI — Your Reading Roadmap\n\n"
        f"Here is your personalized reading guide:\n\n"
        f"## 📚 Recommended Books\n\n"
        f"{formatted_books}"
        f"## 🗺️ Reading Roadmap\n\n"
        f"{formatted_roadmap}\n\n"
        f"## 🎓 Learning Outcomes\n\n"
        f"After completing this roadmap, you will learn:\n"
        f"{formatted_skills}\n\n"
        f"## ⏱️ Estimated Completion Time\n\n"
        f"**{est_time}**\n\n"
        f"## 🎯 Recommendation Score\n\n"
        f"**{score}% Highly Recommended**\n"
    )
    
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=final_text)]))
    yield Event(output=final_text)

# ----------------------------------------------------------------------
# 5. Workflow Definition
# ----------------------------------------------------------------------
root_agent = Workflow(
    name="bookcompass_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {
            "clean": orchestrator_node,
            "unsafe": security_event,
        }),
        (orchestrator_node, human_review),
        (human_review, {
            "approved": final_generation,
            "modify": orchestrator_node,
        }),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(enabled=True),
)
