-- P(Doom)1 Database Schema Migration v3
-- Cumulative Hash Verification System
-- Implements timestamp priority system for duplicate hash handling
-- See: pdoom1/docs/HASH_VERIFICATION_POLICY.md

-- ============================================================================
-- VERIFICATION HASH TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS verification_hashes (
    hash_id SERIAL PRIMARY KEY,
    verification_hash VARCHAR(64) UNIQUE NOT NULL,
    first_submission_id UUID REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    first_submitted_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    first_submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duplicate_count INTEGER DEFAULT 0,
    seed VARCHAR(100) NOT NULL,

    -- Rapid duplicate detection (10+ in 1 hour = flag for review)
    rapid_duplicate_flag BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,
    flagged_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_hash_length CHECK (char_length(verification_hash) = 64),
    CONSTRAINT valid_duplicate_count CHECK (duplicate_count >= 0)
);

COMMENT ON TABLE verification_hashes IS 'Track first occurrence of each unique verification hash';
COMMENT ON COLUMN verification_hashes.verification_hash IS 'SHA-256 cumulative hash from VerificationTracker';
COMMENT ON COLUMN verification_hashes.first_submission_id IS 'First game session to submit this hash';
COMMENT ON COLUMN verification_hashes.first_submitted_by IS 'User who discovered this strategy first';
COMMENT ON COLUMN verification_hashes.first_submitted_at IS 'Timestamp of first submission (timestamp priority)';
COMMENT ON COLUMN verification_hashes.duplicate_count IS 'Number of duplicate submissions (same hash, different players)';
COMMENT ON COLUMN verification_hashes.rapid_duplicate_flag IS 'True if 10+ duplicates within 1 hour (potential bot farm)';

