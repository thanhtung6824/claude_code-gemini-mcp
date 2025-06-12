#!/usr/bin/env python3
"""
Claude-OpenRouter MCP Server
Enables Claude Code to collaborate with multiple AI providers through OpenRouter
"""

import json
import sys
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import uuid
from typing import Dict, Any, Optional, List

# Ensure unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)

# Server version
__version__ = "2.1.0"

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")

# Session ID for tracking requests
SESSION_ID = str(uuid.uuid4())

# OpenRouter configuration
OPENROUTER_API_KEY = ""
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Available models with their providers
AVAILABLE_MODELS = {
    "gemini-pro": "google/gemini-2.5-pro-preview"
}

# Default model
DEFAULT_MODEL = "gemini-pro"

# Track token usage (kept for legacy compatibility, but will be retrieved from DB)
token_usage = {
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_cost": 0.0,
    "requests": []
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}", file=sys.stderr)
        return None

def init_database():
    """Initialize database connection and ensure tables exist"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Test connection
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Database initialization error: {e}", file=sys.stderr)
            return False
    return False

def save_usage_to_db(model: str, prompt_tokens: int, completion_tokens: int, 
                     total_tokens: int, cost: float, request_type: str = "ask_ai"):
    """Save usage data to database"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Use the cost directly from API response
        # For gemini-pro, calculate prompt and completion costs based on pricing
        # Input: $1.25 per 1M tokens (≤200K), $2.50 per 1M tokens (>200K)
        # Output: $10 per 1M tokens (≤200K), $15 per 1M tokens (>200K)
        
        # Calculate input cost based on token count
        if prompt_tokens <= 200000:
            prompt_cost = (prompt_tokens / 1000000.0) * 1.25
        else:
            # First 200K at $1.25, rest at $2.50
            prompt_cost = (200000 / 1000000.0) * 1.25 + ((prompt_tokens - 200000) / 1000000.0) * 2.50
        
        # Calculate output cost based on token count
        if completion_tokens <= 200000:
            completion_cost = (completion_tokens / 1000000.0) * 10.0
        else:
            # First 200K at $10, rest at $15
            completion_cost = (200000 / 1000000.0) * 10.0 + ((completion_tokens - 200000) / 1000000.0) * 15.0
        
        # Use the API-provided cost if available, otherwise use calculated cost
        total_cost = cost if cost > 0 else (prompt_cost + completion_cost)
        
        # Insert usage record
        cur.execute("""
            INSERT INTO usage_records 
            (model, prompt_tokens, completion_tokens, total_tokens, 
             prompt_cost, completion_cost, total_cost, request_type, session_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (model, prompt_tokens, completion_tokens, total_tokens,
               prompt_cost, completion_cost, total_cost, request_type, SESSION_ID))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving usage to database: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
            conn.close()

def get_usage_from_db(detailed: bool = False, period: str = "all", 
                      start_date: Optional[datetime] = None, 
                      end_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Get usage statistics from database"""
    conn = get_db_connection()
    if not conn:
        return {
            "error": "Database connection failed",
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "requests": []
        }
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query based on period
        query_conditions = []
        query_params = []
        
        if period == "today":
            query_conditions.append("DATE(created_at) = CURRENT_DATE")
        elif period == "month":
            query_conditions.append("DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)")
        elif period == "session":
            query_conditions.append("session_id = %s")
            query_params.append(SESSION_ID)
        elif period == "custom" and start_date and end_date:
            query_conditions.append("created_at BETWEEN %s AND %s")
            query_params.extend([start_date, end_date])
        
        where_clause = "WHERE " + " AND ".join(query_conditions) if query_conditions else ""
        
        # Get aggregate statistics
        cur.execute(f"""
            SELECT 
                COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COUNT(*) as total_requests
            FROM usage_records
            {where_clause}
        """, query_params)
        
        stats = cur.fetchone()
        
        result = {
            "total_prompt_tokens": int(stats["total_prompt_tokens"]),
            "total_completion_tokens": int(stats["total_completion_tokens"]),
            "total_tokens": int(stats["total_tokens"]),
            "total_cost": float(stats["total_cost"]),
            "total_requests": int(stats["total_requests"]),
            "requests": []
        }
        
        if detailed:
            # Get recent requests
            cur.execute(f"""
                SELECT 
                    model, prompt_tokens, completion_tokens, total_tokens,
                    total_cost as cost, created_at, request_type
                FROM usage_records
                {where_clause}
                ORDER BY created_at DESC
                LIMIT 20
            """, query_params)
            
            result["requests"] = cur.fetchall()
        
        cur.close()
        conn.close()
        return result
        
    except Exception as e:
        print(f"Error getting usage from database: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return {
            "error": str(e),
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "requests": []
        }

def send_response(response: Dict[str, Any]):
    """Send a JSON-RPC response"""
    print(json.dumps(response), flush=True)

def handle_initialize(request_id: Any) -> Dict[str, Any]:
    """Handle initialization"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "claude-openrouter-mcp",
                "version": __version__
            }
        }
    }

def handle_tools_list(request_id: Any) -> Dict[str, Any]:
    """List available tools"""
    tools = []
    
    if OPENROUTER_API_KEY:
        tools = [
            {
                "name": "ask_ai",
                "description": "Ask any AI model through OpenRouter and get the response with token usage",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The question or prompt for the AI"
                        },
                        "model": {
                            "type": "string",
                            "description": f"Model to use. Available: {', '.join(AVAILABLE_MODELS.keys())}",
                            "default": DEFAULT_MODEL
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Temperature for response (0.0-1.0)",
                            "default": 0.5
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Maximum tokens in response",
                            "default": 4096
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "ai_code_review",
                "description": "Have any AI model review code through OpenRouter",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to review"
                        },
                        "model": {
                            "type": "string",
                            "description": f"Model to use. Available: {', '.join(AVAILABLE_MODELS.keys())}",
                            "default": DEFAULT_MODEL
                        },
                        "focus": {
                            "type": "string",
                            "description": "Specific focus area (security, performance, etc.)",
                            "default": "general"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "ai_brainstorm",
                "description": "Brainstorm solutions with any AI model through OpenRouter",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic to brainstorm about"
                        },
                        "model": {
                            "type": "string",
                            "description": f"Model to use. Available: {', '.join(AVAILABLE_MODELS.keys())}",
                            "default": DEFAULT_MODEL
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context",
                            "default": ""
                        }
                    },
                    "required": ["topic"]
                }
            },
            {
                "name": "list_models",
                "description": "List all available AI models through OpenRouter",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_token_usage",
                "description": "Get current token usage and cost statistics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "detailed": {
                            "type": "boolean",
                            "description": "Show detailed request history",
                            "default": False
                        },
                        "period": {
                            "type": "string",
                            "description": "Time period: all, today, month, session",
                            "default": "all"
                        }
                    }
                }
            },
            {
                "name": "get_cache_stats",
                "description": "Get cache statistics including hit rate and savings",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    else:
        tools = [
            {
                "name": "server_info",
                "description": "Get server status and configuration info",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": tools
        }
    }

def call_openrouter(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.5, max_tokens: int = 4096) -> Dict[str, Any]:
    """Call OpenRouter API and return response with usage info"""
    try:
        # Get the full model name
        model_id = AVAILABLE_MODELS.get(model, model)
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usage": {
                "include": True
            }
        }
        
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        
        # Extract response and usage
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "No response")
        usage = result.get("usage", {})
        
        # Update token tracking
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        
        # Use the cost from API response directly
        estimated_cost = usage.get("cost", 0) if isinstance(usage, dict) and "cost" in usage else 0
        
        # Save to database
        save_usage_to_db(model, prompt_tokens, completion_tokens, total_tokens, estimated_cost)
        
        # Still update in-memory tracking for backward compatibility
        token_usage["total_prompt_tokens"] += prompt_tokens
        token_usage["total_completion_tokens"] += completion_tokens
        token_usage["total_cost"] += estimated_cost
        token_usage["requests"].append({
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": estimated_cost
        })
        
        # Get provider from response
        provider = result.get("provider", "Unknown")
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": f"${estimated_cost:.6f}"
            },
            "model": model,
            "provider": provider,
            "model_id": result.get("model", model_id)
        }
        
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
        except:
            error_detail = e.response.text
        return {
            "content": f"OpenRouter API Error: {str(e)}\nDetails: {error_detail}",
            "usage": None,
            "model": model
        }
    except requests.exceptions.RequestException as e:
        return {
            "content": f"Error calling OpenRouter: {str(e)}",
            "usage": None,
            "model": model
        }
    except Exception as e:
        return {
            "content": f"Unexpected error: {type(e).__name__}: {str(e)}",
            "usage": None,
            "model": model
        }

def handle_tool_call(request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tool execution"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    try:
        result = ""
        
        if tool_name == "server_info":
            if OPENROUTER_API_KEY:
                result = f"Server v{__version__} - OpenRouter connected and ready!\nAvailable models: {', '.join(AVAILABLE_MODELS.keys())}"
            else:
                result = f"Server v{__version__} - Please set your OpenRouter API key"
        
        elif tool_name == "ask_ai":
            prompt = arguments.get("prompt", "")
            model = arguments.get("model", DEFAULT_MODEL)
            temperature = arguments.get("temperature", 0.5)
            max_tokens = arguments.get("max_tokens", 4096)
            
            response = call_openrouter(prompt, model, temperature, max_tokens)
            
            usage_info = ""
            if response["usage"]:
                usage_info = f"\n\n📊 Token Usage:\n"
                usage_info += f"- Prompt tokens: {response['usage']['prompt_tokens']}\n"
                usage_info += f"- Completion tokens: {response['usage']['completion_tokens']}\n"
                usage_info += f"- Total tokens: {response['usage']['total_tokens']}\n"
                usage_info += f"- Estimated cost: {response['usage']['estimated_cost']}"
            
            provider_info = f" ({response['provider']})" if response.get('provider') else ""
            result = f"🤖 {response['model'].upper()}{provider_info} RESPONSE:\n\n{response['content']}{usage_info}"
            
        elif tool_name == "ai_code_review":
            code = arguments.get("code", "")
            model = arguments.get("model", DEFAULT_MODEL)
            focus = arguments.get("focus", "general")
            
            prompt = f"""Please review this code with a focus on {focus}:

```
{code}
```

Provide specific, actionable feedback on:
1. Potential issues or bugs
2. Security concerns
3. Performance optimizations
4. Best practices
5. Code clarity and maintainability"""
            
            response = call_openrouter(prompt, model, 0.2, 8192)
            
            usage_info = ""
            if response["usage"]:
                usage_info = f"\n\n📊 Token Usage:\n"
                usage_info += f"- Prompt tokens: {response['usage']['prompt_tokens']}\n"
                usage_info += f"- Completion tokens: {response['usage']['completion_tokens']}\n"
                usage_info += f"- Total tokens: {response['usage']['total_tokens']}\n"
                usage_info += f"- Estimated cost: {response['usage']['estimated_cost']}"
            
            provider_info = f" ({response['provider']})" if response.get('provider') else ""
            result = f"🤖 {response['model'].upper()}{provider_info} CODE REVIEW:\n\n{response['content']}{usage_info}"
            
        elif tool_name == "ai_brainstorm":
            topic = arguments.get("topic", "")
            model = arguments.get("model", DEFAULT_MODEL)
            context = arguments.get("context", "")
            
            prompt = f"Let's brainstorm about: {topic}"
            if context:
                prompt += f"\n\nContext: {context}"
            prompt += "\n\nProvide creative ideas, alternatives, and considerations."
            
            response = call_openrouter(prompt, model, 0.7, 4096)
            
            usage_info = ""
            if response["usage"]:
                usage_info = f"\n\n📊 Token Usage:\n"
                usage_info += f"- Prompt tokens: {response['usage']['prompt_tokens']}\n"
                usage_info += f"- Completion tokens: {response['usage']['completion_tokens']}\n"
                usage_info += f"- Total tokens: {response['usage']['total_tokens']}\n"
                usage_info += f"- Estimated cost: {response['usage']['estimated_cost']}"
            
            provider_info = f" ({response['provider']})" if response.get('provider') else ""
            result = f"🤖 {response['model'].upper()}{provider_info} BRAINSTORM:\n\n{response['content']}{usage_info}"
            
        elif tool_name == "list_models":
            result = "📋 Available AI Models through OpenRouter:\n\n"
            for key, value in AVAILABLE_MODELS.items():
                result += f"- {key}: {value}\n"
            result += f"\nDefault model: {DEFAULT_MODEL}"
            
        elif tool_name == "get_token_usage":
            detailed = arguments.get("detailed", False)
            period = arguments.get("period", "all")
            
            # Get usage from database
            usage_data = get_usage_from_db(detailed, period)
            
            if "error" in usage_data and usage_data["error"] != "Database connection failed":
                result = f"⚠️ Error getting usage data: {usage_data['error']}\n\n"
                result += "Falling back to session data:\n\n"
                # Fall back to in-memory data
                result += f"Total Prompt Tokens: {token_usage['total_prompt_tokens']:,}\n"
                result += f"Total Completion Tokens: {token_usage['total_completion_tokens']:,}\n"
                result += f"Total Tokens: {token_usage['total_prompt_tokens'] + token_usage['total_completion_tokens']:,}\n"
                result += f"Total Estimated Cost: ${token_usage['total_cost']:.4f}\n"
                result += f"Total Requests: {len(token_usage['requests'])}\n"
            else:
                period_label = {
                    "all": "All Time",
                    "today": "Today",
                    "month": "This Month",
                    "session": "Current Session"
                }.get(period, period)
                
                result = f"📊 Token Usage Statistics ({period_label}):\n\n"
                result += f"Total Prompt Tokens: {usage_data['total_prompt_tokens']:,}\n"
                result += f"Total Completion Tokens: {usage_data['total_completion_tokens']:,}\n"
                result += f"Total Tokens: {usage_data['total_tokens']:,}\n"
                result += f"Total Estimated Cost: ${usage_data['total_cost']:.4f}\n"
                result += f"Total Requests: {usage_data['total_requests']}\n"
                
                if detailed and usage_data['requests']:
                    result += "\n\n📝 Request History:\n"
                    for i, req in enumerate(usage_data['requests'][:10], 1):  # Show last 10
                        result += f"\n{i}. Model: {req['model']}\n"
                        result += f"   Tokens: {req['total_tokens']} (P:{req['prompt_tokens']}, C:{req['completion_tokens']})\n"
                        result += f"   Cost: ${req['cost']:.4f}\n"
                        if 'created_at' in req:
                            result += f"   Time: {req['created_at']}\n"
        
        elif tool_name == "get_cache_stats":
            result = "📊 Cache Statistics:\n\n"
            result += "Cache feature is not yet implemented.\n"
            result += "This will track repeated prompts to save on API costs."
            
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }

def main():
    """Main server loop"""
    # Initialize database
    db_initialized = init_database()
    if not db_initialized:
        print("Warning: Database connection failed. Usage tracking will be session-only.", file=sys.stderr)
    
    # Check API key on startup
    if OPENROUTER_API_KEY == "YOUR_API_KEY_HERE":
        print(json.dumps({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": "Please set your OpenRouter API key in the server_openrouter.py file or OPENROUTER_API_KEY environment variable"
            }
        }), file=sys.stdout, flush=True)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line.strip())
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            if method == "initialize":
                response = handle_initialize(request_id)
            elif method == "tools/list":
                response = handle_tools_list(request_id)
            elif method == "tools/call":
                response = handle_tool_call(request_id, params)
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            send_response(response)
            
        except json.JSONDecodeError:
            continue
        except EOFError:
            break
        except Exception as e:
            if 'request_id' in locals():
                send_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                })

if __name__ == "__main__":
    main()