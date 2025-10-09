#!/usr/bin/env python3
"""
P(Doom)1 Website API Endpoints for Game Integration

This script provides mock API endpoints that will eventually be replaced
by real data service integration. It serves leaderboard data, game stats,
and other integration endpoints.

Usage:
    python scripts/api-server.py                    # Start development API server
    python scripts/api-server.py --port 8080        # Custom port
    python scripts/api-server.py --production       # Production mode
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket


class GameIntegrationAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for game integration API endpoints."""
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.data_dir = Path(__file__).parent.parent / "public" / "data"
        self.leaderboard_file = Path(__file__).parent.parent / "public" / "leaderboard" / "data" / "leaderboard.json"
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for API endpoints."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        # CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        try:
            if path == '/api/leaderboards/current':
                self._handle_current_leaderboard(query_params)
            elif path.startswith('/api/leaderboards/seed/'):
                seed = path.split('/')[-1]
                self._handle_seed_leaderboard(seed, query_params)
            elif path == '/api/stats':
                self._handle_game_stats(query_params)
            elif path == '/api/status':
                self._handle_integration_status()
            elif path == '/api/health':
                self._handle_health_check()
            elif path == '/api/league/current':
                self._handle_current_league(query_params)
            elif path == '/api/league/status':
                self._handle_league_status()
            elif path == '/api/league/standings':
                self._handle_league_standings(query_params)
            else:
                self._send_404()
                
        except Exception as e:
            self._send_error(500, f"Internal server error: {str(e)}")
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests for score submission."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        try:
            if path == '/api/scores/submit':
                self._handle_score_submission()
            else:
                self._send_404()
        except Exception as e:
            self._send_error(500, f"Internal server error: {str(e)}")
    
    def _handle_score_submission(self):
        """Handle score submission from game clients."""
        try:
            # Read request data
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "No data provided")
                return
                
            post_data = self.rfile.read(content_length)
            score_data = json.loads(post_data.decode('utf-8'))
            
            # Validate submission
            if self._validate_score_submission(score_data):
                # Add to leaderboard (for now, just log it)
                rank = self._add_score_to_leaderboard(score_data)
                
                # Send success response
                response = {
                    "status": "success", 
                    "rank": rank,
                    "message": "Score submitted successfully",
                    "timestamp": datetime.now().isoformat()
                }
                self._send_json_response(200, response)
            else:
                self._send_error(400, "Invalid score submission")
                
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON data")
        except Exception as e:
            self._send_error(500, f"Score submission error: {str(e)}")
    
    def _validate_score_submission(self, score_data: Dict[str, Any]) -> bool:
        """Validate score submission data."""
        required_fields = [
            'player_uuid', 'player_name', 'seed', 'score', 
            'verification_hash', 'timestamp'
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in score_data:
                return False
        
        # Basic validation
        if not isinstance(score_data['score'], int) or score_data['score'] < 0:
            return False
            
        if len(score_data['player_name']) > 100:  # Reasonable name length
            return False
            
        return True
    
    def _add_score_to_leaderboard(self, score_data: Dict[str, Any]) -> int:
        """Add submitted score to leaderboard and return rank."""
        try:
            # Load current leaderboard
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                leaderboard_data = json.load(f)
            
            # Create new entry in website format
            new_entry = {
                "score": score_data['score'],
                "player_name": score_data['player_name'],
                "date": score_data['timestamp'],
                "level_reached": score_data['score'],
                "game_mode": score_data.get('game_mode', 'Bootstrap_v0.4.1'),
                "duration_seconds": score_data.get('duration_seconds', 0.0),
                "entry_uuid": score_data.get('entry_uuid', score_data['player_uuid']),
                "final_doom": score_data.get('final_metrics', {}).get('final_doom', 25.0),
                "final_money": score_data.get('final_metrics', {}).get('final_money', 100000),
                "final_staff": score_data.get('final_metrics', {}).get('final_staff', 5),
                "final_reputation": score_data.get('final_metrics', {}).get('final_reputation', 50.0),
                "final_compute": score_data.get('final_metrics', {}).get('final_compute', 10000),
                "research_papers_published": score_data.get('final_metrics', {}).get('research_papers_published', 0),
                "technical_debt_accumulated": score_data.get('final_metrics', {}).get('technical_debt_accumulated', 0)
            }
            
            # Add to entries
            leaderboard_data['entries'].append(new_entry)
            
            # Re-sort by score (highest first)
            def get_score(entry: Dict[str, Any]) -> int:
                return entry['score']
            
            leaderboard_data['entries'].sort(key=get_score, reverse=True)
            
            # Update metadata
            leaderboard_data['meta']['generated'] = datetime.now().isoformat() + "Z"
            leaderboard_data['meta']['total_players'] = len(set(
                entry['player_name'] for entry in leaderboard_data['entries']
            ))
            
            # Find rank of submitted score
            rank = None
            for i, entry in enumerate(leaderboard_data['entries'], 1):
                if entry['entry_uuid'] == new_entry['entry_uuid']:
                    rank = i
                    break
            
            # Save updated leaderboard
            with open(self.leaderboard_file, 'w', encoding='utf-8') as f:
                json.dump(leaderboard_data, f, indent=2, ensure_ascii=False)
            
            return rank or len(leaderboard_data['entries'])
            
        except Exception as e:
            print(f"Error adding score to leaderboard: {e}")
            return 999  # Default rank on error
    
    def _handle_current_leaderboard(self, query_params: Dict[str, Any]):
        """Handle /api/leaderboards/current endpoint."""
        try:
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                leaderboard_data = json.load(f)
            
            # Apply limit if specified
            limit = int(query_params.get('limit', [10])[0])
            entries = leaderboard_data['entries'][:limit]
            
            response = {
                "status": "success",
                "data": {
                    "meta": leaderboard_data['meta'],
                    "seed": leaderboard_data['seed'],
                    "economic_model": leaderboard_data['economic_model'],
                    "entries": entries,
                    "api_info": {
                        "endpoint": "/api/leaderboards/current",
                        "requested_limit": limit,
                        "returned_count": len(entries),
                        "total_available": len(leaderboard_data['entries'])
                    }
                },
                "timestamp": datetime.now().isoformat() + "Z"
            }
            
            self._send_json_response(200, response)
            
        except FileNotFoundError:
            self._send_error(404, "Leaderboard data not found")
        except Exception as e:
            self._send_error(500, f"Failed to load leaderboard: {str(e)}")
    
    def _handle_seed_leaderboard(self, seed: str, query_params: Dict[str, Any]):
        """Handle /api/leaderboards/seed/{seed} endpoint."""
        try:
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                leaderboard_data = json.load(f)
            
            # For now, we only have one seed's data, so we'll return it regardless
            # In real implementation, this would filter by actual seed
            current_seed = leaderboard_data.get('seed', 'unknown')
            
            if seed != current_seed and seed != 'all':
                # Return empty results for non-matching seeds
                response = {
                    "status": "success",
                    "data": {
                        "meta": {
                            "generated": datetime.now().isoformat() + "Z",
                            "game_version": leaderboard_data['meta']['game_version'],
                            "total_seeds": 0,
                            "total_players": 0
                        },
                        "seed": seed,
                        "economic_model": "Bootstrap_v0.4.1",
                        "entries": [],
                        "api_info": {
                            "endpoint": f"/api/leaderboards/seed/{seed}",
                            "message": f"No data available for seed '{seed}'"
                        }
                    },
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            else:
                # Return the available data
                limit = int(query_params.get('limit', [50])[0])
                entries = leaderboard_data['entries'][:limit]
                
                response = {
                    "status": "success",
                    "data": {
                        "meta": leaderboard_data['meta'],
                        "seed": current_seed,
                        "economic_model": leaderboard_data['economic_model'],
                        "entries": entries,
                        "api_info": {
                            "endpoint": f"/api/leaderboards/seed/{seed}",
                            "requested_seed": seed,
                            "actual_seed": current_seed,
                            "returned_count": len(entries)
                        }
                    },
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            
            self._send_json_response(200, response)
            
        except Exception as e:
            self._send_error(500, f"Failed to load seed leaderboard: {str(e)}")
    
    def _handle_game_stats(self, query_params: Dict[str, Any]):
        """Handle /api/stats endpoint for aggregated game statistics."""
        try:
            # Load current leaderboard for stats
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                leaderboard_data = json.load(f)
            
            entries = leaderboard_data['entries']
            
            # Calculate aggregated statistics
            scores = [entry['score'] for entry in entries]
            doom_values = [entry['final_doom'] for entry in entries]
            
            stats = {
                "game_statistics": {
                    "total_players": len(set(entry['player_name'] for entry in entries)),
                    "total_games": len(entries),
                    "highest_score": max(scores) if scores else 0,
                    "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
                    "average_doom": round(sum(doom_values) / len(doom_values), 1) if doom_values else 0,
                    "survival_rate": len([s for s in scores if s > 50]) / len(scores) if scores else 0
                },
                "leaderboard_info": {
                    "current_seed": leaderboard_data.get('seed'),
                    "economic_model": leaderboard_data.get('economic_model'),
                    "last_updated": leaderboard_data['meta']['generated']
                },
                "api_info": {
                    "endpoint": "/api/stats",
                    "calculation_time": datetime.now().isoformat() + "Z",
                    "data_source": "bridge"
                }
            }
            
            response = {
                "status": "success",
                "data": stats,
                "timestamp": datetime.now().isoformat() + "Z"
            }
            
            self._send_json_response(200, response)
            
        except Exception as e:
            self._send_error(500, f"Failed to calculate stats: {str(e)}")
    
    def _handle_integration_status(self):
        """Handle /api/status endpoint for integration status."""
        try:
            # Check if various data files exist
            version_file = self.data_dir / "version.json"
            
            integration_status = {
                "integration_ready": True,
                "services": {
                    "leaderboard_bridge": {
                        "status": "active",
                        "data_available": self.leaderboard_file.exists(),
                        "last_update": None
                    },
                    "game_stats": {
                        "status": "active",
                        "calculation_ready": True
                    },
                    "version_sync": {
                        "status": "active" if version_file.exists() else "pending",
                        "file_exists": version_file.exists()
                    }
                },
                "next_steps": [
                    "Connect to real game leaderboard export",
                    "Implement real-time data sync",
                    "Add authentication for private APIs"
                ],
                "development_mode": True,
                "api_endpoints": [
                    "/api/leaderboards/current",
                    "/api/leaderboards/seed/{seed}",
                    "/api/stats",
                    "/api/status",
                    "/api/health"
                ]
            }
            
            if self.leaderboard_file.exists():
                stat = self.leaderboard_file.stat()
                integration_status["services"]["leaderboard_bridge"]["last_update"] = \
                    datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z"
            
            response = {
                "status": "success",
                "data": integration_status,
                "timestamp": datetime.now().isoformat() + "Z"
            }
            
            self._send_json_response(200, response)
            
        except Exception as e:
            self._send_error(500, f"Failed to get status: {str(e)}")
    
    def _handle_health_check(self):
        """Handle /api/health endpoint for service health."""
        health_status = {
            "status": "healthy",
            "services": {
                "api_server": "running",
                "leaderboard_data": "available" if self.leaderboard_file.exists() else "unavailable",
                "file_system": "accessible"
            },
            "uptime": "active",
            "version": "bridge-v1.0.0"
        }
        
        response = {
            "status": "success",
            "data": health_status,
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        self._send_json_response(200, response)
    
    def _handle_current_league(self, query_params: Dict[str, Any]):
        """Handle /api/league/current endpoint for weekly league data."""
        try:
            # Load current weekly league data
            weekly_file = Path(__file__).parent.parent / "public" / "leaderboard" / "data" / "weekly" / "current.json"
            
            if not weekly_file.exists():
                # Fall back to main leaderboard data if no weekly league is active
                self._handle_current_leaderboard(query_params)
                return
            
            with open(weekly_file, 'r', encoding='utf-8') as f:
                league_data = json.load(f)
            
            # Apply limit if specified
            limit = int(query_params.get('limit', [10])[0])
            entries = league_data.get('entries', [])[:limit]
            
            response = {
                "status": "success",
                "data": {
                    "meta": league_data.get('meta', {}),
                    "week_info": league_data.get('week_info', {}),
                    "seed": league_data.get('seed', ''),
                    "economic_model": league_data.get('economic_model', 'Bootstrap_v0.4.1'),
                    "entries": entries,
                    "statistics": league_data.get('statistics', {}),
                    "api_info": {
                        "endpoint": "/api/league/current",
                        "requested_limit": limit,
                        "returned_count": len(entries),
                        "total_available": len(league_data.get('entries', []))
                    }
                },
                "timestamp": datetime.now().isoformat() + "Z"
            }
            
            self._send_json_response(200, response)
            
        except Exception as e:
            self._send_error(500, f"Failed to load current league: {str(e)}")
    
    def _handle_league_status(self) -> None:
        """Handle /api/league/status endpoint for weekly league status."""
        try:
            # Try to import and use weekly league manager
            from pathlib import Path
            import sys
            
            # Add scripts directory to path for import
            scripts_dir = Path(__file__).parent
            sys.path.insert(0, str(scripts_dir))
            
            try:
                # Dynamic import to avoid linting issues
                import importlib
                weekly_league_module = importlib.import_module('weekly-league-manager')
                WeeklyLeagueManager = getattr(weekly_league_module, 'WeeklyLeagueManager')
                
                manager = WeeklyLeagueManager()
                status = manager.get_league_status()
                
                response: Dict[str, Any] = {
                    "status": "success",
                    "data": status,
                    "timestamp": datetime.now().isoformat() + "Z"
                }
                
                self._send_json_response(200, response)
                
            except (ImportError, AttributeError):
                # Fall back to basic status if weekly league manager not available
                basic_status: Dict[str, Any] = {
                    "league_active": False,
                    "message": "Weekly league manager not available",
                    "current_week": self._get_basic_week_info()
                }
                
                response = {
                    "status": "success", 
                    "data": basic_status,
                    "timestamp": datetime.now().isoformat() + "Z"
                }
                
                self._send_json_response(200, response)
                
        except Exception as e:
            self._send_error(500, f"Failed to get league status: {str(e)}")
    
    def _handle_league_standings(self, query_params: Dict[str, Any]) -> None:
        """Handle /api/league/standings endpoint."""
        try:
            # Try to import weekly league manager with dynamic import
            import importlib
            
            try:
                # Dynamic import to avoid linting issues
                weekly_league_module = importlib.import_module('weekly-league-manager')
                WeeklyLeagueManager = getattr(weekly_league_module, 'WeeklyLeagueManager')
                
                manager = WeeklyLeagueManager()
                standings = manager.get_league_standings()
                
                if not standings:
                    self._send_error(404, "No active league standings available")
                    return
                
                # Apply limit if specified
                limit = int(query_params.get('limit', [50])[0])
                if 'top_10' in standings:
                    standings['top_entries'] = standings['top_10'][:limit]
                
                response: Dict[str, Any] = {
                    "status": "success",
                    "data": standings,
                    "timestamp": datetime.now().isoformat() + "Z"
                }
                
                self._send_json_response(200, response)
                
            except (ImportError, AttributeError):
                self._send_error(500, "Weekly league manager not available")
                
        except Exception as e:
            self._send_error(500, f"Failed to get league standings: {str(e)}")
    
    def _get_basic_week_info(self) -> Dict[str, Any]:
        """Get basic week information when weekly league manager is not available."""
        now = datetime.now()
        year, week, _ = now.isocalendar()
        
        return {
            "week_id": f"{year}_W{week:02d}",
            "year": year,
            "week_number": week,
            "basic_info": True
        }
    
    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send a JSON response with proper headers."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        json_data = json.dumps(data, indent=2, ensure_ascii=False)
        self.wfile.write(json_data.encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str) -> None:
        """Send an error response."""
        error_response: Dict[str, Any] = {
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
    
    def log_message(self, format: str, *args: Any) -> None:
        """Custom log message format."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")


class GameIntegrationAPIServer:
    """Development API server for game integration endpoints."""
    
    def __init__(self, port: int = 8080, host: str = "localhost"):
        self.port = port
        self.host = host
        self.server = None
    
    def start(self):
        """Start the API server."""
        try:
            self.server = HTTPServer((self.host, self.port), GameIntegrationAPIHandler)
            print(f"STARTING: Game Integration API Server starting on http://{self.host}:{self.port}")
            print(f"ENDPOINTS: Available endpoints:")
            print(f"   GET /api/leaderboards/current?limit=10")
            print(f"   GET /api/leaderboards/seed/{{seed}}?limit=50")
            print(f"   GET /api/stats")
            print(f"   GET /api/status")
            print(f"   GET /api/health")
            print(f"   GET /api/league/current?limit=10")
            print(f"   GET /api/league/status")
            print(f"   GET /api/league/standings?limit=50")
            print(f"STOP: Press Ctrl+C to stop the server")
            print()
            
            self.server.serve_forever()
            
        except KeyboardInterrupt:
            print("\nSTOP: Server stopped by user")
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"❌ Port {self.port} is already in use. Try a different port with --port")
            else:
                print(f"❌ Failed to start server: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            if self.server:
                self.server.server_close()
    
    def test_endpoints(self):
        """Test that all endpoints are working correctly."""
        import urllib.request
        import urllib.error
        
        base_url = f"http://{self.host}:{self.port}"
        endpoints = [
            "/api/health",
            "/api/status", 
            "/api/stats",
            "/api/leaderboards/current?limit=5",
            "/api/leaderboards/seed/demo-competitive-seed"
        ]
        
        print(f"🧪 Testing API endpoints on {base_url}")
        
        for endpoint in endpoints:
            try:
                url = base_url + endpoint
                with urllib.request.urlopen(url, timeout=5) as response:
                    if response.status == 200:
                        print(f"✅ {endpoint} - OK")
                    else:
                        print(f"❌ {endpoint} - Status {response.status}")
            except urllib.error.URLError as e:
                print(f"❌ {endpoint} - Connection failed: {e}")
            except Exception as e:
                print(f"❌ {endpoint} - Error: {e}")


def find_free_port(start_port: int = 8080) -> int:
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free ports found starting from {start_port}")


def main():
    """CLI interface for the API server."""
    parser = argparse.ArgumentParser(description="p(Doom)1 Game Integration API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run server on")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind to")
    parser.add_argument("--find-port", action="store_true", help="Automatically find a free port")
    parser.add_argument("--test", action="store_true", help="Test API endpoints")
    
    args = parser.parse_args()
    
    if args.find_port:
        args.port = find_free_port(args.port)
        print(f"🔍 Using free port: {args.port}")
    
    server = GameIntegrationAPIServer(port=args.port, host=args.host)
    
    if args.test:
        print("🧪 API endpoint testing mode")
        # Note: For testing, you'd need the server running in another process
        print("ℹ️  Start the server in another terminal first, then run with --test")
        server.test_endpoints()
    else:
        server.start()


if __name__ == "__main__":
    main()