-- ============================================================================
-- DUPLICATE HASH TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS hash_duplicates (
    duplicate_id SERIAL PRIMARY KEY,
    hash_id INTEGER REFERENCES verification_hashes(hash_id) ON DELETE CASCADE,
    session_id UUID REFERENCES game_sessions(session_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    time_delta_seconds INTEGER, -- Seconds after first submission
    is_self_duplicate BOOLEAN DEFAULT FALSE, -- True if same user submitted this hash before

    -- Constraints
    CONSTRAINT valid_time_delta CHECK (time_delta_seconds IS NULL OR time_delta_seconds >= 0)
);

COMMENT ON TABLE hash_duplicates IS 'Track all duplicate hash submissions';
COMMENT ON COLUMN hash_duplicates.time_delta_seconds IS 'Seconds between first submission and this duplicate';
COMMENT ON COLUMN hash_duplicates.is_self_duplicate IS 'True if user resubmitted their own hash (practice/accident)';

-- ============================================================================
-- LEADERBOARD ENHANCEMENTS
-- ============================================================================

-- Add verification flags to existing leaderboard_entries table
ALTER TABLE leaderboard_entries
ADD COLUMN IF NOT EXISTS is_original_hash BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_duplicate_hash BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN leaderboard_entries.is_original_hash IS 'True if this was the first submission of this hash';
COMMENT ON COLUMN leaderboard_entries.is_duplicate_hash IS 'True if this hash was submitted before by another player';

-- ============================================================================
-- USER PREFERENCES FOR ATTRIBUTION
-- ============================================================================

-- Add opt-in attribution for "Hall of Fame" feature
ALTER TABLE users
ADD COLUMN IF NOT EXISTS display_discoveries BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verified_external_account TEXT;

COMMENT ON COLUMN users.display_discoveries IS 'Opt-in to display pseudonym for first discoveries (Hall of Fame)';
COMMENT ON COLUMN users.verified_external_account IS 'Optional linked account for verification badge (Steam, Forum, etc.)';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Verification hash lookups (critical path for submissions)
CREATE INDEX IF NOT EXISTS idx_verification_hash
    ON verification_hashes(verification_hash);

CREATE INDEX IF NOT EXISTS idx_verification_seed
    ON verification_hashes(seed);

CREATE INDEX IF NOT EXISTS idx_verification_flagged
    ON verification_hashes(rapid_duplicate_flag)
    WHERE rapid_duplicate_flag = TRUE;

-- Duplicate tracking
CREATE INDEX IF NOT EXISTS idx_hash_duplicates_hash_id
    ON hash_duplicates(hash_id);

CREATE INDEX IF NOT EXISTS idx_hash_duplicates_user_id
    ON hash_duplicates(user_id);

CREATE INDEX IF NOT EXISTS idx_hash_duplicates_submitted_at
    ON hash_duplicates(submitted_at DESC);

-- Leaderboard queries (originals only vs all submissions)
CREATE INDEX IF NOT EXISTS idx_leaderboard_original_hash
    ON leaderboard_entries(seed, score DESC, is_original_hash)
    WHERE is_original_hash = TRUE;

CREATE INDEX IF NOT EXISTS idx_leaderboard_all_submissions
    ON leaderboard_entries(seed, score DESC, submitted_at DESC);

-- ============================================================================
-- FUNCTIONS FOR DUPLICATE DETECTION
-- ============================================================================

-- Function to check for rapid duplicates (10+ in 1 hour)
CREATE OR REPLACE FUNCTION check_rapid_duplicates(p_hash_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    duplicate_count INTEGER;
    time_window INTERVAL := '1 hour';
BEGIN
    -- Count duplicates in last hour
    SELECT COUNT(*)
    INTO duplicate_count
    FROM hash_duplicates
    WHERE hash_id = p_hash_id
        AND submitted_at >= (NOW() - time_window);

    -- 10+ duplicates in 1 hour = rapid duplicate activity
    RETURN (duplicate_count >= 10);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_rapid_duplicates IS 'Check if hash has 10+ duplicates in last hour (bot detection)';

-- Function to get time delta for duplicate submission
CREATE OR REPLACE FUNCTION calculate_time_delta(
    p_first_submitted_at TIMESTAMP WITH TIME ZONE,
    p_current_time TIMESTAMP WITH TIME ZONE
)
RETURNS INTEGER AS $$
BEGIN
    RETURN EXTRACT(EPOCH FROM (p_current_time - p_first_submitted_at))::INTEGER;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_time_delta IS 'Calculate seconds between first submission and current time';

-- ============================================================================
-- TRIGGER FOR AUTO-FLAGGING RAPID DUPLICATES
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_check_rapid_duplicates()
RETURNS TRIGGER AS $$
DECLARE
    is_rapid BOOLEAN;
BEGIN
    -- Check if this hash now has rapid duplicates
    is_rapid := check_rapid_duplicates(NEW.hash_id);

    -- If rapid duplicates detected, flag the original hash
    IF is_rapid THEN
        UPDATE verification_hashes
        SET rapid_duplicate_flag = TRUE,
            flag_reason = 'Rapid duplicate detection: 10+ submissions in 1 hour',
            flagged_at = NOW()
        WHERE hash_id = NEW.hash_id
            AND rapid_duplicate_flag = FALSE; -- Only flag once
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on hash_duplicates insert
CREATE TRIGGER trigger_rapid_duplicate_check
    AFTER INSERT ON hash_duplicates
    FOR EACH ROW
    EXECUTE FUNCTION trigger_check_rapid_duplicates();

COMMENT ON TRIGGER trigger_rapid_duplicate_check ON hash_duplicates IS 'Auto-flag rapid duplicate activity for admin review';

-- ============================================================================
-- ANALYTICS VIEWS
-- ============================================================================

-- View: Most reproduced strategies (popular/obvious)
CREATE OR REPLACE VIEW v_popular_strategies AS
SELECT
    vh.seed,
    vh.verification_hash,
    vh.duplicate_count,
    vh.first_submitted_at,
    u.pseudonym AS discoverer,
    u.display_discoveries AS show_discoverer
FROM verification_hashes vh
LEFT JOIN users u ON vh.first_submitted_by = u.user_id
ORDER BY vh.duplicate_count DESC;

COMMENT ON VIEW v_popular_strategies IS 'Most reproduced strategies (sorted by duplicate count)';

-- View: Rarest strategies (creative/difficult)
CREATE OR REPLACE VIEW v_rare_strategies AS
SELECT
    vh.seed,
    vh.verification_hash,
    vh.duplicate_count,
    vh.first_submitted_at,
    u.pseudonym AS discoverer,
    u.display_discoveries AS show_discoverer
FROM verification_hashes vh
LEFT JOIN users u ON vh.first_submitted_by = u.user_id
WHERE vh.duplicate_count = 0
ORDER BY vh.first_submitted_at DESC;

COMMENT ON VIEW v_rare_strategies IS 'Unique strategies (zero duplicates)';

-- View: Leaderboard with discovery information
CREATE OR REPLACE VIEW v_leaderboard_with_discoveries AS
SELECT
    le.entry_id,
    le.session_id,
    u.pseudonym,
    le.seed,
    le.score,
    le.submitted_at,
    le.is_original_hash,
    le.is_duplicate_hash,
    vh.verification_hash,
    vh.duplicate_count,
    vh.first_submitted_at AS discovered_at,
    first_user.pseudonym AS discoverer,
    first_user.display_discoveries AS show_discoverer
FROM leaderboard_entries le
JOIN users u ON le.user_id = u.user_id
LEFT JOIN game_sessions gs ON le.session_id = gs.session_id
LEFT JOIN verification_hashes vh ON gs.checksum = vh.verification_hash
LEFT JOIN users first_user ON vh.first_submitted_by = first_user.user_id
ORDER BY le.seed, le.score DESC;

COMMENT ON VIEW v_leaderboard_with_discoveries IS 'Leaderboard with original discovery information';

-- ============================================================================
-- SAMPLE QUERIES FOR API IMPLEMENTATION
-- ============================================================================

-- Query 1: Check if hash exists (for timestamp priority)
-- SELECT verification_hash, first_submitted_by, first_submitted_at, duplicate_count
-- FROM verification_hashes
-- WHERE verification_hash = $1;

-- Query 2: Insert new hash (first discovery)
-- INSERT INTO verification_hashes (verification_hash, first_submission_id, first_submitted_by, first_submitted_at, seed)
-- VALUES ($1, $2, $3, NOW(), $4)
-- RETURNING hash_id;

-- Query 3: Record duplicate submission
-- INSERT INTO hash_duplicates (hash_id, session_id, user_id, submitted_at, time_delta_seconds, is_self_duplicate)
-- VALUES ($1, $2, $3, NOW(), $4, $5);

-- Query 4: Update duplicate count
-- UPDATE verification_hashes
-- SET duplicate_count = duplicate_count + 1
-- WHERE hash_id = $1;

-- Query 5: Get leaderboard (originals only)
-- SELECT * FROM v_leaderboard_with_discoveries
-- WHERE is_original_hash = TRUE
--     AND seed = $1
-- ORDER BY score DESC
-- LIMIT 100;

-- Query 6: Get flagged hashes (admin dashboard)
-- SELECT * FROM verification_hashes
-- WHERE rapid_duplicate_flag = TRUE
-- ORDER BY flagged_at DESC;

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
    AND table_name IN ('verification_hashes', 'hash_duplicates')
ORDER BY table_name;

-- Verify indexes were created
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN ('verification_hashes', 'hash_duplicates')
ORDER BY tablename, indexname;

-- Verify views were created
SELECT
    table_name as view_name
FROM information_schema.views
WHERE table_schema = 'public'
    AND table_name LIKE 'v_%'
ORDER BY table_name;

-- Migration complete
SELECT 'Migration 003_add_verification_hashes.sql completed successfully!' as status,
       'Cumulative hash verification system ready for API integration' as next_step;
