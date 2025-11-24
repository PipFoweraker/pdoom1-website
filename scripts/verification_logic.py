#!/usr/bin/env python3
"""
Cumulative Hash Verification Logic
Implements timestamp priority system and plausibility checks
See: pdoom1/docs/HASH_VERIFICATION_POLICY.md
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import json


class VerificationError(Exception):
    """Raised when verification fails."""
    pass


class PlausibilityChecker:
    """Validates that final game states are plausible."""

    # Plausibility bounds (permissive to allow creative play)
    BOUNDS = {
        'doom': (0.0, 100.0),
        'money': (-10_000_000, 1_000_000_000),  # Can go negative (loans), but not absurdly
        'papers': (0, 1000),  # Can't be negative
        'research': (0, 100_000),
        'compute': (0, 1_000_000),
        'turn': (1, 500),
        'researchers': (0, 1000),
    }

    @classmethod
    def is_plausible(cls, final_state: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if final game state is within plausible bounds.

        Args:
            final_state: Final game state dictionary

        Returns:
            (is_valid, error_message) tuple
        """
        # Check doom
        doom = final_state.get('doom', 0)
        if not cls._in_bounds('doom', doom):
            return False, f"Implausible doom: {doom} (expected 0-100)"

        # Check money
        money = final_state.get('money', 0)
        if not cls._in_bounds('money', money):
            return False, f"Implausible money: {money}"

        # Check papers (can't be negative)
        papers = final_state.get('papers', 0)
        if not cls._in_bounds('papers', papers):
            return False, f"Implausible papers: {papers} (can't be negative)"

        # Check research
        research = final_state.get('research', 0)
        if not cls._in_bounds('research', research):
            return False, f"Implausible research: {research}"

        # Check compute
        compute = final_state.get('compute', 0)
        if not cls._in_bounds('compute', compute):
            return False, f"Implausible compute: {compute}"

        # Check turn count
        turn = final_state.get('turn', 0)
        if not cls._in_bounds('turn', turn):
            return False, f"Implausible turn count: {turn}"

        # Check researcher count
        researchers = final_state.get('researchers', 0)
        if not cls._in_bounds('researchers', researchers):
            return False, f"Implausible researcher count: {researchers}"

        return True, ""

    @classmethod
    def _in_bounds(cls, field: str, value: float) -> bool:
        """Check if value is within bounds for field."""
        if field not in cls.BOUNDS:
            return True  # Unknown field, skip check

        min_val, max_val = cls.BOUNDS[field]
        return min_val <= value <= max_val


class ScoreCalculator:
    """Recalculates score from game state to prevent tampering."""

    @staticmethod
    def calculate_score(final_state: Dict[str, Any]) -> int:
        """
        Calculate score from final game state.

        CRITICAL: This must match the game's scoring formula exactly!
        See: godot/scripts/game_manager.gd or equivalent

        Formula (example - adjust to match actual game):
            score = money * 0.1
                  + papers * 5000
                  + (100 - doom) * 1000
                  + researchers * 2000
        """
        money = final_state.get('money', 0)
        papers = final_state.get('papers', 0)
        doom = final_state.get('doom', 0)
        researchers = final_state.get('researchers', 0)

        # Calculate score
        score = 0
        score += money * 0.1
        score += papers * 5000
        score += (100 - doom) * 1000
        score += researchers * 2000

        return int(score)

    @staticmethod
    def validate_score(submitted_score: int, final_state: Dict[str, Any], tolerance: int = 100) -> Tuple[bool, str]:
        """
        Validate that submitted score matches calculated score.

        Args:
            submitted_score: Score submitted by client
            final_state: Final game state
            tolerance: Allowed difference (for rounding/edge cases)

        Returns:
            (is_valid, error_message) tuple
        """
        calculated_score = ScoreCalculator.calculate_score(final_state)
        difference = abs(submitted_score - calculated_score)

        if difference > tolerance:
            return False, f"Score mismatch: submitted {submitted_score}, calculated {calculated_score} (diff: {difference})"

        return True, ""


