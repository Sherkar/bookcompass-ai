# 🗺️ Submission Write-up — BookCompass AI

## 1. Problem Statement
Many learners spend excessive time deciding what books to read, in what order, and how to schedule their study hours. Traditional searches or simple LLM prompts return flat lists of recommendations without logical sequencing, time commitments, or explanation of fit. There is a clear need for a secure, interactive concierge that plans structured, customized reading roadmaps matching a user's learning speed and preferences.

## 2. Solution Architecture
BookCompass AI solves this by building a graph-based multi-agent reading assistant. The flow is structured as a robust stateful workflow:

```mermaid
graph TD
    START((User Input)) --> SC[Security Checkpoint]
    SC -- clean --> ON[Orchestrator Node]
    SC -- unsafe --> SE[Security Event]
    
    ON --> HR{Human Review Node}
    HR -- approved --> FG[Final Generation]
    HR -- modify --> ON
    
    sub-agents -- tool calls --- ON
    sub-agents["Specialized Sub-Agents<br>(recommender_agent, roadmap_agent)"]
    MCP[MCP Server] -- stdio -- tools --- sub-agents
    
    FG --> FinalOutput[Final Rendered Roadmap]
    SE --> ErrorOutput[Security Blocked Output]
```

## 3. Concepts Used
- **ADK 2.0 Workflows**: Graph topology configured with nodes and edges defined in [app/agent.py](file:///c:/AI%20Agent/adk-workspace/bookcompass-ai/app/agent.py#L182-L194).
- **LlmAgent**: Used for specialized sub-agents `recommender_agent` and `roadmap_agent` defined in [app/agent.py](file:///c:/AI%20Agent/adk-workspace/bookcompass-ai/app/agent.py#L42-L68).
- **AgentTool**: Used by `orchestrator_agent` to delegate tasks to sub-agents [app/agent.py](file:///c:/AI%20Agent/adk-workspace/bookcompass-ai/app/agent.py#L88).
- **MCP Server**: Stdio connection configured in [app/agent.py](file:///c:/AI%20Agent/adk-workspace/bookcompass-ai/app/agent.py#L31-L40) and implemented in [app/mcp_server.py](file:///c:/AI%20Agent/adk-workspace/bookcompass-ai/app/mcp_server.py).
- **Security Checkpoint**: The `security_checkpoint` node filters and logs queries in [app/agent.py](file:///c:/AI%20Agent/adk-workspace/bookcompass-ai/app/agent.py#L94-L141).
- **Agents CLI**: Project scaffolded, structured, and run using standard `agents-cli` targets.

## 4. Security Design
- **PII Scrubbing**: Cleans email addresses and phone numbers using regex before LLM execution, preventing leakage.
- **Prompt Injection Filter**: Matches adversarial commands (e.g. `"ignore previous instructions"`) and redirects immediately to a safe terminal block.
- **Structured Audit Logging**: Outputs audit logs as JSON to stdout for log collection and monitoring.
- **Domain Restriction**: Blocks common system commands or SQL injections (e.g. `rm -rf`, `drop table`).

## 5. MCP Server Design
The local Model Context Protocol (MCP) server runs inside the project environment and exposes:
1. `search_books_by_topic`: Curates specific book recommendations from a local database of classic tech and business literature.
2. `get_book_details_by_title`: Resolves reading durations, difficulty, and book outlines to ensure the LLM has accurate, grounded data.
3. `calculate_reading_pace`: Dynamically calculates daily study target minutes and overall duration based on weekly hours.

## 6. Human-in-the-Loop (HITL) Flow
BookCompass uses the ADK 2.0 `RequestInput` mechanism. After the initial book recommendations and roadmap are formulated:
1. The execution halts and yields a review prompt showing the proposal.
2. The user reviews the books and replies.
3. If they say "yes", we proceed to generate the structured final outputs.
4. If they suggest changes, the workflow loops back to the orchestrator, passing the feedback to re-run tool calls and refine the roadmap.

## 7. Demo Walkthrough
- **Test Case 1 (Happy Path)**: Entering "I want to learn Java" triggers the database tools, fetches *Head First Java*, and prompts the user for review.
- **Test Case 2 (Modification)**: Replying "Exclude Head First" modifies the state, and the second iteration recommends *Effective Java* and *Spring Start Here*.
- **Test Case 3 (Injection Block)**: Inputting a jailbreak command triggers the `unsafe` edge and halts output with a security notification.

## 8. Impact / Value Statement
BookCompass AI eliminates decision fatigue for readers, structuring random reading lists into progressive curricula. Students and professionals can save hours of planning, ensuring they build skills in the correct order with realistic timelines.
