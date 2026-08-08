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
import sys
import argparse
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def scrape_program_links(program_url):
    """Scrapes event page links from the central schedule page."""
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
        print(f"Error fetching program links: {e}", file=sys.stderr)
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
    overall_program_track = "Unknown"
    slides = container.find_all(class_=lambda c: c and 'swiper-slide' in c)
    
    if not slides:
        return {"program_track": overall_program_track, "artists": artists_data}

    for slide in slides:
        # Extract Artist Name
        artist_element = slide.find(class_='artists-single__title')
        artist_name = "Unknown Artist"
        if artist_element:
            # Strip out <sup> tags first
            for sup in artist_element.find_all('sup'):
                sup.decompose()
            span = artist_element.find('span')
            artist_name = span.get_text(strip=True) if span else artist_element.get_text(strip=True)

        # Extract Program Track, Date, and Time
        date = "Unknown"
        start_time = "Unknown"
        end_time = "Unknown"
        
        # Extract Artist Profile URL
        profile_url = "Unknown"
        href = slide.get('href')
        if href:
            if href.startswith('/'):
                 profile_url = f"https://montreal.mutek.org{href}"
            else:
                 profile_url = href

        wysiwyg = slide.find(class_='artists-single__wysiwyg')
        if wysiwyg:
            cols = wysiwyg.find_all(class_='artists-single__wysiwyg-col')
            if len(cols) >= 1:
                program_track = cols[0].get_text(strip=True)
                if overall_program_track == "Unknown" and program_track:
                    overall_program_track = program_track
            if len(cols) >= 2:
                date = cols[1].get_text(strip=True)
            if len(cols) >= 3:
                for p_tag in cols[2].find_all('p'):
                    text = p_tag.get_text(separator=" ", strip=True)
                    if 'Performs at' in text:
                        # Find 12h times using regex
                        matches = re.findall(r'(\d{1,2}:\d{2}\s*[ap]m|\d{1,2}\s*[ap]m)', text, re.IGNORECASE)
                        if len(matches) >= 1:
                            start_time = convert_to_24h(matches[0])
                        if len(matches) >= 2:
                            end_time = convert_to_24h(matches[1])
                        break
        
        artists_data.append({
            "artist": artist_name,
            "profile_url": profile_url,
            "date": date,
            "start_time": start_time,
            "end_time": end_time
        })
        
    return {
        "program_track": overall_program_track,
        "artists": artists_data
    }

def scrape_event_details(url):
    """Scrapes a specific event page for venues, artists, times, track, and date."""
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
            
            sidebar_location = soup.find('div', class_='event-single__sidebar-location')
            actual_venue_name = "Main Venue"
            
            if sidebar_location:
                p_tag = sidebar_location.find('p')
                if p_tag:
                    actual_venue_name = p_tag.get_text(strip=True)

            containers = soup.find_all('div', class_=lambda c: c and 'event-single__showrooms-container' in c)
            for idx, container in enumerate(containers):
                # Fallback to the extracted name or a default name since it's not explicitly labeled
                venue_name = actual_venue_name if len(containers) == 1 else f"{actual_venue_name} {idx+1}"
                venue_data[venue_name] = _extract_artists_from_container(container)

        return {
            "event_url": url,
            "structured_schedule": venue_data
        }

    except urllib.error.URLError as e:
        print(f"Error fetching the URL {url}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred parsing {url}: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Mutek schedule data.')
    parser.add_argument('-d', '--develop', action='store_true', help='Scrape only one single-room event and one multi-room event, then exit.')
    args = parser.parse_args()

    # 1. Scrape the main program schedule for all event links
    program_url = "https://montreal.mutek.org/en/schedule/program?_gl=1*yqfcs7*_up*MQ..&gclid=CjwKCAjwpqHTBhAcEiwAj2Aful13LWxyHsdkRPvpqJvZCNNNjIn4RvVos3E_dzwZOW76qsud4LT6GhoCV48QAvD_BwE&gbraid=0AAAAADOgMODZz1eGZxaShegp9wPUlb_EZ#weekly-view"
    
    event_links = scrape_program_links(program_url)
    
    all_festival_data = []
    found_single = False
    found_multi = False
    
    # 2. Iterate through each discovered link and extract the details
    for link in event_links:
        event_data = scrape_event_details(link)
        if event_data and event_data.get('structured_schedule'):
            schedule = event_data['structured_schedule']
            
            # If in develop mode, limit to 1 single-room and 1 multi-room
            if args.develop:
                is_multi = len(schedule.keys()) > 1
                
                if is_multi and not found_multi:
                    all_festival_data.append(event_data)
                    found_multi = True
                elif not is_multi and not found_single:
                    all_festival_data.append(event_data)
                    found_single = True
                    
                # Break early once we have one of each
                if found_single and found_multi:
                    break
            else:
                all_festival_data.append(event_data)
            
    print(json.dumps(all_festival_data, indent=4, ensure_ascii=False))