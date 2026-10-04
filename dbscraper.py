import requests
from bs4 import BeautifulSoup

# 1. Ask the user to type the website URL directly in the terminal
url = input("Please enter the website URL: ")

# Add a basic check to ensure the URL starts with http:// or https://
if not url.startswith(("http://", "https://")):
    url = "https://" + url

print(f"\nConnecting to {url}...\n")

try:
    # 2. Fetch the website content
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. Pull all paragraphs (<p> tags) from the page as an example
        paragraphs = soup.find_all('p')
        
        if paragraphs:
            print("--- Content Found ---")
            for p in paragraphs:
                text = p.text.strip()
                if text: # Only print if the paragraph isn't empty
                    print(text)
                    print("-" * 20)
        else:
            print("No paragraph text found on this page. The page might be empty or use a different layout.")
            
    else:
        print(f"Could not open the website. Status code: {response.status_code}")

except Exception as e:
    print(f"An error occurred while trying to connect: {e}")
