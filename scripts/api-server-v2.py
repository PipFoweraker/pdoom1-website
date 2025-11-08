#!/usr/bin/env python3
"""
P(Doom)1 Production API Server with PostgreSQL Support

This is the production-ready API server that replaces the bridge implementation.
It connects to PostgreSQL for persistent storage and implements JWT authentication.

Usage:
    python scripts/api-server-v2.py                    # Start with .env config
    python scripts/api-server-v2.py --port 8080        # Custom port
    python scripts/api-server-v2.py --production       # Production mode

Environment Variables Required:
    DATABASE_URL    - PostgreSQL connection string
    JWT_SECRET      - Secret key for JWT token signing
    CORS_ORIGINS    - Comma-separated allowed origins (production)
    PORT            - Server port (optional, default 8080)
"""

import json
import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket
import hashlib
import uuid
import re

# Check for required dependencies
try:
    import psycopg2
    from psycopg2 import pool, sql
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 is required. Install with: pip install psycopg2-binary")
    sys.exit(1)

try:
    import jwt
except ImportError:
    print("ERROR: PyJWT is required. Install with: pip install PyJWT")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("WARNING: python-dotenv not installed. Environment variables must be set manually.")


# Production configuration
PRODUCTION_CORS_ORIGINS = [
    "https://pdoom1.com",
    "https://www.pdoom1.com"
]

# Database connection pool (global)
db_pool: Optional[pool.SimpleConnectionPool] = None


