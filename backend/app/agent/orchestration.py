import os
import json
from sqlalchemy.orm import Session
from anthropic import Anthropic

from app.db.models import User, AuditLog
from app.tools.registry import TOOLS_DEFINITION
from app.tools.document_search import search_documents
from app.tools.structured_data import query_structured_data
from app.tools.actions import propose_action
from app.tools.proactive_signals import get_operational_signals

class AgentService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.trace = []  # List of dicts compiling tool execution outputs: {tool_name, args, output}
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

    def run_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Executes a database tool securely inside the verified user workspace.
        Appends tool events to agent execution traces and persists inside AuditLogs.
        """
        output = ""
        try:
            if tool_name == "search_documents":
                include_deprecated = arguments.get("include_deprecated", False)
                # Force FALSE for customer role
                if self.user.role == "customer":
                    include_deprecated = False
                hits = search_documents(
                    db=self.db,
                    user=self.user,
                    query=arguments.get("query"),
                    include_deprecated=include_deprecated
                )
                output = json.dumps(hits, default=str)
            elif tool_name == "query_structured_data":
                res = query_structured_data(
                    db=self.db,
                    user=self.user,
                    entity=arguments.get("entity"),
                    filters=arguments.get("filters", {}),
                    run_calculation=arguments.get("run_calculation")
                )
                output = json.dumps(res, default=str)
            elif tool_name == "propose_action":
                res = propose_action(
                    db=self.db,
                    user=self.user,
                    action_type=arguments.get("action_type"),
                    reason=arguments.get("reason"),
                    order_id=arguments.get("order_id"),
                    ticket_id=arguments.get("ticket_id"),
                    amount=arguments.get("amount")
                )
                output = json.dumps(res, default=str)
            elif tool_name == "get_operational_signals":
                res = get_operational_signals(
                    db=self.db,
                    user=self.user
                )
                output = json.dumps(res, default=str)
            else:
                output = json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            output = json.dumps({"error": str(e)})

        # Record in trace
        self.trace.append({
            "tool_name": tool_name,
            "args": arguments,
            "output": output
        })

        # Save to Audit Log
        log = AuditLog(
            account_id=self.user.account_id,
            user_id=self.user.user_id,
            tool_name=tool_name,
            input=json.dumps(arguments),
            output=output
        )
        self.db.add(log)
        self.db.commit()
        return output

    def get_system_prompt(self) -> str:
        role_desc = {
            "customer": f"You are the customer support chatbot talking directly to a customer of account {self.user.account_id}.",
            "internal_support": "You are the internal operations support agent with full account query metrics view.",
            "internal_lead": "You are the internal team lead agent with administrative oversight."
        }
        
        prompt = (
            "You are the ParcelPilot AI Assistant, a production-grade support bot. "
            f"{role_desc.get(self.user.role, 'You are a support bot.')}\n"
            "Enforce the authority hierarchy rules when reading policies from 'search_documents':\n"
            "Level 1: Signed Customer Agreements (eg: Northstar Agreement, LumenWorks Agreement) - Highest authority.\n"
            "Level 2: Current SOPs (eg: Cancellation SOP v4, Support Policy v3) - Overridden by customer agreements.\n"
            "Level 3: Product Operations Guide - Operational guidelines.\n"
            "Level 4: Deprecated Policies (eg: Support Policy v2) - Never use to resolve current claims.\n"
            "Level 5: Historical Resolution records - Informational only.\n\n"
            "Operational snapshot time for any date calculation is strictly: 2026-08-16 11:00:00+05:30. "
            "You MUST compute time relative to this baseline.\n"
            "When performing cancellations or proposing service credits, you MUST first run calculations via 'query_structured_data' "
            "before calling 'propose_action'. If parameters are missing (carrier fault, etc.), notify the user.\n"
            "If an action requires manager approval (credit amount > 1000 INR), warn the user of this rule.\n"
            "Answer concisely and frame decisions professionally."
        )
        return prompt

    def run_agent_loop(self, chat_history: list[dict], message: str) -> dict:
        """
        Executes the main tool-calling orchestrator loop.
        Prioritizes Anthropic Claude Messages, falls back to OpenAI Translation if Anthropic keys are absent.
        """
        if self.anthropic_key:
            return self._run_anthropic_loop(chat_history, message)
        elif self.openai_key:
            return self._run_openai_translation_loop(chat_history, message)
        else:
            return self._run_mock_fallback_loop(message)

    def _run_anthropic_loop(self, chat_history: list[dict], message: str) -> dict:
        client = Anthropic(api_key=self.anthropic_key)
        system_prompt = self.get_system_prompt()
        
        # Translate history format to Anthropic Messages style
        messages = []
        for h in chat_history:
            role = "assistant" if h.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": h.get("content")})
            
        messages.append({"role": "user", "content": message})
        
        loop_limit = 5
        while loop_limit > 0:
            loop_limit -= 1
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=system_prompt,
                messages=messages,
                tools=TOOLS_DEFINITION
            )
            
            # Analyze response contents
            text_ans = ""
            tool_calls_req = []
            
            for content in response.content:
                if content.type == "text":
                    text_ans += content.text
                elif content.type == "tool_use":
                    tool_calls_req.append(content)
            
            if not tool_calls_req:
                # No more tools requested, loop finished
                return {"text_response": text_ans, "tool_calls": self.trace}
            
            # Build assistant message block including text and tool usage
            assistant_content = []
            if text_ans:
                assistant_content.append({"type": "text", "text": text_ans})
            
            for tool_use in tool_calls_req:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tool_use.id,
                    "name": tool_use.name,
                    "input": tool_use.input
                })
            
            messages.append({"role": "assistant", "content": assistant_content})
            
            # Execute tools and build user follow-up tool outputs block
            tool_results_content = []
            for tool_use in tool_calls_req:
                tool_output = self.run_tool(tool_use.name, tool_use.input)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_output
                })
                
            messages.append({"role": "user", "content": tool_results_content})
            
        return {"text_response": "Limit exceeded call loops.", "tool_calls": self.trace}

    def _run_openai_translation_loop(self, chat_history: list[dict], message: str) -> dict:
        import openai
        client = openai.OpenAI(api_key=self.openai_key)
        
        # Translate Anthropic tool schema declarations to OpenAI function calling
        openai_tools = []
        for t in TOOLS_DEFINITION:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"]
                }
            })
            
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        
        for h in chat_history:
            role = "assistant" if h.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": h.get("content")})
            
        messages.append({"role": "user", "content": message})
        
        loop_limit = 5
        while loop_limit > 0:
            loop_limit -= 1
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=openai_tools,
                max_tokens=800
            )
            
            choice = response.choices[0]
            assistant_msg = choice.message
            
            # Convert message to add to list
            to_append = {"role": "assistant", "content": assistant_msg.content or ""}
            if assistant_msg.tool_calls:
                to_append["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in assistant_msg.tool_calls
                ]
            messages.append(to_append)
            
            if not assistant_msg.tool_calls:
                return {"text_response": assistant_msg.content or "", "tool_calls": self.trace}
                
            # Execute tool queries and push response messages
            for tc in assistant_msg.tool_calls:
                args = json.loads(tc.function.arguments)
                tool_output = self.run_tool(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": tool_output
                })
                
        return {"text_response": "Limit exceeded.", "tool_calls": self.trace}

    def _run_mock_fallback_loop(self, message: str) -> dict:
        """
        Pure deterministic fallback if no API keys are present (for offline test harnesses).
        """
        msg_lower = message.lower()
        ans = "I am operating in offline simulated mode."
        
        if "cancellation" in msg_lower or "cancel" in msg_lower:
            ans += " To cancel a shipment, please provide the shipment/order ID. If it is booked longer than 30 minutes, standard fees apply."
        elif "credit" in msg_lower or "refund" in msg_lower:
            ans += " Service credit eligibility requires a carrier fault delay exceeding policy thresholds."
        elif "search" in msg_lower or "policy" in msg_lower:
            # Mock document search
            self.run_tool("search_documents", {"query": message})
            ans += f" Searched policies matching keyword filters."
            
        return {"text_response": ans, "tool_calls": self.trace}
