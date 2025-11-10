-- P(Doom)1 Database Schema Migration v2
-- Add game_events table for dynamic event system
-- Created: 2025-11-10
-- Related Issue: #67

-- ============================================================================
-- GAME EVENTS TABLE
-- ============================================================================
-- Stores event catalog for dynamic game content delivery via API
-- Events are imported from pdoom-data cleaned event logs

CREATE TABLE IF NOT EXISTS game_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    event_type VARCHAR(50), -- e.g., 'combat', 'economic', 'narrative', 'research', 'political'
    category VARCHAR(50),    -- Subcategory for filtering
    difficulty INTEGER,      -- 1-10 scale for balancing
    impact_pdoom FLOAT,      -- Expected impact on P(Doom) (-1.0 to 1.0)
    impact_funding FLOAT,    -- Expected impact on funding (-1.0 to 1.0)
    parameters JSONB,        -- Flexible event configuration (choices, outcomes, etc.)
    tags TEXT[],             -- Searchable tags (e.g., ['boss', 'endgame', 'critical'])
    source VARCHAR(50) DEFAULT 'pdoom-data', -- Source of event data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    -- Constraints
    CONSTRAINT valid_difficulty CHECK (difficulty IS NULL OR (difficulty >= 1 AND difficulty <= 10)),
    CONSTRAINT valid_impact_pdoom CHECK (impact_pdoom IS NULL OR (impact_pdoom >= -1.0 AND impact_pdoom <= 1.0)),
    CONSTRAINT valid_impact_funding CHECK (impact_funding IS NULL OR (impact_funding >= -1.0 AND impact_funding <= 1.0)),
    CONSTRAINT valid_event_type CHECK (event_type IN ('combat', 'economic', 'narrative', 'research', 'political', 'random', 'special'))
);

COMMENT ON TABLE game_events IS 'Catalog of game events for dynamic content delivery';
COMMENT ON COLUMN game_events.name IS 'Display name of the event';
COMMENT ON COLUMN game_events.event_type IS 'Primary event category for filtering';
COMMENT ON COLUMN game_events.difficulty IS 'Event difficulty rating (1=easy, 10=very hard)';
COMMENT ON COLUMN game_events.impact_pdoom IS 'Expected P(Doom) impact (-1.0 to +1.0)';
COMMENT ON COLUMN game_events.impact_funding IS 'Expected funding impact (-1.0 to +1.0)';
COMMENT ON COLUMN game_events.parameters IS 'Event configuration (choices, outcomes, requirements, etc.)';
COMMENT ON COLUMN game_events.tags IS 'Searchable tags for event discovery';
COMMENT ON COLUMN game_events.is_active IS 'Whether event is active and can be served to clients';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Fast lookup by event type
CREATE INDEX IF NOT EXISTS idx_game_events_type
    ON game_events(event_type)
    WHERE is_active = TRUE;

-- Difficulty-based filtering
CREATE INDEX IF NOT EXISTS idx_game_events_difficulty
    ON game_events(difficulty)
    WHERE is_active = TRUE;

-- Tag-based search (GIN index for array operations)
CREATE INDEX IF NOT EXISTS idx_game_events_tags
    ON game_events USING GIN(tags);

-- Category filtering
CREATE INDEX IF NOT EXISTS idx_game_events_category
    ON game_events(category)
    WHERE is_active = TRUE;

-- Composite index for type + difficulty queries
CREATE INDEX IF NOT EXISTS idx_game_events_type_difficulty
    ON game_events(event_type, difficulty)
    WHERE is_active = TRUE;

-- Active events only
CREATE INDEX IF NOT EXISTS idx_game_events_active
    ON game_events(is_active, created_at DESC);

-- Full-text search on name and description (optional, for future use)
-- CREATE INDEX IF NOT EXISTS idx_game_events_search
--     ON game_events USING GIN(to_tsvector('english', name || ' ' || COALESCE(description, '')));

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_game_events_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_game_events_updated_at
    BEFORE UPDATE ON game_events
    FOR EACH ROW
    EXECUTE FUNCTION update_game_events_updated_at();

COMMENT ON TRIGGER trigger_game_events_updated_at ON game_events IS 'Auto-update updated_at on row modification';

-- ============================================================================
-- SAMPLE DATA (for testing, can be removed for production)
-- ============================================================================

