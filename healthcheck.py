import http.server
import socketserver
import threading
import os

PORT = int(os.environ.get('PORT', 8080))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'OK')
        
    def log_message(self, format, *args):
        # Отключаем логирование для уменьшения вывода
        return

def start_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving healthcheck at port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Этот файл может использоваться как основной, если необходимо запустить только healthcheck
    import time
    while True:
        time.sleep(60) 