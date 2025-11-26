import re, json

PROFILE_RE = {
    "uuid": re.compile(r'/artist/([0-9a-f\-]{36})'),
    "name": re.compile(r'<h1><a[^>]*><bdi>([^<]+)</bdi></a>'),
    "comment": re.compile(r'<span class="comment">\(<bdi>([^<]+)</bdi>\)</span>'),
    "type": re.compile(r'<dd class="type">([^<]+)</dd>'),
    "founded": re.compile(r'Founded:\s*([0-9\-]+)\s*in\s*([^,<>]+)', re.I),
    "area": re.compile(r'Area:\s*([^,<>"\n]+)', re.I),
    "isni": re.compile(r'isni\.org/([0-9X]+)', re.I),
    "rating_block": re.compile(r'<h2 class="rating">.*?</p>', re.S),
    "rating_value": re.compile(r'style="width:(\d+)%">([\d.]+)</span>'),
    "genres_block": re.compile(r'<h3>Genres</h3><div class="genre-list">(.*?)</div>', re.S),
    "other_tags_block": re.compile(r'<h3>Other tags</h3><div id="sidebar-tag-list">(.*?)</div>', re.S),
    "anchor_texts": re.compile(r'<a [^>]*>([^<]+)</a>'),
    "has_none": re.compile(r'\(none\)', re.I),
    "release": re.compile(
        r'<tr.*?><td class="c">(\d{4}|—)</td>.*?<a class="wrap-anywhere" href="([^"]+)"><bdi>([^<]+)</bdi></a>.*?<td><bdi>.*?>([^<]+)</a>',
        re.S
    ),
    "recording": re.compile(
        r'<tr.*?>.*?<a class="wrap-anywhere" href="([^"]+)"><bdi>([^<]+)</bdi></a>.*?<td><bdi>([^<]+)</bdi>.*?</tr>',
        re.S
    ),
    "relationship": re.compile(
        r'<tr.*?><td><a href="([^"]+/artist/[^"]+)"><bdi>([^<]+)</bdi></a>.*?<td>([^<]+)</td>',
        re.S
    ),
    "last_updated": re.compile(r'<p class="lastupdate">Last updated on ([^<]+)</p>'),
    # "ext_links": re.compile(r'<ul class="external_links">(.*?)</ul>', re.S),
    # "ext_item": re.compile(r'<a href="([^"]+)"[^>]*>([^<]+)</a>'),
}


def parse_profile_html(html):
    """Extract main profile metadata from profile.html"""
    data = {}
    get = lambda key: PROFILE_RE[key].search(html).group(1) if PROFILE_RE[key].search(html) else None

    data["uuid"] = get("uuid")
    data["name"] = get("name")
    data["comment"] = get("comment")
    data["type"] = get("type")
    data["founded"] = get("founded")
    data["founded_in"] = PROFILE_RE["founded"].search(html).group(2) if PROFILE_RE["founded"].search(html) else None
    data["area"] = get("area")
    data["isni_code"] = get("isni")

    rating_block = PROFILE_RE["rating_block"].search(html)
    if rating_block:
        m = PROFILE_RE["rating_value"].search(rating_block.group(0))
        if m:
            data["rating_percent"] = m.group(1)
            data["rating_value"] = float(m.group(2))
        else:
            data["rating_percent"] = None
            data["rating_value"] = None
    else:
        data["rating_percent"] = None
        data["rating_value"] = None

    # Genres
    genres = []
    block = PROFILE_RE["genres_block"].search(html)
    if block and not PROFILE_RE["has_none"].search(block.group(1)):
        genres = PROFILE_RE["anchor_texts"].findall(block.group(1))
    data["genres"] = sorted(set(g.strip() for g in genres if g.strip()))

    # Other tags
    other_tags = []
    block = PROFILE_RE["other_tags_block"].search(html)
    if block and not PROFILE_RE["has_none"].search(block.group(1)):
        other_tags = PROFILE_RE["anchor_texts"].findall(block.group(1))
    data["other_tags"] = sorted(set(t.strip() for t in other_tags if t.strip()))

    # External links - disabled for now, maybe will be used in the future
    # links = []
    # ext_block = PROFILE_RE["ext_links"].search(html)
    # if ext_block:
    #     for url, name in PROFILE_RE["ext_item"].findall(ext_block.group(1)):
    #         links.append({"name": name.strip(), "url": url})
    # data["external_links"] = links

    # Last updated
    data["last_updated"] = get("last_updated")

    return data


