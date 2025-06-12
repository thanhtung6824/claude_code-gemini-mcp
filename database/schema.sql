-- OpenRouter Usage Tracking Schema

-- Create usage_records table for storing individual API calls
CREATE TABLE IF NOT EXISTS usage_records (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    model VARCHAR(100) NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    prompt_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
    completion_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
    total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
    request_type VARCHAR(50) DEFAULT 'ask_ai',
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    metadata JSONB
);

-- Create indexes for common queries
CREATE INDEX idx_usage_records_created_at ON usage_records(created_at);
CREATE INDEX idx_usage_records_model ON usage_records(model);
CREATE INDEX idx_usage_records_session_id ON usage_records(session_id);
CREATE INDEX idx_usage_records_user_id ON usage_records(user_id);

-- Create daily usage summary table for faster aggregations
CREATE TABLE IF NOT EXISTS daily_usage_summary (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    model VARCHAR(100) NOT NULL,
    total_requests INTEGER NOT NULL DEFAULT 0,
    total_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
    UNIQUE(date, model)
);

-- Create monthly usage summary table
CREATE TABLE IF NOT EXISTS monthly_usage_summary (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    model VARCHAR(100) NOT NULL,
    total_requests INTEGER NOT NULL DEFAULT 0,
    total_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
    UNIQUE(year, month, model)
);

-- Create model pricing table for accurate cost calculation
CREATE TABLE IF NOT EXISTS model_pricing (
    id SERIAL PRIMARY KEY,
    model VARCHAR(100) NOT NULL UNIQUE,
    prompt_price_per_million DECIMAL(10, 6) NOT NULL,
    completion_price_per_million DECIMAL(10, 6) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default pricing for common models
INSERT INTO model_pricing (model, prompt_price_per_million, completion_price_per_million) VALUES
    ('claude-3-opus', 15.0, 75.0),
    ('claude-3-sonnet', 3.0, 15.0),
    ('claude-3-haiku', 0.25, 1.25),
    ('gpt-4', 30.0, 60.0),
    ('gpt-4-turbo', 10.0, 30.0),
    ('gpt-3.5-turbo', 0.5, 1.5),
    ('gemini-pro', 0.5, 1.5),
    ('mixtral-8x7b', 0.7, 0.7),
    ('llama-3-70b', 0.8, 0.8),
    ('llama-3-8b', 0.2, 0.2)
ON CONFLICT (model) DO NOTHING;

-- Create function to update daily summary
CREATE OR REPLACE FUNCTION update_daily_summary()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO daily_usage_summary (date, model, total_requests, total_prompt_tokens, total_completion_tokens, total_tokens, total_cost)
    VALUES (
        DATE(NEW.created_at),
        NEW.model,
        1,
        NEW.prompt_tokens,
        NEW.completion_tokens,
        NEW.total_tokens,
        NEW.total_cost
    )
    ON CONFLICT (date, model) DO UPDATE
    SET total_requests = daily_usage_summary.total_requests + 1,
        total_prompt_tokens = daily_usage_summary.total_prompt_tokens + NEW.prompt_tokens,
        total_completion_tokens = daily_usage_summary.total_completion_tokens + NEW.completion_tokens,
        total_tokens = daily_usage_summary.total_tokens + NEW.total_tokens,
        total_cost = daily_usage_summary.total_cost + NEW.total_cost;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create function to update monthly summary
CREATE OR REPLACE FUNCTION update_monthly_summary()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO monthly_usage_summary (year, month, model, total_requests, total_prompt_tokens, total_completion_tokens, total_tokens, total_cost)
    VALUES (
        EXTRACT(YEAR FROM NEW.created_at),
        EXTRACT(MONTH FROM NEW.created_at),
        NEW.model,
        1,
        NEW.prompt_tokens,
        NEW.completion_tokens,
        NEW.total_tokens,
        NEW.total_cost
    )
    ON CONFLICT (year, month, model) DO UPDATE
    SET total_requests = monthly_usage_summary.total_requests + 1,
        total_prompt_tokens = monthly_usage_summary.total_prompt_tokens + NEW.prompt_tokens,
        total_completion_tokens = monthly_usage_summary.total_completion_tokens + NEW.completion_tokens,
        total_tokens = monthly_usage_summary.total_tokens + NEW.total_tokens,
        total_cost = monthly_usage_summary.total_cost + NEW.total_cost;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to automatically update summaries
CREATE TRIGGER update_daily_summary_trigger
AFTER INSERT ON usage_records
FOR EACH ROW
EXECUTE FUNCTION update_daily_summary();

CREATE TRIGGER update_monthly_summary_trigger
AFTER INSERT ON usage_records
FOR EACH ROW
EXECUTE FUNCTION update_monthly_summary();

-- Create views for easy querying
CREATE VIEW daily_usage_view AS
SELECT 
    date,
    model,
    total_requests,
    total_prompt_tokens,
    total_completion_tokens,
    total_tokens,
    total_cost,
    total_cost / total_requests AS avg_cost_per_request
FROM daily_usage_summary
ORDER BY date DESC, model;

CREATE VIEW monthly_usage_view AS
SELECT 
    year,
    month,
    TO_CHAR(TO_DATE(year::text || '-' || month::text, 'YYYY-MM'), 'Month YYYY') AS month_name,
    model,
    total_requests,
    total_prompt_tokens,
    total_completion_tokens,
    total_tokens,
    total_cost,
    total_cost / total_requests AS avg_cost_per_request
FROM monthly_usage_summary
ORDER BY year DESC, month DESC, model;