INSERT INTO game_events (name, description, event_type, category, difficulty, impact_pdoom, impact_funding, parameters, tags)
VALUES
    (
        'Rogue AI Incident',
        'An experimental AI system has exhibited unexpected behavior. Choose your response carefully.',
        'combat',
        'ai_safety',
        8,
        0.15,
        -0.10,
        '{"choices": [{"id": "shutdown", "text": "Immediate shutdown", "pdoom_impact": -0.05}, {"id": "observe", "text": "Continue monitoring", "pdoom_impact": 0.20}]}'::jsonb,
        ARRAY['crisis', 'high-stakes', 'ai-safety']
    ),
    (
        'Major Breakthrough',
        'Your research team has achieved a significant breakthrough in interpretability.',
        'research',
        'progress',
        5,
        -0.12,
        0.08,
        '{"outcomes": {"publicity": "high", "funding_boost": 1.5}}'::jsonb,
        ARRAY['positive', 'research', 'funding-boost']
    ),
    (
        'Funding Crisis',
        'A major donor has withdrawn their support. You need to find alternative funding sources.',
        'economic',
        'funding',
        6,
        0.05,
        -0.25,
        '{"duration": 3, "required_action": "fundraising"}'::jsonb,
        ARRAY['negative', 'funding', 'challenge']
    ),
    (
        'Public Relations Disaster',
        'A leaked internal memo has caused a media firestorm. How do you respond?',
        'political',
        'reputation',
        7,
        0.08,
        -0.15,
        '{"choices": [{"id": "deny", "text": "Issue denial"}, {"id": "apologize", "text": "Public apology"}, {"id": "silent", "text": "Stay silent"}]}'::jsonb,
        ARRAY['crisis', 'pr', 'political']
    ),
    (
        'Talent Acquisition',
        'A world-class AI safety researcher is considering joining your organization.',
        'narrative',
        'team',
        4,
        -0.08,
        0.05,
        '{"salary_cost": 150000, "skill_bonus": 1.3}'::jsonb,
        ARRAY['positive', 'hiring', 'talent']
    )
ON CONFLICT DO NOTHING;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get random event by criteria
CREATE OR REPLACE FUNCTION get_random_event(
    p_event_type VARCHAR DEFAULT NULL,
    p_difficulty_min INTEGER DEFAULT NULL,
    p_difficulty_max INTEGER DEFAULT NULL,
    p_tags TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    event_id UUID,
    name VARCHAR,
    description TEXT,
    event_type VARCHAR,
    difficulty INTEGER,
    parameters JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ge.event_id,
        ge.name,
        ge.description,
        ge.event_type,
        ge.difficulty,
        ge.parameters
    FROM game_events ge
    WHERE
        ge.is_active = TRUE
        AND (p_event_type IS NULL OR ge.event_type = p_event_type)
        AND (p_difficulty_min IS NULL OR ge.difficulty >= p_difficulty_min)
        AND (p_difficulty_max IS NULL OR ge.difficulty <= p_difficulty_max)
        AND (p_tags IS NULL OR ge.tags && p_tags) -- Array overlap operator
    ORDER BY RANDOM()
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_random_event IS 'Get a random active event matching optional criteria';

-- Function to get events by type
CREATE OR REPLACE FUNCTION get_events_by_type(p_event_type VARCHAR, p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    event_id UUID,
    name VARCHAR,
    description TEXT,
    difficulty INTEGER,
    tags TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ge.event_id,
        ge.name,
        ge.description,
        ge.difficulty,
        ge.tags
    FROM game_events ge
    WHERE
        ge.is_active = TRUE
        AND ge.event_type = p_event_type
    ORDER BY ge.difficulty ASC, ge.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_events_by_type IS 'Get active events of a specific type';

-- ============================================================================
-- GRANTS AND PERMISSIONS
-- ============================================================================

-- For application user (read-write access)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON game_events TO pdoom_api;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pdoom_api;

-- For analytics/dashboard user (read-only access)
-- GRANT SELECT ON game_events TO pdoom_readonly;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify table was created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'game_events') as column_count
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = 'game_events';

-- Verify indexes were created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'game_events'
ORDER BY indexname;

-- Verify sample data was inserted
SELECT COUNT(*) as sample_event_count FROM game_events;

-- Show event type distribution
SELECT event_type, COUNT(*) as count
FROM game_events
WHERE is_active = TRUE
GROUP BY event_type
ORDER BY count DESC;

-- Migration complete
SELECT 'Migration 002_add_game_events.sql completed successfully!' as status,
       (SELECT COUNT(*) FROM game_events) as total_events,
       (SELECT COUNT(*) FROM game_events WHERE is_active = TRUE) as active_events;
