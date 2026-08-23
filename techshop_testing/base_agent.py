"""
base_agent.py is  shared agent logic


Why do we need the base class:
Our pseudocode defines agent_phase1, agent_phase2, and so on as a separate
things. But all of our phases  share the same basic behavior:
  1) Receive instructions
  2) Call the LLM with those instructions plus context -> (requirements_path)
  3) Uses the tools it needs
  4) Return a result
 
Instead of copy pasting that logic 4 times, we put it here once.
Each phase agent then only defines what is different about it:
  * Its specific instructions
  * Which tools it is allowed to use
  * What it does with the LLM response
 
How our agent calls the tools:
  * We give the agent an access to the functions -> tools (we tell the agent that it can call these functions)
  * The agent decides it needs information or actions and
    returns:{ "tool": "read_file", "args": {"file_path": "req.md"} }
  * Our Python code executes the tool
  * The tool result is sent back to the agent
  * The agent continues with the new information
 
This repeats until the agent finds out it has enough information and 
produces a final answer.

This cycle is called the agentic loop because the agent controls
the process by deciding which tools to use and when.

"""
import json
import inspect
from openai import OpenAI
from Tools import TOOL_REGISTRY

class BaseAgent:
    """
    Base class for all our pipeline agents.
 
    All our agents share:
        * An OpenAI client pointed at Azure
        * A model name
        * A list of allowed tools
        * The run_with_tools() method that controls the agentic loop
 
    Each subclass defines:
        * self.instructions -> (the system prompt for that particular phase)
        * self.tools -> (subset of TOOL_REGISTRY this agent can use)
        * run(...) -> (the public method with phase specific arguments) -> our entry point called by coordinator
    """
 
    def __init__(self, client: OpenAI, deployment: str):
        """
        Args:
            client:The OpenAI client already configured with Azure endpoint and key
            deployment
 
        We receive the client instead of creating it here so that all our
        agents share one client, same as our pseudocode passing the
        client through the coordinator.
        """
        self.client     = client
        self.deployment = deployment
        self.instructions: str  = ""    
        self.tools: list        = []   

#Core method that is used by all our agents
    def call_ai(self, user_message: str, expect_json: bool = False) -> str:
        """
        Sends a message to the  and returns the response text.
 
        This is just the simple version, no tool calls, just a direct question.
        Used when we have all the context already and just need the AI
        to analyse and write a response for example like writing the reports.
 
        Args:
            user_message:  The full prompt to send
            expect_json:   If True, instructs the AI to return only JSON
        """
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user",   "content": user_message},
        ]
 
        if expect_json:
            messages[0]["content"] += (
                "\n\nIMPORTANT: Respond ONLY with valid JSON. "
                "No markdown, no explanation, no code fences. Just JSON."
            )
 
        response = self.client.chat.completions.create(
            model=self.deployment,
            max_tokens=4000,
            messages=messages,
        )
 
        raw = response.choices[0].message.content.strip()
 
        if expect_json and raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
 
        return raw

#Our agentic loop
    def run_with_tools(self, user_message: str) -> str:
        """
        The agentic loop that sends a message and lets the agent call tools
        until it has enough information to give a final answer. If our agent does not have enough
        information it doesn't give us final answer also a proper answer.
 
        How the agentic loop works:
            1) Send user_message->(prompt) to the agent along with tool descriptions
            2) agent responds with either:
               a) A final text answer -> we return it
               b) A tool_call -> we execute the tool and send result back to agent
            3) Repeat from step 2 until our agent gives a final answer
 
        This is the core of agentic behaviour,  the agent decides what
        information it needs, asks for it via tool calls, and keeps
        going until it can answer. It gets enough informations only via tools.
        If our agent has the right tools it needs for performing its tasks
        then it gives us the final answer.
 
        The agent never directly reads files or runs git, it asks us to
        do it via tool calls. Once the python executes the tools we send the results back to agent
        abd agent continue its job.
        """
 
        # Building the tool descriptions to give our agent
        # Format: list of { "type": "function", "function": { name, description, parameters } }
        tool_definitions = self._build_tool_definitions()
 
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user",   "content": user_message},
        ]
 
        # Our loop: keep going until our agent stops calling tools
        for _ in range(10): 
            response = self.client.chat.completions.create(
                model=self.deployment,
                max_completion_tokens=4000,
                messages=messages,
                tools=tool_definitions,
                tool_choice="auto",  # our agent decides when to call tool
            )
 
            choice  = response.choices[0]
            message = choice.message
 
            # Adds the agent's response to the conversation history
            messages.append({"role": "assistant", "content": message.content,
                              "tool_calls": message.tool_calls})
 
            # If there is no tool calls -> agent has finished. Return its answer.
            if not message.tool_calls:
                return message.content or ""
 
            # If there are tool calls -> execute each one and send results back to our agent
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
 
                print(f"[tool call] {tool_name}({tool_args})")
 
                # looking up and executing the tool
                if tool_name not in TOOL_REGISTRY:
                    tool_result = f"Error: tool '{tool_name}' not found"
                else:
                    try:
                        tool_func   = TOOL_REGISTRY[tool_name]
                        tool_result = tool_func(**tool_args)

                        # Converting non string results to JSON string
                        if not isinstance(tool_result, str):
                            tool_result = json.dumps(tool_result, indent=2)
                    except Exception as e:
                        tool_result = f"Tool error: {e}"
 
                print(f"    [tool result] {str(tool_result)[:80]}...")
 
                # Sending tool result back to the agent
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "content":      str(tool_result),
                })
 
        return "Agent exceeded maximum tool call rounds without finishing."

#Our list of functions name -> in other words tools name
    def _build_tool_definitions(self) -> list:
        """
        Converts our list of tool names into the format agent expects.
 
        agent needs tools described as:
            {
              "type": "function",
              "function": {
                "name": "read_file",
                "description": "Reads a file...",
                "parameters": {
                  "type": "object",
                  "properties": { "file_path": {"type": "string"} },
                  "required": ["file_path"]
                }
              }
            }
 
        We build this from the function's docstring and type hints.
        """
        definitions = []
 
        for tool_name in self.tools:
            if tool_name not in TOOL_REGISTRY:
                continue
 
            func = TOOL_REGISTRY[tool_name]
            sig  = inspect.signature(func)
            doc  = (func.__doc__ or "").strip().split("\n")[0]  # first line only
 
            # Build parameters from type hints
            properties = {}
            required   = []
 
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
 
                properties[param_name] = {
                    "type": "string",   
                    "description": param_name.replace("_", " "),
                }
 
                # If no default value -> required
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)
 
            definitions.append({
                "type": "function",
                "function": {
                    "name":        tool_name,
                    "description": doc,
                    "parameters":  {
                        "type":       "object",
                        "properties": properties,
                        "required":   required,
                    },
                },
            })
 
        return definitions
 
 