class DatabaseManager:
    """Manages PostgreSQL database connections and queries."""

    def __init__(self, database_url: str):
        """Initialize database connection pool."""
        self.database_url = database_url
        self.pool = None

    def initialize_pool(self, min_conn: int = 1, max_conn: int = 10):
        """Create connection pool."""
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                min_conn,
                max_conn,
                self.database_url
            )
            print(f"✅ Database pool initialized ({min_conn}-{max_conn} connections)")
        except Exception as e:
            print(f"❌ Failed to create database pool: {e}")
            raise

    def get_connection(self):
        """Get a connection from the pool."""
        if self.pool is None:
            raise RuntimeError("Database pool not initialized")
        return self.pool.getconn()

    def return_connection(self, conn):
        """Return a connection to the pool."""
        if self.pool is not None:
            self.pool.putconn(conn)

    def close_all_connections(self):
        """Close all connections in the pool."""
        if self.pool is not None:
            self.pool.closeall()
            print("✅ All database connections closed")

    def execute_query(self, query: str, params: Tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
        """Execute a query and return results."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)

                if fetch:
                    result = cur.fetchall()
                    return [dict(row) for row in result]
                else:
                    conn.commit()
                    return None

        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.return_connection(conn)

    def execute_insert(self, query: str, params: Tuple = None) -> Optional[Dict]:
        """Execute an INSERT and return the inserted row."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                conn.commit()
                return dict(result) if result else None

        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.return_connection(conn)


class JWTManager:
    """Manages JWT token creation and validation."""

    def __init__(self, secret: str):
        """Initialize with JWT secret."""
        self.secret = secret
        self.algorithm = "HS256"

    def create_token(self, user_id: str, pseudonym: str, permissions: List[str] = None) -> str:
        """Create a JWT token for a user."""
        if permissions is None:
            permissions = ['leaderboard_submit', 'analytics_opt_in']

        payload = {
            'sub': user_id,
            'pseudonym': pseudonym,
            'permissions': permissions,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(days=1)
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


class ProductionAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for production API with PostgreSQL backend."""

    # Class-level configuration (set by server)
    is_production = False
    cors_origins: List[str] = ["*"]
    db_manager: Optional[DatabaseManager] = None
    jwt_manager: Optional[JWTManager] = None

    def _sanitize_origin(self, origin: str) -> str:
        """Sanitize origin header to prevent header injection attacks."""
        if not origin:
            return ''

        # Remove any newline characters that could enable header injection
        sanitized = origin.replace('\r', '').replace('\n', '')

        # Validate it looks like a valid origin (scheme://host[:port])
        if not (sanitized.startswith('http://') or sanitized.startswith('https://')):
            return ''

        return sanitized

    def _set_cors_headers(self):
        """Set CORS headers based on environment."""
        origin = self.headers.get('Origin', '')

        if self.is_production:
            sanitized_origin = self._sanitize_origin(origin)

            if sanitized_origin and (sanitized_origin in self.cors_origins or '*' in self.cors_origins):
                self.send_header('Access-Control-Allow-Origin', sanitized_origin)
            else:
                self.send_header('Access-Control-Allow-Origin', self.cors_origins[0] if self.cors_origins else 'https://pdoom1.com')
        else:
            self.send_header('Access-Control-Allow-Origin', '*')

        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PATCH, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Game-Version, X-Client-ID')

    def _get_auth_token(self) -> Optional[str]:
        """Extract JWT token from Authorization header."""
        auth_header = self.headers.get('Authorization', '')

        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix

        return None

    def _verify_request(self) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Verify request authentication. Returns (success, user_data, error_message)."""
        token = self._get_auth_token()

        if not token:
            return (False, None, "No authentication token provided")

        user_data = self.jwt_manager.verify_token(token)

        if not user_data:
            return (False, None, "Invalid or expired token")

        return (True, user_data, None)

    def do_GET(self):
        """Handle GET requests for API endpoints."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        self._set_cors_headers()

        try:
            # Public endpoints (no auth required)
            if path == '/api/health':
                self._handle_health_check()
            elif path == '/api/status':
                self._handle_integration_status()

            # Endpoints that require authentication
            elif path == '/api/leaderboards/current':
                self._handle_current_leaderboard(query_params)
            elif path.startswith('/api/leaderboards/seed/'):
                seed = path.split('/')[-1]
                self._handle_seed_leaderboard(seed, query_params)
            elif path == '/api/stats':
                self._handle_game_stats(query_params)
            elif path == '/api/league/current':
                self._handle_current_league(query_params)
            elif path == '/api/league/status':
                self._handle_league_status()
            elif path == '/api/league/standings':
                self._handle_league_standings(query_params)
            elif path == '/api/users/profile':
                success, user_data, error = self._verify_request()
                if not success:
                    self._send_error(401, error)
                    return
                self._handle_get_profile(user_data)
            else:
                self._send_404()

        except Exception as e:
            print(f"ERROR in GET {path}: {e}")
            self._send_error(500, f"Internal server error: {str(e)}")

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        self._set_cors_headers()

        try:
            # Public endpoints
            if path == '/api/auth/register':
                self._handle_register()
            elif path == '/api/auth/login':
                self._handle_login()

            # Protected endpoints
            elif path == '/api/scores/submit':
                success, user_data, error = self._verify_request()
                if not success:
                    self._send_error(401, error)
                    return
                self._handle_score_submission(user_data)
            else:
                self._send_404()

        except Exception as e:
            print(f"ERROR in POST {path}: {e}")
            self._send_error(500, f"Internal server error: {str(e)}")

    def _handle_register(self):
        """Handle user registration."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "No data provided")
                return

            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            pseudonym = data.get('pseudonym', '').strip()
            email = data.get('email', '').strip()

            # Validate pseudonym
            if not pseudonym or len(pseudonym) < 3 or len(pseudonym) > 50:
                self._send_error(400, "Pseudonym must be 3-50 characters")
                return

            # Only allow alphanumeric, underscore, hyphen
            if not re.match(r'^[a-zA-Z0-9_-]+$', pseudonym):
                self._send_error(400, "Pseudonym can only contain letters, numbers, underscore, and hyphen")
                return

            # Hash email for privacy (optional field)
            email_hash = None
            if email:
                email_hash = hashlib.sha256(email.encode()).hexdigest()

            # Check if pseudonym exists
            existing = self.db_manager.execute_query(
                "SELECT user_id FROM users WHERE pseudonym = %s",
                (pseudonym,)
            )

            if existing:
                self._send_error(409, "Pseudonym already taken")
                return

            # Create user
            query = """
                INSERT INTO users (pseudonym, email_hash, privacy_settings, opt_in_leaderboard, opt_in_analytics)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING user_id, pseudonym, created_at
            """

            privacy_settings = data.get('privacy_settings', {})
            opt_in_leaderboard = data.get('opt_in_leaderboard', False)
            opt_in_analytics = data.get('opt_in_analytics', False)

            result = self.db_manager.execute_insert(
                query,
                (pseudonym, email_hash, json.dumps(privacy_settings), opt_in_leaderboard, opt_in_analytics)
            )

            if not result:
                self._send_error(500, "Failed to create user")
                return

            # Create JWT token
            user_id = str(result['user_id'])
            token = self.jwt_manager.create_token(user_id, pseudonym)

            response = {
                "status": "success",
                "data": {
                    "user_id": user_id,
                    "pseudonym": pseudonym,
                    "token": token,
                    "created_at": result['created_at'].isoformat()
                },
                "message": "User registered successfully",
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(201, response)

        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON data")
        except Exception as e:
            print(f"Registration error: {e}")
            self._send_error(500, f"Registration failed: {str(e)}")

    def _handle_login(self):
        """Handle user login."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            pseudonym = data.get('pseudonym', '').strip()

            if not pseudonym:
                self._send_error(400, "Pseudonym required")
                return

            # Find user
            query = """
                SELECT user_id, pseudonym, created_at, last_active
                FROM users
                WHERE pseudonym = %s
            """

            result = self.db_manager.execute_query(query, (pseudonym,))

            if not result:
                self._send_error(404, "User not found")
                return

            user = result[0]
            user_id = str(user['user_id'])

            # Update last_active
            self.db_manager.execute_query(
                "UPDATE users SET last_active = NOW() WHERE user_id = %s",
                (user_id,),
                fetch=False
            )

            # Create JWT token
            token = self.jwt_manager.create_token(user_id, pseudonym)

            response = {
                "status": "success",
                "data": {
                    "user_id": user_id,
                    "pseudonym": pseudonym,
                    "token": token
                },
                "message": "Login successful",
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(200, response)

        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON data")
        except Exception as e:
            print(f"Login error: {e}")
            self._send_error(500, f"Login failed: {str(e)}")

    def _handle_score_submission(self, user_data: Dict):
        """Handle score submission from authenticated game clients."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "No data provided")
                return

            post_data = self.rfile.read(content_length)
            score_data = json.loads(post_data.decode('utf-8'))

            # Validate submission
            if not self._validate_score_submission(score_data):
                self._send_error(400, "Invalid score submission")
                return

            user_id = user_data['sub']

            # Create game session
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
                    score_data.get('final_turn', 0),
                    json.dumps(score_data.get('final_metrics', {})),
                    score_data['verification_hash'],
                    score_data.get('duration_seconds', 0.0)
                )
            )

            session_id = str(session_result['session_id'])

            # Create leaderboard entry
            leaderboard_query = """
                INSERT INTO leaderboard_entries (
                    session_id, user_id, seed, config_hash, score, verified
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING entry_id
            """

            leaderboard_result = self.db_manager.execute_insert(
                leaderboard_query,
                (
                    session_id,
                    user_id,
                    score_data['seed'],
                    score_data.get('config_hash', 'default'),
                    score_data['score'],
                    False  # Will be verified later
                )
            )

            # Calculate rank
            rank_query = """
                SELECT COUNT(*) + 1 as rank
                FROM leaderboard_entries
                WHERE seed = %s AND score > %s
            """

            rank_result = self.db_manager.execute_query(
                rank_query,
                (score_data['seed'], score_data['score'])
            )

            rank = rank_result[0]['rank'] if rank_result else 999

            response = {
                "status": "success",
                "data": {
                    "session_id": session_id,
                    "entry_id": str(leaderboard_result['entry_id']),
                    "rank": rank,
                    "score": score_data['score']
                },
                "message": "Score submitted successfully",
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(200, response)

        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON data")
        except Exception as e:
            print(f"Score submission error: {e}")
            self._send_error(500, f"Score submission failed: {str(e)}")

    def _validate_score_submission(self, score_data: Dict[str, Any]) -> bool:
        """Validate score submission data."""
        required_fields = ['seed', 'score', 'verification_hash', 'timestamp']

        for field in required_fields:
            if field not in score_data:
                return False

        if not isinstance(score_data['score'], int) or score_data['score'] < 0:
            return False

        return True

    def _handle_current_leaderboard(self, query_params: Dict[str, Any]):
        """Handle /api/leaderboards/current endpoint."""
        try:
            limit = int(query_params.get('limit', [10])[0])

            query = """
                SELECT
                    le.entry_id,
                    u.pseudonym as player_name,
                    le.score,
                    le.submitted_at,
                    gs.duration_seconds,
                    gs.game_metadata,
                    ROW_NUMBER() OVER (ORDER BY le.score DESC) as rank
                FROM leaderboard_entries le
                JOIN users u ON le.user_id = u.user_id
                JOIN game_sessions gs ON le.session_id = gs.session_id
                WHERE u.opt_in_leaderboard = true
                ORDER BY le.score DESC
                LIMIT %s
            """

            entries = self.db_manager.execute_query(query, (limit,))

            # Format entries
            formatted_entries = []
            for entry in entries:
                metadata = entry.get('game_metadata', {})
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                formatted_entries.append({
                    "rank": entry['rank'],
                    "player_name": entry['player_name'],
                    "score": entry['score'],
                    "date": entry['submitted_at'].isoformat(),
                    "duration_seconds": float(entry['duration_seconds'] or 0),
                    "final_doom": metadata.get('final_doom', 25.0),
                    "final_money": metadata.get('final_money', 100000),
                    "final_staff": metadata.get('final_staff', 5),
                    "final_reputation": metadata.get('final_reputation', 50.0)
                })

            response = {
                "status": "success",
                "data": {
                    "entries": formatted_entries,
                    "meta": {
                        "total_returned": len(formatted_entries),
                        "requested_limit": limit,
                        "generated": datetime.now().isoformat() + "Z"
                    }
                },
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(200, response)

        except Exception as e:
            print(f"Leaderboard error: {e}")
            self._send_error(500, f"Failed to load leaderboard: {str(e)}")

    def _handle_seed_leaderboard(self, seed: str, query_params: Dict[str, Any]):
        """Handle /api/leaderboards/seed/{seed} endpoint."""
        try:
            limit = int(query_params.get('limit', [50])[0])

            query = """
                SELECT
                    le.entry_id,
                    u.pseudonym as player_name,
                    le.score,
                    le.submitted_at,
                    gs.duration_seconds,
                    gs.game_metadata,
                    ROW_NUMBER() OVER (ORDER BY le.score DESC) as rank
                FROM leaderboard_entries le
                JOIN users u ON le.user_id = u.user_id
                JOIN game_sessions gs ON le.session_id = gs.session_id
                WHERE le.seed = %s AND u.opt_in_leaderboard = true
                ORDER BY le.score DESC
                LIMIT %s
            """

            entries = self.db_manager.execute_query(query, (seed, limit))

            formatted_entries = []
            for entry in entries:
                metadata = entry.get('game_metadata', {})
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                formatted_entries.append({
                    "rank": entry['rank'],
                    "player_name": entry['player_name'],
                    "score": entry['score'],
                    "date": entry['submitted_at'].isoformat(),
                    "duration_seconds": float(entry['duration_seconds'] or 0),
                    "final_doom": metadata.get('final_doom', 25.0)
                })

            response = {
                "status": "success",
                "data": {
                    "seed": seed,
                    "entries": formatted_entries,
                    "meta": {
                        "total_returned": len(formatted_entries),
                        "requested_limit": limit
                    }
                },
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(200, response)

        except Exception as e:
            print(f"Seed leaderboard error: {e}")
            self._send_error(500, f"Failed to load seed leaderboard: {str(e)}")

    def _handle_game_stats(self, query_params: Dict[str, Any]):
        """Handle /api/stats endpoint for aggregated statistics."""
        try:
            query = """
                SELECT
                    COUNT(DISTINCT le.user_id) as total_players,
                    COUNT(*) as total_games,
                    MAX(le.score) as highest_score,
                    AVG(le.score) as average_score
                FROM leaderboard_entries le
                JOIN users u ON le.user_id = u.user_id
                WHERE u.opt_in_leaderboard = true
            """

            stats = self.db_manager.execute_query(query)

            if stats:
                stats_data = stats[0]
                response = {
                    "status": "success",
                    "data": {
                        "game_statistics": {
                            "total_players": stats_data['total_players'],
                            "total_games": stats_data['total_games'],
                            "highest_score": stats_data['highest_score'] or 0,
                            "average_score": round(float(stats_data['average_score'] or 0), 1)
                        }
                    },
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            else:
                response = {
                    "status": "success",
                    "data": {"game_statistics": {}},
                    "timestamp": datetime.now().isoformat() + "Z"
                }

            self._send_json_response(200, response)

        except Exception as e:
            print(f"Stats error: {e}")
            self._send_error(500, f"Failed to calculate stats: {str(e)}")

    def _handle_integration_status(self):
        """Handle /api/status endpoint."""
        try:
            # Test database connection
            db_status = "connected"
            try:
                self.db_manager.execute_query("SELECT 1")
            except:
                db_status = "disconnected"

            status = {
                "integration_ready": db_status == "connected",
                "services": {
                    "database": {
                        "status": db_status,
                        "type": "PostgreSQL"
                    },
                    "authentication": {
                        "status": "active",
                        "type": "JWT"
                    },
                    "api": {
                        "status": "active",
                        "version": "v2.0.0"
                    }
                },
                "production_mode": self.is_production
            }

            response = {
                "status": "success",
                "data": status,
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(200, response)

        except Exception as e:
            self._send_error(500, f"Failed to get status: {str(e)}")

    def _handle_health_check(self):
        """Handle /api/health endpoint."""
        health = {
            "status": "healthy",
            "services": {
                "api_server": "running",
                "database": "unknown"
            },
            "version": "v2.0.0-production"
        }

        # Test database
        try:
            self.db_manager.execute_query("SELECT 1")
            health["services"]["database"] = "connected"
        except:
            health["services"]["database"] = "disconnected"
            health["status"] = "degraded"

        response = {
            "status": "success",
            "data": health,
            "timestamp": datetime.now().isoformat() + "Z"
        }

        self._send_json_response(200, response)

    def _handle_current_league(self, query_params: Dict[str, Any]):
        """Handle /api/league/current - placeholder for now."""
        self._send_error(501, "Weekly league feature not yet implemented in v2")

    def _handle_league_status(self):
        """Handle /api/league/status - placeholder for now."""
        self._send_error(501, "Weekly league feature not yet implemented in v2")

    def _handle_league_standings(self, query_params: Dict[str, Any]):
        """Handle /api/league/standings - placeholder for now."""
        self._send_error(501, "Weekly league feature not yet implemented in v2")

    def _handle_get_profile(self, user_data: Dict):
        """Handle GET /api/users/profile."""
        try:
            user_id = user_data['sub']

            query = """
                SELECT user_id, pseudonym, created_at, last_active,
                       privacy_settings, opt_in_leaderboard, opt_in_analytics
                FROM users
                WHERE user_id = %s
            """

            result = self.db_manager.execute_query(query, (user_id,))

            if not result:
                self._send_error(404, "User not found")
                return

            user = result[0]
            privacy_settings = user['privacy_settings']
            if isinstance(privacy_settings, str):
                privacy_settings = json.loads(privacy_settings)

            response = {
                "status": "success",
                "data": {
                    "user_id": str(user['user_id']),
                    "pseudonym": user['pseudonym'],
                    "created_at": user['created_at'].isoformat(),
                    "last_active": user['last_active'].isoformat() if user['last_active'] else None,
                    "privacy_settings": privacy_settings,
                    "opt_in_leaderboard": user['opt_in_leaderboard'],
                    "opt_in_analytics": user['opt_in_analytics']
                },
                "timestamp": datetime.now().isoformat() + "Z"
            }

            self._send_json_response(200, response)

        except Exception as e:
            print(f"Profile error: {e}")
            self._send_error(500, f"Failed to get profile: {str(e)}")

    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send a JSON response with proper headers."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()

        json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        self.wfile.write(json_data.encode('utf-8'))

    def _send_error(self, status_code: int, message: str):
        """Send an error response."""
        error_response = {
            "status": "error",
            "error": {
                "code": status_code,
                "message": message
            },
            "timestamp": datetime.now().isoformat() + "Z"
        }
        self._send_json_response(status_code, error_response)

    def _send_404(self):
        """Send a 404 Not Found response."""
        self._send_error(404, f"API endpoint not found: {self.path}")

    def log_message(self, format: str, *args: Any):
        """Custom log message format."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")


class ProductionAPIServer:
    """Production API server with PostgreSQL and JWT authentication."""

    def __init__(self, port: int = 8080, host: str = "localhost", production: bool = False):
        self.port = port
        self.host = host
        self.production = production
        self.server = None
        self.db_manager = None
        self.jwt_manager = None

        # Load configuration from environment
        self._load_config()

        # Initialize database
        self._init_database()

        # Initialize JWT
        self._init_jwt()

        # Configure handler
        ProductionAPIHandler.is_production = production
        ProductionAPIHandler.db_manager = self.db_manager
        ProductionAPIHandler.jwt_manager = self.jwt_manager

        if production:
            cors_env = os.getenv('CORS_ORIGINS', ','.join(PRODUCTION_CORS_ORIGINS))
            ProductionAPIHandler.cors_origins = [o.strip() for o in cors_env.split(',')]
        else:
            ProductionAPIHandler.cors_origins = ["*"]

    def _load_config(self):
        """Load configuration from environment variables."""
        self.database_url = os.getenv('DATABASE_URL')
        self.jwt_secret = os.getenv('JWT_SECRET')

        if not self.database_url:
            print("❌ DATABASE_URL environment variable not set")
            print("   Example: postgresql://user:pass@localhost:5432/pdoom1")
            sys.exit(1)

        if not self.jwt_secret:
            print("❌ JWT_SECRET environment variable not set")
            print("   Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'")
            sys.exit(1)

    def _init_database(self):
        """Initialize database connection pool with retry logic."""
        max_retries = 5
        retry_delay = 2  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                print(f"🔄 Attempting database connection (attempt {attempt}/{max_retries})...")
                self.db_manager = DatabaseManager(self.database_url)
                self.db_manager.initialize_pool(min_conn=2, max_conn=10)

                # Test connection
                self.db_manager.execute_query("SELECT 1")
                print("✅ Database connection successful")
                return

            except Exception as e:
                if attempt < max_retries:
                    print(f"⚠️  Database connection failed (attempt {attempt}/{max_retries}): {e}")
                    print(f"   Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"❌ Database initialization failed after {max_retries} attempts: {e}")
                    sys.exit(1)

    def _init_jwt(self):
        """Initialize JWT manager."""
        try:
            self.jwt_manager = JWTManager(self.jwt_secret)
            print("✅ JWT authentication initialized")
        except Exception as e:
            print(f"❌ JWT initialization failed: {e}")
            sys.exit(1)

    def start(self):
        """Start the API server."""
        try:
            self.server = HTTPServer((self.host, self.port), ProductionAPIHandler)

            mode = "PRODUCTION" if self.production else "DEVELOPMENT"
            print(f"\n{'='*60}")
            print(f"P(Doom)1 Production API Server v2.0.0 ({mode})")
            print(f"{'='*60}")
            print(f"Server: http://{self.host}:{self.port}")
            if self.production:
                print(f"CORS: {', '.join(ProductionAPIHandler.cors_origins)}")
            print(f"\nEndpoints:")
            print(f"  POST /api/auth/register          - Create user account")
            print(f"  POST /api/auth/login             - Authenticate user")
            print(f"  GET  /api/users/profile          - Get user profile (auth)")
            print(f"  POST /api/scores/submit          - Submit score (auth)")
            print(f"  GET  /api/leaderboards/current   - Current leaderboard")
            print(f"  GET  /api/leaderboards/seed/{{seed}} - Seed leaderboard")
            print(f"  GET  /api/stats                  - Game statistics")
            print(f"  GET  /api/status                 - Integration status")
            print(f"  GET  /api/health                 - Health check")
            print(f"\nPress Ctrl+C to stop")
            print(f"{'='*60}\n")

            self.server.serve_forever()

        except KeyboardInterrupt:
            print("\n\n✅ Server stopped by user")
        except OSError as e:
            if e.errno == 48 or 'Address already in use' in str(e):
                print(f"❌ Port {self.port} is already in use")
            else:
                print(f"❌ Failed to start server: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            if self.db_manager:
                self.db_manager.close_all_connections()
            if self.server:
                self.server.server_close()


def main():
    """CLI interface for the production API server."""
    parser = argparse.ArgumentParser(description="P(Doom)1 Production API Server v2.0.0")
    parser.add_argument("--port", type=int, help="Port to run server on")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind to")
    parser.add_argument("--production", action="store_true", help="Run in production mode")

    args = parser.parse_args()

    # Get port from args, environment, or default
    port = args.port or int(os.getenv('PORT', '8080'))

    # In production mode, default to 0.0.0.0
    host = args.host
    if args.production and args.host == "localhost":
        host = "0.0.0.0"

    server = ProductionAPIServer(port=port, host=host, production=args.production)
    server.start()


if __name__ == "__main__":
    main()
