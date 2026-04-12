"""
Phoenix Core Memory Integration for live-monitor

This script provides a Python HTTP server that:
1. Exposes memory system as HTTP endpoints
2. Can be called from TypeScript ai-engine.ts
3. Stores AI analysis results to memory

Endpoints:
  GET  /memory/context - Get memory context for system prompt
  POST /memory/store    - Store AI analysis result
  POST /memory/search   - Search past analyses

Usage:
  python3 memory_server.py
"""

import sys
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from memory_manager import MemoryManager

# Global memory manager instance
MEMORY_MANAGER = None


class MemoryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global MEMORY_MANAGER

        parsed = urlparse(self.path)

        if parsed.path == '/memory/context':
            # Return memory context for system prompt
            context = MEMORY_MANAGER.build_memory_context() if MEMORY_MANAGER else ""

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "success": True,
                "context": context,
                "timestamp": datetime.now().isoformat()
            })
            self.wfile.write(response.encode('utf-8'))

        elif parsed.path == '/memory/status':
            # Return memory server status with learner info
            learner_status = MEMORY_MANAGER.get_learner_status() if MEMORY_MANAGER else {}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "success": True,
                "status": "running",
                "session_id": MEMORY_MANAGER._session_id if MEMORY_MANAGER else None,
                "learner": learner_status
            })
            self.wfile.write(response.encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global MEMORY_MANAGER

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"success": False, "error": "Invalid JSON"})
            self.wfile.write(response.encode('utf-8'))
            return

        parsed = urlparse(self.path)

        if parsed.path == '/memory/init':
            # Initialize/reinitialize memory
            session_id = data.get('session_id', f"live-monitor-{datetime.now().strftime('%Y%m%d-%H%M%S')}")

            if MEMORY_MANAGER:
                MEMORY_MANAGER.shutdown()

            MEMORY_MANAGER = MemoryManager()
            MEMORY_MANAGER.load(session_id=session_id)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "success": True,
                "session_id": session_id,
                "context": MEMORY_MANAGER.build_memory_context()
            })
            self.wfile.write(response.encode('utf-8'))

        elif parsed.path == '/memory/store':
            # Store AI analysis result
            if not MEMORY_MANAGER:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"success": False, "error": "Memory not initialized"})
                self.wfile.write(response.encode('utf-8'))
                return

            user_content = data.get('user_content', 'AI analysis request')
            assistant_content = data.get('assistant_content', 'AI suggestion')
            tool_iterations = data.get('tool_iterations', 1)

            MEMORY_MANAGER.sync_turn(
                user_content=user_content,
                assistant_content=assistant_content,
                tool_iterations=tool_iterations
            )

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "success": True,
                "message": "Stored in memory"
            })
            self.wfile.write(response.encode('utf-8'))

        elif parsed.path == '/memory/search':
            # Search past analyses
            if not MEMORY_MANAGER:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"success": False, "error": "Memory not initialized"})
                self.wfile.write(response.encode('utf-8'))
                return

            query = data.get('query', '')
            limit = data.get('limit', 5)

            results = MEMORY_MANAGER.search_sessions(query, limit)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "success": True,
                "count": len(results),
                "results": results
            }, default=str)
            self.wfile.write(response.encode('utf-8'))

        elif parsed.path == '/memory/add':
            # Add memory entry
            if not MEMORY_MANAGER:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"success": False, "error": "Memory not initialized"})
                self.wfile.write(response.encode('utf-8'))
                return

            action = data.get('action', 'add')
            target = data.get('target', 'memory')
            content = data.get('content', '')

            result = MEMORY_MANAGER.handle_tool_call("memory", {
                "action": action,
                "target": target,
                "content": content
            })

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(result.encode('utf-8'))

        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"success": False, "error": "Unknown endpoint"})
            self.wfile.write(response.encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def run_server(host='0.0.0.0', port=8765):
    global MEMORY_MANAGER

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('/tmp/memory_server.log'),
            logging.StreamHandler()
        ]
    )

    # Initialize memory manager
    MEMORY_MANAGER = MemoryManager()
    MEMORY_MANAGER.load(session_id="live-monitor-server")

    server = HTTPServer((host, port), MemoryHandler)
    print(f"[Memory Server] Running on http://{host}:{port}")
    print(f"[Memory Server] Endpoints:")
    print(f"  GET  /memory/context - Get memory context")
    print(f"  GET  /memory/status  - Get server status")
    print(f"  POST /memory/init    - Initialize session")
    print(f"  POST /memory/store   - Store analysis result")
    print(f"  POST /memory/search  - Search past analyses")
    print(f"  POST /memory/add     - Add memory entry")

    logging.info("Memory server started")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Memory Server] Shutting down...")
        logging.info("Memory server shutting down")
        if MEMORY_MANAGER:
            MEMORY_MANAGER.shutdown()
        server.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Phoenix Core Memory Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8765, help='Port to listen on')

    args = parser.parse_args()
    run_server(args.host, args.port)
