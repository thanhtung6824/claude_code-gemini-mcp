# OpenRouter Usage Tracking Database

This directory contains the database schema and related files for persistent usage tracking of OpenRouter API calls.

## Features

- **Persistent Storage**: All API usage is stored in PostgreSQL database
- **Automatic Summaries**: Daily and monthly usage summaries are automatically maintained via triggers
- **Model-Specific Pricing**: Accurate cost calculation based on model-specific pricing
- **Multiple Query Periods**: Query usage by all-time, today, this month, or current session
- **Detailed History**: Track individual requests with timestamps and costs

## Database Schema

### Tables

1. **usage_records**: Stores individual API calls
   - Tracks model, tokens, costs, timestamps
   - Includes session_id for session-based queries
   - Supports metadata storage in JSONB format

2. **daily_usage_summary**: Aggregated daily usage by model
   - Automatically updated via trigger
   - Optimized for daily reporting

3. **monthly_usage_summary**: Aggregated monthly usage by model
   - Automatically updated via trigger
   - Optimized for monthly reporting

4. **model_pricing**: Stores pricing per million tokens for each model
   - Used for accurate cost calculation
   - Pre-populated with common models

### Views

1. **daily_usage_view**: Enhanced daily usage with calculated metrics
2. **monthly_usage_view**: Enhanced monthly usage with formatted dates

## Setup

1. Create the database:
   ```bash
   psql -U <username> -d postgres -c "CREATE DATABASE openrouter;"
   ```

2. Apply the schema:
   ```bash
   psql -U <username> -d openrouter < schema.sql
   ```

## Usage in Server

The server automatically:
- Saves usage data after each API call
- Retrieves usage statistics from the database
- Falls back to session-only tracking if database is unavailable

### Available Query Periods

When using `get_token_usage` tool:
- `all`: All-time usage
- `today`: Today's usage only
- `month`: Current month's usage
- `session`: Current session only

## Example Queries

### Get total usage for today:
```sql
SELECT 
    SUM(total_tokens) as tokens,
    SUM(total_cost) as cost
FROM usage_records
WHERE DATE(created_at) = CURRENT_DATE;
```

### Get usage by model for this month:
```sql
SELECT * FROM monthly_usage_view
WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
  AND month = EXTRACT(MONTH FROM CURRENT_DATE);
```

### Get most expensive requests:
```sql
SELECT model, total_tokens, total_cost, created_at
FROM usage_records
ORDER BY total_cost DESC
LIMIT 10;
```

## Maintenance

The database uses triggers to automatically maintain summary tables, so no manual maintenance is required. However, you may want to:

- Periodically archive old usage_records
- Update model_pricing table when OpenRouter changes pricing
- Add indexes if query performance degrades with large datasets