class HashVerificationHandler:
    """Handles cumulative hash verification with timestamp priority."""

    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db_manager = db_manager

    def process_submission(
        self,
        user_id: str,
        score_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process score submission with hash verification.

        Implements timestamp priority system:
        1. Check if hash exists
        2. If new: Record as original, create leaderboard entry
        3. If duplicate from same player: Log but ignore
        4. If duplicate from different player: Record duplicate, create entry

        Args:
            user_id: User UUID
            score_data: Score submission data with verification_hash

        Returns:
            Response dictionary with status, message, and data

        Raises:
            VerificationError: If verification fails
        """
        verification_hash = score_data.get('verification_hash')
        if not verification_hash:
            raise VerificationError("Missing verification_hash")

        if len(verification_hash) != 64:
            raise VerificationError("Invalid verification_hash length (expected 64 characters)")

        # Extract data
        seed = score_data['seed']
        score = score_data['score']
        final_state = score_data.get('final_state', {})

        # Step 1: Plausibility checks
        is_plausible, plausibility_error = PlausibilityChecker.is_plausible(final_state)
        if not is_plausible:
            raise VerificationError(f"Implausible game state: {plausibility_error}")

        # Step 2: Score recalculation
        is_valid_score, score_error = ScoreCalculator.validate_score(score, final_state)
        if not is_valid_score:
            raise VerificationError(f"Invalid score: {score_error}")

        # Step 3: Check if hash exists
        hash_check_query = """
            SELECT
                hash_id,
                first_submitted_by,
                first_submitted_at,
                duplicate_count
            FROM verification_hashes
            WHERE verification_hash = %s
        """

        hash_result = self.db_manager.execute_query(hash_check_query, (verification_hash,))
        is_first_submission = (not hash_result or len(hash_result) == 0)

        # Step 4: Create game session (always)
        session_id = self._create_game_session(user_id, score_data)

        if is_first_submission:
            # FIRST TIME this hash has been seen
            return self._handle_original_submission(
                user_id, session_id, verification_hash, seed, score, score_data
            )
        else:
            # DUPLICATE HASH
            hash_record = hash_result[0]
            first_player = str(hash_record['first_submitted_by'])
            first_timestamp = hash_record['first_submitted_at']

            if first_player == user_id:
                # Same player resubmitting
                return self._handle_self_duplicate(session_id, score, first_timestamp)
            else:
                # Different player found same strategy
                return self._handle_duplicate_submission(
                    hash_record, user_id, session_id, seed, score, first_timestamp
                )

    def _create_game_session(self, user_id: str, score_data: Dict[str, Any]) -> str:
        """Create game session record."""
        session_query = """
            INSERT INTO game_sessions (
                user_id, seed, config_hash, game_version,
                completed_at, final_score, final_turn,
                game_metadata, checksum, duration_seconds
            )
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
            RETURNING session_id
        """

        session_result = self.db_manager.execute_insert(
            session_query,
            (
                user_id,
                score_data['seed'],
                score_data.get('config_hash', 'default'),
                score_data.get('game_version', 'unknown'),
                score_data['score'],
                score_data.get('final_state', {}).get('turn', 0),
                json.dumps(score_data.get('final_state', {})),
                score_data['verification_hash'],
                score_data.get('duration_seconds', 0.0)
            )
        )

        return str(session_result['session_id'])

    def _handle_original_submission(
        self,
        user_id: str,
        session_id: str,
        verification_hash: str,
        seed: str,
        score: int,
        score_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle first-time hash submission (original discovery)."""

        # Record as original discoverer
        insert_hash_query = """
            INSERT INTO verification_hashes (
                verification_hash,
                first_submission_id,
                first_submitted_by,
                first_submitted_at,
                duplicate_count,
                seed
            )
            VALUES (%s, %s, %s, NOW(), 0, %s)
            RETURNING hash_id
        """

        self.db_manager.execute_insert(
            insert_hash_query,
            (verification_hash, session_id, user_id, seed)
        )

        # Create leaderboard entry (marked as original)
        leaderboard_query = """
            INSERT INTO leaderboard_entries (
                session_id, user_id, seed, config_hash, score,
                verified, is_original_hash, is_duplicate_hash
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, TRUE, FALSE)
            RETURNING entry_id
        """

        leaderboard_result = self.db_manager.execute_insert(
            leaderboard_query,
            (
                session_id, user_id, seed,
                score_data.get('config_hash', 'default'),
                score
            )
        )

        # Calculate rank
        rank = self._calculate_rank(seed, score)

        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "entry_id": str(leaderboard_result['entry_id']),
                "rank": rank,
                "score": score,
                "hash_status": "original",
                "message": "First player to achieve this strategy!"
            }
        }

    def _handle_self_duplicate(
        self,
        session_id: str,
        score: int,
        first_timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle same player resubmitting their own hash."""

        # Don't create leaderboard entry (already have one)
        return {
            "status": "accepted",
            "data": {
                "session_id": session_id,
                "score": score,
                "hash_status": "self_duplicate",
                "message": "You already submitted this strategy",
                "original_submission": first_timestamp.isoformat()
            }
        }

    def _handle_duplicate_submission(
        self,
        hash_record: Dict[str, Any],
        user_id: str,
        session_id: str,
        seed: str,
        score: int,
        first_timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle duplicate hash from different player."""

        hash_id = hash_record['hash_id']
        submitted_at = datetime.now()
        time_delta = int((submitted_at - first_timestamp).total_seconds())

        # Record duplicate
        duplicate_query = """
            INSERT INTO hash_duplicates (
                hash_id, session_id, user_id,
                submitted_at, time_delta_seconds, is_self_duplicate
            )
            VALUES (%s, %s, %s, NOW(), %s, FALSE)
        """

        self.db_manager.execute_query(
            duplicate_query,
            (hash_id, session_id, user_id, time_delta),
            fetch=False
        )

        # Increment duplicate count
        update_count_query = """
            UPDATE verification_hashes
            SET duplicate_count = duplicate_count + 1
            WHERE hash_id = %s
        """

        self.db_manager.execute_query(
            update_count_query,
            (hash_id,),
            fetch=False
        )

        # Create leaderboard entry (marked as duplicate)
        leaderboard_query = """
            INSERT INTO leaderboard_entries (
                session_id, user_id, seed, config_hash, score,
                verified, is_original_hash, is_duplicate_hash
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, FALSE, TRUE)
            RETURNING entry_id
        """

        leaderboard_result = self.db_manager.execute_insert(
            leaderboard_query,
            (session_id, user_id, seed, 'default', score)
        )

        # Calculate rank
        rank = self._calculate_rank(seed, score)

        # Format time delta
        delta_str = self._format_time_delta(time_delta)

        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "entry_id": str(leaderboard_result['entry_id']),
                "rank": rank,
                "score": score,
                "hash_status": "duplicate",
                "message": f"Strategy already discovered {delta_str} ago by another player",
                "duplicate_count": hash_record['duplicate_count'] + 1,
                "first_discovered_by": "Anonymous",  # Privacy - don't reveal who
                "first_discovered_at": first_timestamp.isoformat()
            }
        }

    def _calculate_rank(self, seed: str, score: int) -> int:
        """Calculate rank for given seed and score."""
        rank_query = """
            SELECT COUNT(*) + 1 as rank
            FROM leaderboard_entries
            WHERE seed = %s AND score > %s
        """

        rank_result = self.db_manager.execute_query(
            rank_query,
            (seed, score)
        )

        return rank_result[0]['rank'] if rank_result else 999

    @staticmethod
    def _format_time_delta(seconds: int) -> str:
        """Format time delta as human-readable string."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            return f"{seconds // 60} minutes"
        elif seconds < 86400:
            return f"{seconds // 3600} hours"
        else:
            return f"{seconds // 86400} days"
