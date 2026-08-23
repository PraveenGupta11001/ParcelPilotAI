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
from app.tools.document_info import get_document_count, list_all_documents

class RateLimitExceededException(Exception):
    pass

def _is_rate_or_token_limit_error(e: Exception) -> bool:
    import openai
    if isinstance(e, openai.RateLimitError):
        return True
    if hasattr(e, "status_code") and e.status_code == 429:
        return True
    
    err_str = str(e).lower()
    for keyword in ["rate limit", "rate_limit", "429", "token limit", "token_limit", "quota", "too many requests", "resource exhausted"]:
        if keyword in err_str:
            return True
    return False

class AgentService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.trace = []  # List of dicts compiling tool execution outputs: {tool_name, args, output}
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if self.anthropic_key and self.anthropic_key.startswith("your-"):
            self.anthropic_key = None
        self.openai_key = os.getenv("OPENAI_API_KEY")
        if self.openai_key and self.openai_key.startswith("your-"):
            self.openai_key = None
        self.groq_key = os.getenv("GROQ_API_KEY")
        if self.groq_key and self.groq_key.startswith("your-"):
            self.groq_key = None
        self.groq_key_backup = os.getenv("GROQ_API_KEY_BACKUP")
        if self.groq_key_backup and self.groq_key_backup.startswith("your-"):
            self.groq_key_backup = None
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        if self.gemini_key and self.gemini_key.startswith("your-"):
            self.gemini_key = None


    def run_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Executes a database tool securely inside the verified user workspace.
        Appends tool events to agent execution traces and persists inside AuditLogs.
        """
        # Coerce include_deprecated from potential string to boolean
        if isinstance(arguments, dict) and "include_deprecated" in arguments:
            val = arguments["include_deprecated"]
            if isinstance(val, str):
                arguments["include_deprecated"] = (val.lower() == "true")

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
            elif tool_name == "get_document_count":
                include_deprecated = arguments.get("include_deprecated", False)
                # Force FALSE for customer role
                if self.user.role == "customer":
                    include_deprecated = False
                res = get_document_count(
                    db=self.db,
                    user=self.user,
                    include_deprecated=include_deprecated
                )
                output = json.dumps(res, default=str)
            elif tool_name == "list_all_documents":
                include_deprecated = arguments.get("include_deprecated", False)
                # Force FALSE for customer role
                if self.user.role == "customer":
                    include_deprecated = False
                res = list_all_documents(
                    db=self.db,
                    user=self.user,
                    include_deprecated=include_deprecated
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
        """Executes the main tool-calling orchestrator loop.

        Prioritizes Groq (with keys fallback) if available, then Anthropic Claude, then OpenAI, else simulated fallback.

        Args:
            chat_history: Historical list of preceding conversational messages.
            message: The natural language statement from the user.

        Returns:
            dict: The final response containing text_response and tool_calls trace.
        """
        options = []
        if self.groq_key:
            options.append({
                "api_key": self.groq_key,
                "base_url": "https://api.groq.com/openai/v1",
                "model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
                "name": "Groq Primary"
            })
        if self.groq_key_backup:
            options.append({
                "api_key": self.groq_key_backup,
                "base_url": "https://api.groq.com/openai/v1",
                "model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
                "name": "Groq Backup"
            })
        if self.gemini_key:
            options.append({
                "api_key": self.gemini_key,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": "gemini-2.5-flash",
                "name": "Gemini Backup"
            })

        if not options:
            if self.anthropic_key:
                return self._run_anthropic_loop(chat_history, message)
            elif self.openai_key:
                return self._run_openai_translation_loop(chat_history, message)
            else:
                return self._run_mock_fallback_loop(message)

        last_err = None
        rate_limit_occurred = False
        for option in options:
            try:
                return self._run_openai_like_loop(
                    chat_history=chat_history,
                    message=message,
                    api_key=option["api_key"],
                    base_url=option["base_url"],
                    model=option["model"]
                )
            except Exception as e:
                last_err = e
                if _is_rate_or_token_limit_error(e):
                    rate_limit_occurred = True
                
                print(f"Fallback warning: {option['name']} failed with error: {e}. Trying next option if available.")
                continue

        if rate_limit_occurred:
            raise RateLimitExceededException(
                "⚠️ **Rate Limit / Token Limit Exceeded**\n\n"
                "The chat session has exceeded the available model capacity or the message history has grown too large.\n\n"
                "Please initialize a **new chat session** to continue, or try again in **5 minutes**."
            )
        else:
            raise last_err if last_err else Exception("No API keys succeeded.")

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
                max_tokens=4096
            )
            
            choice = response.choices[0]
            assistant_msg = choice.message
            
            # Convert message to add to list
            to_append = {"role": "assistant", "content": assistant_msg.content}
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

    def _run_openai_like_loop(self, chat_history: list[dict], message: str, api_key: str, base_url: str, model: str) -> dict:
        """Executes tool-calling orchestration using completions via any OpenAI compatible SDK API configuration."""
        import openai
        client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        
        # Format tools compatible with OpenAI tool calling schema
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
                model=model,
                messages=messages,
                tools=openai_tools,
                max_tokens=4096
            )
            
            choice = response.choices[0]
            assistant_msg = choice.message
            
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
                
            for tc in assistant_msg.tool_calls:
                args = json.loads(tc.function.arguments)
                tool_output = self.run_tool(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": tool_output
                })
                
        return {"text_response": "Limit exceeded call loops.", "tool_calls": self.trace}

    def run_agent_stream(self, chat_history: list[dict], message: str):
        options = []
        if self.groq_key:
            options.append({
                "api_key": self.groq_key,
                "base_url": "https://api.groq.com/openai/v1",
                "model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
                "name": "Groq Primary"
            })
        if self.groq_key_backup:
            options.append({
                "api_key": self.groq_key_backup,
                "base_url": "https://api.groq.com/openai/v1",
                "model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
                "name": "Groq Backup"
            })
        if self.gemini_key:
            options.append({
                "api_key": self.gemini_key,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": "gemini-2.5-flash",
                "name": "Gemini Backup"
            })

        if not options:
            if self.anthropic_key:
                yield from self._run_anthropic_loop_stream(chat_history, message)
            elif self.openai_key:
                yield from self._run_openai_translation_loop_stream(chat_history, message)
            else:
                yield from self._run_mock_fallback_loop_stream(message)
            return

        last_err = None
        rate_limit_occurred = False
        for option in options:
            try:
                yield from self._run_openai_like_loop_stream(
                    chat_history=chat_history,
                    message=message,
                    api_key=option["api_key"],
                    base_url=option["base_url"],
                    model=option["model"],
                    provider_name=option["name"]
                )
                return
            except Exception as e:
                last_err = e
                if _is_rate_or_token_limit_error(e):
                    rate_limit_occurred = True
                
                print(f"Fallback warning stream: {option['name']} failed with error: {e}. Trying next option if available.")
                continue

        if rate_limit_occurred:
            raise RateLimitExceededException(
                "⚠️ **Rate Limit / Token Limit Exceeded**\n\n"
                "The chat session has exceeded the available model capacity or the message history has grown too large.\n\n"
                "Please initialize a **new chat session** to continue, or try again in **5 minutes**."
            )
        else:
            raise last_err if last_err else Exception("No API keys succeeded.")

    def _run_openai_like_loop_stream(self, chat_history: list[dict], message: str, api_key: str, base_url: str, model: str, provider_name: str):
        import openai
        client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        
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
            
            yield {"event": "status", "message": "Analyzing queries..."}
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools,
                max_tokens=4096
            )
            
            choice = response.choices[0]
            assistant_msg = choice.message
            
            to_append = {"role": "assistant", "content": assistant_msg.content}
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
                yield {"event": "text", "text": assistant_msg.content or ""}
                yield {"event": "done", "text_response": assistant_msg.content or "", "tool_calls": self.trace}
                return
                
            for tc in assistant_msg.tool_calls:
                args = json.loads(tc.function.arguments)
                yield {"event": "tool_call", "name": tc.function.name, "args": args}
                
                tool_output = self.run_tool(tc.function.name, args)
                
                yield {"event": "tool_result", "name": tc.function.name, "output": tool_output}
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": tool_output
                })

    def _run_anthropic_loop_stream(self, chat_history: list[dict], message: str):
        client = Anthropic(api_key=self.anthropic_key)
        system_prompt = self.get_system_prompt()
        
        messages = []
        for h in chat_history:
            role = "assistant" if h.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": h.get("content")})
            
        messages.append({"role": "user", "content": message})
        
        loop_limit = 5
        while loop_limit > 0:
            loop_limit -= 1
            
            yield {"event": "status", "message": "Claude is evaluating policies and agreement documents..."}
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=system_prompt,
                messages=messages,
                tools=TOOLS_DEFINITION
            )
            
            text_ans = ""
            tool_calls_req = []
            
            for content in response.content:
                if content.type == "text":
                    text_ans += content.text
                elif content.type == "tool_use":
                    tool_calls_req.append(content)
            
            if not tool_calls_req:
                yield {"event": "text", "text": text_ans}
                yield {"event": "done", "text_response": text_ans, "tool_calls": self.trace}
                return
            
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
            
            tool_results_content = []
            for tool_use in tool_calls_req:
                yield {"event": "tool_call", "name": tool_use.name, "args": tool_use.input}
                
                tool_output = self.run_tool(tool_use.name, tool_use.input)
                
                yield {"event": "tool_result", "name": tool_use.name, "output": tool_output}
                
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_output
                })
                
            messages.append({"role": "user", "content": tool_results_content})
            
        yield {"event": "text", "text": "Limit exceeded call loops."}
        yield {"event": "done", "text_response": "Limit exceeded call loops.", "tool_calls": self.trace}

    def _run_openai_translation_loop_stream(self, chat_history: list[dict], message: str):
        import openai
        client = openai.OpenAI(api_key=self.openai_key)
        
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
            
            yield {"event": "status", "message": "Searching system parameters and running validations..."}
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=openai_tools,
                max_tokens=4096
            )
            
            choice = response.choices[0]
            assistant_msg = choice.message
            
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
                yield {"event": "text", "text": assistant_msg.content or ""}
                yield {"event": "done", "text_response": assistant_msg.content or "", "tool_calls": self.trace}
                return
                
            for tc in assistant_msg.tool_calls:
                args = json.loads(tc.function.arguments)
                yield {"event": "tool_call", "name": tc.function.name, "args": args}
                
                tool_output = self.run_tool(tc.function.name, args)
                
                yield {"event": "tool_result", "name": tc.function.name, "output": tool_output}
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": tool_output
                })
                
        yield {"event": "text", "text": "Limit exceeded."}
        yield {"event": "done", "text_response": "Limit exceeded.", "tool_calls": self.trace}

    def _run_mock_fallback_loop_stream(self, message: str):
        msg_lower = message.lower()
        ans = "I am operating in offline simulated mode."
        
        yield {"event": "status", "message": "Offline dispatcher analyzing request..."}
        
        if "cancellation" in msg_lower or "cancel" in msg_lower:
            ans += " To cancel a shipment, please provide the shipment/order ID. If it is booked longer than 30 minutes, standard fees apply."
            yield {"event": "status", "message": "Checking shipment cancellation constraints..."}
        elif "credit" in msg_lower or "refund" in msg_lower:
            ans += " Service credit eligibility requires a carrier fault delay exceeding policy thresholds."
            yield {"event": "status", "message": "Evaluating service credit policies..."}
        elif "search" in msg_lower or "policy" in msg_lower:
            yield {"event": "tool_call", "name": "search_documents", "args": {"query": message}}
            tool_output = self.run_tool("search_documents", {"query": message})
            yield {"event": "tool_result", "name": "search_documents", "output": tool_output}
            ans += f" Searched policies matching keyword filters."
            
        yield {"event": "text", "text": ans}
        yield {"event": "done", "text_response": ans, "tool_calls": self.trace}
