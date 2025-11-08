-- P(Doom)1 Database Schema Migration v1
-- Initial schema creation for production database
-- Based on INTEGRATION_PLAN.md specification

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- USER MANAGEMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pseudonym VARCHAR(50) UNIQUE NOT NULL,
    email_hash VARCHAR(64), -- Hashed for privacy (SHA-256)
    privacy_settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE,
    opt_in_leaderboard BOOLEAN DEFAULT FALSE,
    opt_in_analytics BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT pseudonym_length CHECK (char_length(pseudonym) >= 3),
    CONSTRAINT pseudonym_format CHECK (pseudonym ~ '^[a-zA-Z0-9_-]+$')
);

COMMENT ON TABLE users IS 'User accounts with privacy-first pseudonymous design';
COMMENT ON COLUMN users.email_hash IS 'SHA-256 hash of email for privacy-preserving lookup';
COMMENT ON COLUMN users.opt_in_leaderboard IS 'User consent for public leaderboard display';
COMMENT ON COLUMN users.opt_in_analytics IS 'User consent for analytics data collection';

-- ============================================================================
-- GAME SESSIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS game_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    seed VARCHAR(100) NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    game_version VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    final_score INTEGER,
    final_turn INTEGER,
    victory_type VARCHAR(50),
    game_metadata JSONB,
    checksum VARCHAR(64), -- Anti-cheat verification hash
    duration_seconds FLOAT,

    -- Constraints
    CONSTRAINT valid_score CHECK (final_score IS NULL OR final_score >= 0),
    CONSTRAINT valid_duration CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

COMMENT ON TABLE game_sessions IS 'Individual game play sessions with complete metadata';
COMMENT ON COLUMN game_sessions.checksum IS 'Verification hash for anti-cheat validation';
COMMENT ON COLUMN game_sessions.game_metadata IS 'Final game metrics (P(Doom), money, staff, etc.)';

-- ============================================================================
-- LEADERBOARDS
-- ============================================================================

CREATE TABLE IF NOT EXISTS leaderboard_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    seed VARCHAR(100) NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    score INTEGER NOT NULL,
    rank INTEGER, -- Calculated field, updated by triggers
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    metadata JSONB,

    -- Constraints
    CONSTRAINT valid_entry_score CHECK (score >= 0)
);

COMMENT ON TABLE leaderboard_entries IS 'Leaderboard entries linking to game sessions';
COMMENT ON COLUMN leaderboard_entries.rank IS 'Auto-calculated rank within seed';
COMMENT ON COLUMN leaderboard_entries.verified IS 'Anti-cheat verification status';

-- ============================================================================
-- WEEKLY CHALLENGES
-- ============================================================================

CREATE TABLE IF NOT EXISTS weekly_challenges (
    challenge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    week_starting DATE NOT NULL,
    seed VARCHAR(100) NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    reward_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_week CHECK (week_starting = date_trunc('week', week_starting)::date)
);

COMMENT ON TABLE weekly_challenges IS 'Weekly competitive challenges with specific seeds';
COMMENT ON COLUMN weekly_challenges.week_starting IS 'Monday date of challenge week';

-- ============================================================================
-- COMMUNITY CONTENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS blog_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    published_at TIMESTAMP WITH TIME ZONE,
    source_repo VARCHAR(50) DEFAULT 'pdoom1',
    sync_status VARCHAR(20) DEFAULT 'pending',

    -- Constraints
    CONSTRAINT valid_sync_status CHECK (sync_status IN ('pending', 'synced', 'failed'))
);

COMMENT ON TABLE blog_entries IS 'Blog entries synced from game repository';
COMMENT ON COLUMN blog_entries.source_repo IS 'Source repository (pdoom1, pdoom1-website, etc.)';

-- ============================================================================
-- ANALYTICS (PRIVACY-RESPECTING)
-- ============================================================================

CREATE TABLE IF NOT EXISTS analytics_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Automatic deletion after 90 days for privacy
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
);

COMMENT ON TABLE analytics_events IS 'Privacy-respecting analytics with auto-expiration';
COMMENT ON COLUMN analytics_events.expires_at IS 'Auto-deletion timestamp (90 days retention)';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- User lookup indexes
CREATE INDEX IF NOT EXISTS idx_users_pseudonym ON users(pseudonym);
CREATE INDEX IF NOT EXISTS idx_users_email_hash ON users(email_hash) WHERE email_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at DESC);

-- Game session indexes
CREATE INDEX IF NOT EXISTS idx_game_sessions_user_completed
    ON game_sessions(user_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_game_sessions_seed
    ON game_sessions(seed);
CREATE INDEX IF NOT EXISTS idx_game_sessions_version
    ON game_sessions(game_version);

-- Leaderboard indexes (critical for performance)
CREATE INDEX IF NOT EXISTS idx_leaderboard_seed_score
    ON leaderboard_entries(seed, score DESC);
CREATE INDEX IF NOT EXISTS idx_leaderboard_user
    ON leaderboard_entries(user_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_leaderboard_verified
    ON leaderboard_entries(verified, score DESC)
    WHERE verified = true;

-- Weekly challenge indexes
CREATE INDEX IF NOT EXISTS idx_weekly_challenges_active
    ON weekly_challenges(is_active, week_starting DESC)
    WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_weekly_challenges_week
    ON weekly_challenges(week_starting DESC);

-- Blog entry indexes
CREATE INDEX IF NOT EXISTS idx_blog_entries_published
    ON blog_entries(published_at DESC)
    WHERE published_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_blog_entries_slug
    ON blog_entries(slug);

-- Analytics indexes
CREATE INDEX IF NOT EXISTS idx_analytics_user_type
    ON analytics_events(user_id, event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_expires
    ON analytics_events(expires_at)
    WHERE expires_at IS NOT NULL;

-- ============================================================================
-- TRIGGERS AND FUNCTIONS
-- ============================================================================

-- Function to cleanup expired analytics data
CREATE OR REPLACE FUNCTION cleanup_expired_analytics()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM analytics_events
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_analytics() IS 'Delete analytics events past their expiration date';

-- Function to update user last_active timestamp
CREATE OR REPLACE FUNCTION update_user_last_active()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE users
    SET last_active = NOW()
    WHERE user_id = NEW.user_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update last_active on game session
CREATE TRIGGER trigger_update_last_active
    AFTER INSERT ON game_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_user_last_active();

COMMENT ON TRIGGER trigger_update_last_active ON game_sessions IS 'Auto-update user last_active on new session';

-- ============================================================================
-- INITIAL DATA / SEEDS
-- ============================================================================

-- Create a test user for development (optional, can be removed for production)
-- Password is not needed as we use pseudonym-only auth
INSERT INTO users (pseudonym, opt_in_leaderboard, opt_in_analytics, privacy_settings)
VALUES
    ('TestPlayer', true, false, '{"public_profile": false}'::jsonb)
ON CONFLICT (pseudonym) DO NOTHING;

-- ============================================================================
-- GRANTS AND PERMISSIONS
-- ============================================================================

-- For application user (not superuser)
-- Uncomment and modify for your specific database user:

-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pdoom_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pdoom_app;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pdoom_app;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify tables were created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND table_name IN ('users', 'game_sessions', 'leaderboard_entries', 'weekly_challenges', 'blog_entries', 'analytics_events')
ORDER BY table_name;

-- Verify indexes were created
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN ('users', 'game_sessions', 'leaderboard_entries', 'weekly_challenges', 'blog_entries', 'analytics_events')
ORDER BY tablename, indexname;

-- Migration complete
SELECT 'Migration 001_initial_schema.sql completed successfully!' as status;
