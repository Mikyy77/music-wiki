import requests, gzip, re, time, os, random, json

# config
SITEMAP_INDEX = "https://musicbrainz.org/sitemap-index.xml.gz"
UA = {"User-Agent": "IR-Crawler/1.0 (michal.darovec@gmail.com) - student, school research purposes"}
CRAWL_DELAY = 3.0
RAW_DIR = "raw_html"
LOG_FILE = "json/progress.json"

session = requests.Session()
session.headers.update({
    "User-Agent": "IR-Crawler/1.0 (xdarovec@stuba.sk) - student, research purposes",
    "From": "xdarovec@stuba.sk",
    "Connection": "close",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

MAX_ARTISTS = 3000
MAX_RELEASE_PAGES = 5
MAX_RECORDING_PAGES = 5

# regex
ARTIST_SITEMAP_RE = re.compile(r"<loc>(https://musicbrainz.org/sitemap-artist-[^<]+)</loc>")
UUID_RE = re.compile(r"https://musicbrainz.org/artist/([0-9a-f\-]{36})")
TAG_RE = re.compile(r'<a href="/tag/([^"]+)">([^<]+)</a>.*?has been used ([\d,]+) times', re.S)
ARTIST_RE = re.compile(r'/artist/([0-9a-f\-]{36})')

progress = {}

# helper functions
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def load_progress():
    global progress
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            progress = json.load(f)
    else:
        progress = {}

def save_progress():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)

def get_artist_sitemaps():
    r = requests.get(SITEMAP_INDEX, timeout=20)
    r.raise_for_status()
    xml = gzip.decompress(r.content).decode("utf-8")
    return ARTIST_SITEMAP_RE.findall(xml)

def get_artist_ids(sitemap_url):
    r = requests.get(sitemap_url, timeout=20)
    r.raise_for_status()
    xml = gzip.decompress(r.content).decode("utf-8")
    return UUID_RE.findall(xml)

def fetch_and_save(url, outpath):
    """Downloads a URL and saves it to a file, returns HTML text."""
    if os.path.exists(outpath):
        with open(outpath, "r", encoding="utf-8") as f:
            return f.read()
    try:
        print("Fetching:", url)
        r = session.get(url, timeout=5)
        r.raise_for_status()
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Saved:", outpath)
        return r.text
    except requests.exceptions.ReadTimeout:
        wait = min(60, CRAWL_DELAY * 2)
        print(f"[Timeout] Waiting {wait:.1f}s before retrying {url}")
        time.sleep(wait)
    except Exception as e:
        print("Error:", url, e)
        return None
    finally:
        time.sleep(random.uniform(3.5, 7.0))


def crawl_site(base_url, out_prefix):
    outpath = f"{out_prefix}.html"
    fetch_and_save(base_url, outpath)


def crawl_paginated(base_url, out_prefix, max_pages):
    """Download up to max_pages, stop if no further page link is found"""
    pages = 0
    for page in range(1, max_pages + 1):
        url = f"{base_url}?page={page}"
        outpath = f"{out_prefix}-p{page}.html"
        html = fetch_and_save(url, outpath)
        if html is None:
            break
        pages += 1
        if f"?page={page+1}" not in html:
            break
    return pages

def crawl_artist(artist_id, retries=2):
    load_progress()
    if artist_id in progress:
        print(f"Skipping {artist_id}, already in progress log")
        return

    print(f"\n=== Crawling artist {artist_id} ===")
    artist_dir = os.path.join(RAW_DIR, artist_id)
    ensure_dir(artist_dir)
    base = f"https://musicbrainz.org/artist/{artist_id}"
    profile_path = os.path.join(artist_dir, "profile.html")

    # retry loop
    html = None
    for attempt in range(1, retries + 1):
        html = fetch_and_save(base, profile_path)
        if html:
            break
        print(f"Retry {attempt}/{retries} for {artist_id}")
        time.sleep(3)

    if not html:
        print(f"[✗] Skipping {artist_id} — profile fetch failed after {retries} attempts")
        return  # skip related pages entirely

    # continue only if profile exists
    releases = crawl_paginated(f"{base}/releases", os.path.join(artist_dir, "releases"), MAX_RELEASE_PAGES)
    recordings = crawl_paginated(f"{base}/recordings", os.path.join(artist_dir, "recordings"), MAX_RECORDING_PAGES)
    crawl_site(f"{base}/relationships", os.path.join(artist_dir, "relationships"))

    progress[artist_id] = {
        "releases_pages": releases,
        "recordings_pages": recordings,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_progress()
    print(f"Finished {artist_id}: releases={releases}, recordings={recordings}")


def crawl_missing_subpages():
    """
    Find all artist folders in RAW_DIR and crawl missing profile, releases, recordings, and relationships pages.
    """
    ensure_dir(RAW_DIR)
    load_progress()
    print("len(artists) =", len(os.listdir(RAW_DIR)))
    for artist_id in os.listdir(RAW_DIR):
        artist_path = os.path.join(RAW_DIR, artist_id)
        if not os.path.isdir(artist_path):
            continue

        base_url = f"https://musicbrainz.org/artist/{artist_id}"
        print(f"\n=== Checking missing pages for {artist_id} ===")

        # PROFILE
        profile_path = os.path.join(artist_path, "profile.html")
        if not os.path.exists(profile_path):
            print(f"[→] Crawling missing profile for {artist_id}")
            html = fetch_and_save(base_url, profile_path)
            if html:
                progress.setdefault(artist_id, {})["profile_crawled"] = True
                print(f"   [✓] Profile fetched")
            else:
                print(f"   [✗] Failed to fetch profile")

        # RELEASES
        releases_exist = any(f.startswith("releases-p") for f in os.listdir(artist_path))
        if not releases_exist:
            print(f"[→] Crawling missing releases for {artist_id}")
            pages = crawl_paginated(f"{base_url}/releases", os.path.join(artist_path, "releases"), MAX_RELEASE_PAGES)
            progress.setdefault(artist_id, {})["releases_pages"] = pages
            print(f"   [✓] Releases fetched: {pages} pages")

        # RECORDINGS
        recordings_exist = any(f.startswith("recordings-p") for f in os.listdir(artist_path))
        if not recordings_exist:
            print(f"[→] Crawling missing recordings for {artist_id}")
            pages = crawl_paginated(f"{base_url}/recordings", os.path.join(artist_path, "recordings"), MAX_RECORDING_PAGES)
            progress.setdefault(artist_id, {})["recordings_pages"] = pages
            print(f"   [✓] Recordings fetched: {pages} pages")

        # RELATIONSHIPS
        rel_path = os.path.join(artist_path, "relationships.html")
        if not os.path.exists(rel_path):
            print(f"[→] Crawling missing relationships for {artist_id}")
            html = fetch_and_save(f"{base_url}/relationships", rel_path)
            if html:
                progress.setdefault(artist_id, {})["relationships_crawled"] = True
                print(f"   [✓] Relationships fetched")
            else:
                print(f"   [✗] Failed to fetch relationships")

        # Update timestamp if anything changed
        progress[artist_id]["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_progress()
        time.sleep(random.uniform(2.0, 4.0))  # polite delay between artists

# Tag crawling config
# reason - find popular artists by tags, enrich data with diverse and more popular, well-known artists
TAG_DISCOVERY = True          # enable tag-based enrichment
TAG_LIMIT = 30                # how many tags to explore
MIN_TAG_COUNT = 150000        # minimum popularity threshold
# MAX_TAG_COUNT = 200000      # maximum popularity threshold (not used currently)
MAX_ARTISTS_PER_TAG = 100     # top N artists per tag
OUT_POPULAR = "json/popular_artists.json"


def fetch(url):
    """Simple GET request with retry logic and polite delay."""
    try:
        print(f"Fetching: {url}")
        r = session.get(url, timeout=10)
        r.raise_for_status()
        time.sleep(random.uniform(2.0, 5.0))
        return r.text
    except requests.exceptions.ReadTimeout:
        print(f"[Timeout] Retrying after {CRAWL_DELAY:.1f}s: {url}")
        time.sleep(CRAWL_DELAY)
        return None
    except Exception as e:
        print("Error:", url, e)
        return None

def discover_popular_artists_from_tags():
    """Fetch /tags and discover top artists for each popular tag, skipping already saved ones."""
    TAGS_URL = "https://musicbrainz.org/tags"
    html = fetch(TAGS_URL)
    if not html:
        print("[✗] Failed to fetch tags page.")
        return []

    # Load existing popular artists file
    existing_artists = set()
    if os.path.exists(OUT_POPULAR):
        with open(OUT_POPULAR, "r", encoding="utf-8") as f:
            try:
                existing_artists = set(json.load(f))
            except json.JSONDecodeError:
                existing_artists = set()
    print(f"Loaded {len(existing_artists)} already saved artists.")

    # Find tags in popularity range
    tags = []
    for slug, name, count_str in TAG_RE.findall(html):
        count = int(count_str.replace(",", ""))
        if MIN_TAG_COUNT <= count:
            tags.append({"slug": slug, "name": name.strip(), "count": count})

    tags.sort(key=lambda x: x["count"], reverse=True)
    tags = tags[:TAG_LIMIT]
    print(f"Found {len(tags)} popular tags (minimal tags: {MIN_TAG_COUNT}.")

    new_artists = set()
    for tag in tags:
        tag_url = f"https://musicbrainz.org/tag/{tag['slug']}/artist"
        html = fetch(tag_url)
        if not html:
            continue
        artist_ids = ARTIST_RE.findall(html)
        print(f"[{tag['name']}] → {len(artist_ids)} artists")

        for a in artist_ids[:MAX_ARTISTS_PER_TAG]:
            if a not in existing_artists:
                new_artists.add(a)

    print(f"\n✅ Total NEW artists found: {len(new_artists)}")

    # Save updated combined list
    combined = sorted(existing_artists.union(new_artists))
    with open(OUT_POPULAR, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    print(f"Updated {OUT_POPULAR} (now {len(combined)} total artists).")
    return list(new_artists)

# USED TO CHECK FOR MISSING ARTISTS AFTER CRAWL - COMMENTED OUT FOR NORMAL USAGE

# def check_missing_artists():
#     # Load desired artist IDs
#     with open(OUT_POPULAR, "r", encoding="utf-8") as f:
#         popular = json.load(f)
#
#     # Get actually crawled artist folders
#     crawled = [d for d in os.listdir(RAW_DIR) if os.path.isdir(os.path.join(RAW_DIR, d))]
#
#     popular_set = set(popular)
#     crawled_set = set(crawled)
#
#     missing = sorted(list(popular_set - crawled_set))
#     extra = sorted(list(crawled_set - popular_set))
#
#     print(f"Total popular artists: {len(popular)}")
#     print(f"Total crawled artists: {len(crawled)}")
#     print(f"Missing crawls: {len(missing)}")
#     print(f"Extra crawled (not in popular list): {len(extra)}\n")
#
#     if missing:
#         print("=== Missing artist IDs ===")
#         for m in missing[:20]:
#             print(m)
#         if len(missing) > 20:
#             print(f"... and {len(missing) - 20} more.")
#
#     if extra:
#         print("\n=== Extra artist IDs (not in popular_artists.json) ===")
#         for e in extra[:10]:
#             print(e)
#
#     # Optionally save to file for easy batch crawling later
#     with open("missing_artists.json", "w", encoding="utf-8") as f:
#         json.dump(missing, f, indent=2)
#     print("\nSaved missing artist IDs to missing_artists.json")


if __name__ == "__main__":
    ensure_dir(RAW_DIR)
    load_progress()

    mode = "sitemap" # choose tags or sitemap as crawl source

    print(f"\n=== Running in {mode.upper()} mode ===\n")

    start_time = time.time()

    if mode == "tags":
        artist_ids = discover_popular_artists_from_tags()

        print(f"Discovered {len(artist_ids)} new artists to crawl.")
        if not artist_ids:
            print("No new artists found in this popularity range. Exiting.")
            exit(0)
    else:
        sitemaps = get_artist_sitemaps()
        random.shuffle(sitemaps)
        artist_ids = []
        for sm in sitemaps:
            ids = get_artist_ids(sm)
            artist_ids.extend(ids)
            if len(artist_ids) >= MAX_ARTISTS:
                break

    print(f"\nTotal artist IDs to crawl: {len(artist_ids)}\n")

    count = 0
    for artist_id in artist_ids:
        crawl_artist(artist_id)
        count += 1
        if count >= MAX_ARTISTS:
            break

    print(f"\nDone, {count} artists crawled.")
    print("Total time:", round(time.time() - start_time, 2), "seconds")