def parse_releases(folder):
    """Parse releases row-by-row from all releases-pX.html files."""
    releases = []
    row_re = re.compile(
        r'<a class="wrap-anywhere" href="([^"]+)"><bdi>([^<]+)</bdi></a>.*?'
        r'<td><bdi><a [^>]+>([^<]+)</a></bdi></td>.*?'
        r'<td>([^<]*)</td>.*?'
        r'<td>(\d+)</td>.*?'
        r'<abbr title="([^"]+)">.*?<span class="release-date">([^<]*)</span>.*?'
        r'<a href="[^"]+"><bdi>([^<]+)</bdi></a>.*?'
        r'(?:<span class="catalog-number">([^<]+)</span>)?.*?'
        r'class="barcode-cell">([^<]*)</td>',
        re.S
    )

    for fname in sorted(os.listdir(folder)):
        if not (fname.startswith("releases-") and fname.endswith(".html")):
            continue
        path = os.path.join(folder, fname)
        with open(path, encoding="utf-8") as f:
            html = f.read()

        rows = re.findall(r'<tr.*?</tr>', html, re.S)
        for tr in rows:
            m = row_re.search(tr)
            if not m:
                continue
            href, title, artist, fmt, tracks, country, date, label, catalog, barcode = m.groups()
            releases.append({
                "title": (title or "").strip(),
                "artist": (artist or "").strip(),
                "format": (fmt or "").strip() or None,
                "tracks": int(tracks) if tracks and tracks.isdigit() else None,
                "country": (country or "").strip() or None,
                "date": (date or "").strip() or None,
                "label": (label or "").strip() or None,
                "catalog": (catalog or "").strip() or None,
                "barcode": (barcode or "").replace("[none]", "").strip() or None,
                "url": "https://musicbrainz.org" + href
            })

    print(f"Parsed {len(releases)} release entries total.")

    # Deduplicate by normalized title
    aggregated = {}
    for r in releases:
        key = re.sub(r'\s*\(.*?\)\s*', '', r["title"]).strip().lower()
        if key not in aggregated:
            aggregated[key] = {
                "title": r["title"],
                "artist": r["artist"],
                "variants": set(),
                "formats": set(),
                "labels": set(),
                "countries": set(),
                "dates": set(),
                "catalogs": set(),
                "barcodes": set()
            }
        aggregated[key]["variants"].add(r["title"])
        if r["format"]: aggregated[key]["formats"].add(r["format"])
        if r["label"]: aggregated[key]["labels"].add(r["label"])
        if r["country"]: aggregated[key]["countries"].add(r["country"])
        if r["date"]: aggregated[key]["dates"].add(r["date"])
        if r["catalog"]: aggregated[key]["catalogs"].add(r["catalog"])
        if r["barcode"]: aggregated[key]["barcodes"].add(r["barcode"])

    # Build final deduplicated list
    refined = []
    for _, info in aggregated.items():
        refined.append({
            "title": info["title"],
            "artist": info["artist"],
            "formats": sorted(info["formats"]),
            "labels": sorted(info["labels"]),
            "countries": sorted(info["countries"]),
            "dates": sorted(info["dates"]),
            "catalogs": sorted(info["catalogs"]),
            "barcodes": sorted(info["barcodes"]),
            "occurrences": len(info["variants"]),
            "variants": sorted(info["variants"])
        })

    refined.sort(key=lambda x: x["title"].lower())
    return refined



import re, statistics, os

def parse_recordings(folder):
    """Fast parse and aggregate unique recordings from all recordings-pX.html files."""
    recordings = []
    row_re = re.compile(
        r'<tr[^>]*>.*?'
        r'<a class="wrap-anywhere" href="([^"]+)"><bdi>([^<]+)</bdi></a>.*?'  # href + title
        r'<td><bdi><a [^>]+>([^<]+)</a></bdi></td>.*?'                      # artist
        r'(?:<td class="c">.*?<span class="current-rating" style="width:\d+%">([\d.]+)</span>.*?</td>)?.*?'  # optional rating
        r'<td>([\d:]+)</td>.*?'                                             # length
        r'<td>.*?<a href="[^"]+"><bdi>([^<]+)</bdi></a>',                   # release group
        re.S
    )

    for fname in sorted(os.listdir(folder)):
        if not (fname.startswith("recordings-") and fname.endswith(".html")):
            continue

        path = os.path.join(folder, fname)
        with open(path, encoding="utf-8") as f:
            html = f.read()

        # Pre-split HTML by <tr> blocks to reduce regex overhead
        for block in html.split("<tr"):
            if "wrap-anywhere" not in block:
                continue
            m = row_re.search("<tr" + block)
            if not m:
                continue

            href, title, artist, rating, length, release_group = m.groups()
            recordings.append((
                title.strip(),
                artist.strip(),
                "https://musicbrainz.org" + href,
                float(rating) if rating else None,
                parse_length(length),
                release_group.strip()
            ))

    # Aggregate duplicates (by normalized title)
    aggregated = {}
    for title, artist, url, rating, length, release_group in recordings:
        key = re.sub(r'\s*\(.*?\)\s*', '', title).strip().lower()
        rec = aggregated.setdefault(key, {
            "title": title,
            "variants": set(),
            "lengths": [],
            "ratings": []
        })
        rec["variants"].add(title)
        if length:
            rec["lengths"].append(length)
        if rating:
            rec["ratings"].append(rating)

    # Build final list
    refined = []
    for _, info in aggregated.items():
        avg_length = round(statistics.mean(info["lengths"]), 2) if info["lengths"] else None
        avg_rating = round(statistics.mean(info["ratings"]), 2) if info["ratings"] else None
        refined.append({
            "title": info["title"],
            "avg_length_sec": avg_length,
            "avg_rating": avg_rating,
            "occurrences": len(info["variants"]),
            "variants": sorted(info["variants"])
        })

    refined.sort(key=lambda x: x["title"].lower())
    return refined


