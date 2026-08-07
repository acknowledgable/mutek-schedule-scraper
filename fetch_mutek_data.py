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

def nocturne(url):
    """Scrapes a specific event page (like Nocturne) for venues, artists, and times."""
    print(f"Scraping event details from: {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as response:
            html = response.read()

        soup = BeautifulSoup(html, 'html.parser')
        
        venue_data = {}
        showroom_titles = soup.find_all('h3', class_='event-single__showrooms-title')
        
        for title_element in showroom_titles:
            venue_name = title_element.get_text(strip=True)
            venue_data[venue_name] = []
            
            container = title_element.find_next_sibling('div', class_='event-single__showrooms-container')
            
            if container:
                slides = container.find_all(class_=lambda c: c and 'swiper-slide' in c)
                
                if slides:
                    for slide in slides:
                        artist_name = "Unknown Artist"
                        start_time = "Unknown"
                        end_time = "Unknown"
                        
                        artist_heading = slide.find(['h4', 'h5'], class_=lambda c: c and 'artists-single__title' in c)
                        if not artist_heading:
                            artist_heading = slide.find(['h4', 'h5', 'strong'])

                        if artist_heading:
                            name_span = artist_heading.find('span')
                            if name_span:
                                artist_name = name_span.get_text(strip=True)
                            else:
                                for sup in artist_heading.find_all('sup'):
                                    sup.decompose()
                                artist_name = artist_heading.get_text(strip=True)
                        else:
                            artist_link = slide.find('a', href=lambda href: href and '/en/artists/' in href)
                            if artist_link:
                                name_span = artist_link.find('span')
                                if name_span:
                                    artist_name = name_span.get_text(strip=True)
                                else:
                                    for sup in artist_link.find_all('sup'):
                                        sup.decompose()
                                    artist_name = artist_link.get_text(strip=True)
                                
                        time_p = None
                        for p_tag in slide.find_all('p'):
                            if 'Performs at' in p_tag.get_text():
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
                        
                        venue_data[venue_name].append({
                            'artist': artist_name,
                            'start_time': start_time,
                            'end_time': end_time
                        })

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
    # 1. Scrape the main program schedule for links
    program_url = "https://montreal.mutek.org/en/schedule/program?_gl=1*yqfcs7*_up*MQ..&gclid=CjwKCAjwpqHTBhAcEiwAj2Aful13LWxyHsdkRPvpqJvZCNNNjIn4RvVos3E_dzwZOW76qsud4LT6GhoCV48QAvD_BwE&gbraid=0AAAAADOgMODZz1eGZxaShegp9wPUlb_EZ#weekly-view"
    
    event_links = scrape_program_links(program_url)
    print(f"\nFound {len(event_links)} event links on the schedule page.")
    for link in event_links:
        print(f" - {link}")
        
    print("\n" + "="*50 + "\n")
    
    # 2. Test the nocturne function on the specific URL
    test_nocturne_url = "https://montreal.mutek.org/en/shows/2026/nocturne-2"
    nocturne_data = nocturne(test_nocturne_url)
    
    if nocturne_data:
        print("Successfully parsed Nocturne event data:")
        print(json.dumps(nocturne_data, indent=4, ensure_ascii=False))