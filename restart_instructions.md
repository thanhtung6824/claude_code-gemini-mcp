# Restart MCP Server Instructions

The OpenRouter MCP server has been updated with database persistence. To apply the changes:

## From Claude Desktop App:

1. Go to Settings (⚙️)
2. Navigate to "Developer" section
3. Find "openrouter-collab" in the MCP Servers list
4. Click the restart button (🔄) next to it

## What's New:

- **Database Persistence**: All usage is now saved to PostgreSQL
- **Time-based Queries**: Use `get_token_usage` with period parameter:
  - `period: "all"` - All-time usage
  - `period: "today"` - Today's usage only
  - `period: "month"` - Current month's usage
  - `period: "session"` - Current session only
- **Automatic Summaries**: Daily and monthly usage are automatically aggregated
- **Accurate Pricing**: Model-specific pricing from database

## Verify It's Working:

After restart, try:
1. Use `ask_ai` tool to make some requests
2. Use `get_token_usage` with `period: "today"` to see today's usage
3. Check the database directly with: `psql -U tung -d openrouter -c "SELECT * FROM usage_records ORDER BY created_at DESC LIMIT 5;"`

## Troubleshooting:

If you see database connection warnings, ensure:
- PostgreSQL is running: `brew services list | grep postgresql`
- Database exists: `psql -U tung -l | grep openrouter`
- Can connect: `psql -U tung -d openrouter -c "SELECT 1;"`

The server will still work without database (session-only tracking) if connection fails.