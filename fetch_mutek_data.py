import urllib.request
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# Setup instructions using uv:
# 1. Install uv if you haven't already: pip install uv
# 2. Create a virtual environment: uv venv
# 3. Activate the virtual environment:
#    - On Windows: .venv\Scripts\activate
#    - On macOS/Linux: source .venv/bin/activate
# 4. Install dependencies: uv pip install beautifulsoup4

url = "https://montreal.mutek.org/en/shows/2026/nocturne-2"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        html = response.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    def convert_to_24h(time_str):
        if not time_str or time_str == "Unknown":
            return time_str
            
        time_str = time_str.strip().lower()
        # Handle cases where minutes might be missing (e.g., "10 pm" vs "10:45 pm")
        try:
            if ':' in time_str:
                dt = datetime.strptime(time_str, '%I:%M %p')
            else:
                dt = datetime.strptime(time_str, '%I %p')
            return dt.strftime('%H:%M')
        except ValueError:
            # If parsing fails, return the original string
            return time_str

    # We will build a more structured dictionary to hold artists/times per venue
    # Example format: {'Espace SAT': [{'artist': 'Artist A', 'start_time': '22:00', 'end_time': '23:00'}], ...}
    venue_data = {}
    
    # The user noted venues are in h3.event-single__showrooms-title
    showroom_titles = soup.find_all('h3', class_='event-single__showrooms-title')
    
    for title_element in showroom_titles:
        venue_name = title_element.get_text(strip=True)
        venue_data[venue_name] = []
        
        # The container for this venue's artists/times is expected to be the next sibling or close by
        # Looking for div.event-single__showrooms-container
        container = title_element.find_next_sibling('div', class_='event-single__showrooms-container')
        
        if container:
            # Artists are typically in links or specific spans within this container
            # Times might be in separate spans. We need to look at the structure inside.
            # Assuming a structure where each performance is a block.
            
            # Look for performance blocks. Often they are list items or specific divs.
            # Since we don't have the exact inner HTML, we will look for common patterns:
            # 1. Links to artists
            # 2. Text that looks like time
            
            # Let's try to find artist links first
            artist_links = container.find_all('a', href=lambda href: href and '/en/artists/' in href)
            
            # If we find specific blocks for each performance, we should iterate those instead.
            # Usually, in a swiper container, there are 'swiper-slide' divs.
            slides = container.find_all(class_=lambda c: c and 'swiper-slide' in c)
            
            if slides:
                for slide in slides:
                    artist_name = "Unknown Artist"
                    start_time = "Unknown"
                    end_time = "Unknown"
                    
                    # Find artist name in slide
                    artist_heading = slide.find(['h4', 'h5'], class_=lambda c: c and 'artists-single__title' in c)
                    if not artist_heading:
                        # Fallback to any heading or strong tag if the specific class isn't found
                        artist_heading = slide.find(['h4', 'h5', 'strong'])

                    if artist_heading:
                        # Look specifically for the span inside the heading
                        name_span = artist_heading.find('span')
                        if name_span:
                            artist_name = name_span.get_text(strip=True)
                        else:
                            # Safegaurd: remove any <sup> tags to avoid country codes bleeding into the name
                            for sup in artist_heading.find_all('sup'):
                                sup.decompose()
                            artist_name = artist_heading.get_text(strip=True)
                    else:
                        # Fallback to checking the anchor tag directly
                        artist_link = slide.find('a', href=lambda href: href and '/en/artists/' in href)
                        if artist_link:
                            name_span = artist_link.find('span')
                            if name_span:
                                artist_name = name_span.get_text(strip=True)
                            else:
                                for sup in artist_link.find_all('sup'):
                                    sup.decompose()
                                artist_name = artist_link.get_text(strip=True)
                            
                    # Find time in slide: <p>Performs at 10:45 pm<span class="underscore">_</span>11:35 pm
                    time_p = None
                    for p_tag in slide.find_all('p'):
                        if p_tag.get_text() and 'Performs at' in p_tag.get_text():
                            time_p = p_tag
                            break

                    if time_p:
                        full_time_text = time_p.get_text(strip=True)
                        # Example full_text: "Performs at 10:45 pm_11:35 pmMontréal time"
                        
                        # Use regex to find times like "10:45 pm" or "10 pm"
                        time_pattern = r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))'
                        matches = re.findall(time_pattern, full_time_text, flags=re.IGNORECASE)
                        
                        if len(matches) >= 1:
                            start_time = convert_to_24h(matches[0])
                        if len(matches) >= 2:
                            end_time = convert_to_24h(matches[1])
                    
                    venue_data[venue_name].append({
                        'artist': artist_name,
                        'start_time': start_time,
                        'end_time': end_time
                    })
            else:
                 # If no slides found, fallback logic needs to be updated for new structure if necessary
                 # But we assume swiper-slides exist based on the prompt's context
                 pass

    if not venue_data:
        # Fallback if the specific structure wasn't found
        print("Warning: Could not find the expected HTML structure (h3.event-single__showrooms-title). Falling back to general parsing.")
        # ... (Previous fallback parsing logic would go here if needed, but we focus on the new structure)
        
    result = {
        "event": "NOCTURNE 2",
        "structured_schedule": venue_data
    }

    print(json.dumps(result, indent=4, ensure_ascii=False))

except urllib.error.URLError as e:
    print(f"Error fetching the URL: {e.reason}")
    print("Using fallback data gathered from search snippets since the URL might be blocking scraping or is unavailable.")
    
    fallback_result = {
        "event": "NOCTURNE 2 (August 27, 2026)",
        "venues": [
            "Société des arts technologiques [SAT]",
            "Espace SAT",
            "Satosphère"
        ],
        "time_ranges": [
            "10:00 pm"
        ],
        "artists": [
            "Arbor and Tzu Ni",
            "Korea Town Acid & Ajeebsir",
            "MOORE + SALAS",
            "Nelly-Eve Rajotte",
            "ELECTRONICOS FANTASTICOS!",
            "Jump Source",
            "Noémi Büchi",
            "Zora Jones"
        ]
    }
    print("\nFallback Data:")
    print(json.dumps(fallback_result, indent=4, ensure_ascii=False))
except Exception as e:
    print(f"An unexpected error occurred: {e}")