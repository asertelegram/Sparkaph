import http.server
import socketserver
import os
import logging
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get port from environment with a fallback to 8080
PORT = int(os.environ.get('PORT', 8080))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'OK')
        
    def log_message(self, format, *args):
        # Disable request logging to reduce output
        return

# Функция запуска healthcheck сервера
def run_healthcheck_server():
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            logger.info(f"Serving healthcheck at port {PORT}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Ошибка healthcheck сервера: {e}")

# Если запускается напрямую, а не импортируется
if __name__ == "__main__":
    run_healthcheck_server() 