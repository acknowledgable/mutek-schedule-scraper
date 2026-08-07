# Setup instructions using uv:
# 1. Install uv if you haven't already: pip install uv
# 2. Create a virtual environment: uv venv
# 3. Activate the virtual environment:
#    - On Windows: .venv\Scripts\activate
#    - On macOS/Linux: source .venv/bin/activate
# 4. Install dependencies: uv pip install beautifulsoup4

import urllib.request
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def scrape_program_links(program_url):
    """Scrapes event page links from the central schedule page."""
    print(f"Scraping schedule for event links...")
    try:
        req = urllib.request.Request(program_url, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            html = response.read()

        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all anchor tags with the specific class for calendar blocks
        event_blocks = soup.find_all('a', class_=lambda c: c and 'program__calendar-col-block' in c)
        
        links = []
        for block in event_blocks:
            href = block.get('href')
            if href:
                # Ensure the URL is absolute
                if href.startswith('/'):
                    href = f"https://montreal.mutek.org{href}"
                
                # Avoid duplicates
                if href not in links:
                    links.append(href)
        
        return links
    except Exception as e:
        print(f"Error fetching program links: {e}")
        return []

def convert_to_24h(time_str):
    if not time_str or time_str == "Unknown":
        return time_str
        
    time_str = time_str.strip().lower()
    try:
        if ':' in time_str:
            dt = datetime.strptime(time_str, '%I:%M %p')
        else:
            dt = datetime.strptime(time_str, '%I %p')
        return dt.strftime('%H:%M')
    except ValueError:
        return time_str

def _extract_artists_from_container(container):
    """Helper to extract artist details from a swiper container."""
    artists_data = []
    slides = container.find_all(class_=lambda c: c and 'swiper-slide' in c)
    
    if not slides:
        return artists_data
        
    for slide in slides:
        artist_name = "Unknown Artist"
        start_time = "Unknown"
        end_time = "Unknown"
        program_track = "Unknown"
        date = "Unknown"
        
        # 1. Extract Artist Name
        artist_heading = slide.find(['h4', 'h5'], class_=lambda c: c and 'artists-single__title' in c)
        if not artist_heading:
            artist_heading = slide.find(['h4', 'h5', 'strong'])
            
        if not artist_heading:
            # Try finding an anchor tag if headings fail
            artist_heading = slide.find('a', href=lambda href: href and '/en/artists/' in href)

        if artist_heading:
            name_span = artist_heading.find('span')
            if name_span:
                artist_name = name_span.get_text(strip=True)
            else:
                for sup in artist_heading.find_all('sup'):
                    sup.decompose()
                artist_name = artist_heading.get_text(strip=True)

        # 2. Extract Track, Date, and Time from wysiwyg columns
        wysiwyg_container = slide.find('div', class_=lambda c: c and 'artists-single__wysiwyg' in c)
        if wysiwyg_container:
            cols = wysiwyg_container.find_all('div', class_='artists-single__wysiwyg-col')
            
            # Usually 3 columns: [Track, Date, Time]. Check if they exist.
            if len(cols) >= 1:
                p = cols[0].find('p')
                if p: program_track = p.get_text(strip=True)
            
            if len(cols) >= 2:
                p = cols[1].find('p')
                if p: date = p.get_text(strip=True)
                
        # 3. Extract time by scanning all p tags for "Performs at"
        time_p = None
        for p_tag in slide.find_all('p'):
            if p_tag.get_text() and 'Performs at' in p_tag.get_text():
                time_p = p_tag
                break
        
        if time_p:
            full_time_text = time_p.get_text(strip=True)
            time_pattern = r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))'
            matches = re.findall(time_pattern, full_time_text, flags=re.IGNORECASE)
            
            if len(matches) >= 1:
                start_time = convert_to_24h(matches[0])
            if len(matches) >= 2:
                end_time = convert_to_24h(matches[1])
                
        artists_data.append({
            'artist': artist_name,
            'track': program_track,
            'date': date,
            'start_time': start_time,
            'end_time': end_time
        })
        
    return artists_data

def scrape_event_details(url):
    """Scrapes a specific event page for venues, artists, times, track, and date."""
    print(f"Scraping event details from: {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            html = response.read()

        soup = BeautifulSoup(html, 'html.parser')
        
        venue_data = {}
        
        # Scenario A: The event has multiple showrooms (e.g., Nocturnes) indicated by h3 tags
        showroom_titles = soup.find_all('h3', class_='event-single__showrooms-title')
        
        if showroom_titles:
            for title_element in showroom_titles:
                venue_name = title_element.get_text(strip=True)
                # The artists for this venue are in the sibling div immediately following the h3
                container = title_element.find_next_sibling('div', class_=lambda c: c and 'event-single__showrooms-container' in c)
                
                if container:
                    venue_data[venue_name] = _extract_artists_from_container(container)
        else:
            # Scenario B: Single room or general event lacking h3 titles (e.g., Expérience)
            containers = soup.find_all('div', class_=lambda c: c and 'event-single__showrooms-container' in c)
            for idx, container in enumerate(containers):
                # Fallback to a default name since it's not explicitly labeled
                venue_name = "Main Venue" if len(containers) == 1 else f"Venue {idx+1}"
                venue_data[venue_name] = _extract_artists_from_container(container)

        return {
            "event_url": url,
            "structured_schedule": venue_data
        }

    except urllib.error.URLError as e:
        print(f"Error fetching the URL {url}: {e.reason}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred parsing {url}: {e}")
        return None

if __name__ == '__main__':
    # 1. Scrape the main program schedule for all event links
    program_url = "https://montreal.mutek.org/en/schedule/program?_gl=1*yqfcs7*_up*MQ..&gclid=CjwKCAjwpqHTBhAcEiwAj2Aful13LWxyHsdkRPvpqJvZCNNNjIn4RvVos3E_dzwZOW76qsud4LT6GhoCV48QAvD_BwE&gbraid=0AAAAADOgMODZz1eGZxaShegp9wPUlb_EZ#weekly-view"
    
    event_links = scrape_program_links(program_url)
    print(f"\nFound {len(event_links)} event links on the schedule page.")
    
    # Optional: limit the links for testing to avoid hitting the server too hard initially
    # event_links = event_links[:3] 
    
    all_festival_data = []
    
    print("\n" + "="*50 + "\n")
    
    # 2. Iterate through each discovered link and extract the details
    for link in event_links:
        event_data = scrape_event_details(link)
        if event_data and event_data.get('structured_schedule'):
            all_festival_data.append(event_data)
            print(f" -> Successfully parsed data for {link}")
        else:
            print(f" -> No schedule data found for {link}")
            
    print("\n" + "="*50 + "\n")
    print("FINAL CONSOLIDATED DATA:")
    print(json.dumps(all_festival_data, indent=4, ensure_ascii=False))