def parse_length(s):
    """Convert MM:SS to seconds"""
    m = re.match(r'(\d+):(\d+)', s)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def parse_relationships(folder):
    """Parse relationships.html and extract members, original members, and artistic directors."""
    path = os.path.join(folder, "relationships.html")
    if not os.path.exists(path):
        return {"members": [], "original_members": [], "artistic_directors": []}

    with open(path, encoding="utf-8") as f:
        html = f.read()

    # --- Capture each relationship row (<th> + <td> pair)
    row_re = re.compile(r'<th[^>]*>([^<:]+):</th>\s*<td[^>]*>(.*?)</td>', re.S | re.I)

    # --- Capture linked artists inside each <td>
    artist_re = re.compile(
        r'<a [^>]*href="(/artist/[^"]+)"[^>]*><bdi>([^<]+)</bdi></a>', re.S
    )

    # Capture optional date or detail strings like "(from 1996 to present)"
    detail_re = re.compile(r'\(([^)]+)\)')

    data = {
        "members": [],
        "original_members": [],
        "artistic_directors": []
    }

    for label, cell_html in row_re.findall(html):
        label = label.strip().lower().replace(" ", "_")
        if label not in data:
            continue  # skip unrelated categories like "associated acts", etc.

        for href, name in artist_re.findall(cell_html):
            # Try to extract time range or comment near the artist
            details = detail_re.findall(cell_html)
            entry = {
                "name": name.strip(),
                "details": details[0].strip() if details else None,
                "url": "https://musicbrainz.org" + href
            }
            data[label].append(entry)

    # combined searchable text summary
    data["text_summary"] = " ".join(
        n["name"] for cat in data.values() if isinstance(cat, list) for n in cat
    )

    return data


def parse_artist_folder(folder):
    """Combine profile, releases, recordings, and relationships"""
    profile_path = os.path.join(folder, "profile.html")
    if not os.path.exists(profile_path):
        return None

    with open(profile_path, encoding="utf-8") as f:
        html = f.read()
    data = parse_profile_html(html)
    data["url"] = f"https://musicbrainz.org/artist/{data['uuid']}"
    print('parsed profile')

    data["releases"] = parse_releases(folder)
    data["recordings"] = parse_recordings(folder)
    data["relationships"] = parse_relationships(folder)

    return data

RAW_DIR = "raw_html"
OUT_DIR = "parsed_artists"

def parse_all_artists():
    artist_folders = [
        d for d in os.listdir(RAW_DIR)
        if os.path.isdir(os.path.join(RAW_DIR, d))
    ]

    print(f"Found {len(artist_folders)} artist folders.")

    total = 0
    success = 0
    for artist_id in artist_folders:
        folder = os.path.join(RAW_DIR, artist_id)
        print(f"\n[{total+1}/{len(artist_folders)}] Parsing {artist_id} ...")

        try:
            parsed = parse_artist_folder(folder)
            if not parsed:
                print(f"No parsed data for {artist_id}, skipping.")
                continue

            out_path = os.path.join(OUT_DIR, f"{artist_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=4)

            print(f"[✓] Saved: {out_path}")
            success += 1

        except Exception as e:
            print(f"[!] Error parsing {artist_id}: {e}")

        total += 1

    print(f"\nDone — parsed {success}/{total} artists successfully.")

if __name__ == "__main__":
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)
    parse_all_artists()
