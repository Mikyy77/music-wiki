import re, os, json

PROFILE_RE = {
    "uuid": re.compile(r'/artist/([0-9a-f\-]{36})'),
    "name": re.compile(r'<h1><a[^>]*><bdi>([^<]+)</bdi></a>'),
    "comment": re.compile(r'<span class="comment">\(<bdi>([^<]+)</bdi>\)</span>'),
    "type": re.compile(r'<dd class="type">([^<]+)</dd>'),

    # Founded (napr. Founded: 1996-09 in London, Area: United Kingdom)
    "founded": re.compile(r'Founded:\s*([0-9\-]+)\s*in\s*([^,<>]+)', re.I),
    "area": re.compile(r'Area:\s*([^,<>"\n]+)', re.I),
    "isni": re.compile(r'isni\.org/([0-9X]+)', re.I),

    "rating": re.compile(r'<span class="current-rating" style="width:(\d+)%">([\d.]+)</span>'),

    # genres and other tags
    "genres_block": re.compile(r'<h3>Genres</h3><div class="genre-list">(.*?)</div>', re.S),
    "other_tags_block": re.compile(r'<h3>Other tags</h3><div id="sidebar-tag-list">(.*?)</div>', re.S),
    "tags_items": re.compile(r'<p[^>]*>(?!\(none\))(?:\s*<a [^>]*>)?([^<\n]+)(?:</a>)?\s*</p>', re.S),
    "anchor_texts": re.compile(r'<a [^>]*>([^<]+)</a>'),
    "has_none": re.compile(r'\(none\)', re.I),

    # External links
    "ext_links": re.compile(r'<ul class="external_links">(.*?)</ul>', re.S),
    "ext_item": re.compile(r'<a href="([^"]+)"[^>]*>([^<]+)</a>'),

    "wikipedia_link": re.compile(
        r'<a href="(https?://[a-z]+\.wikipedia\.org/[^"]+)"[^>]*>Continue reading at Wikipedia',
        re.I
    ),

    # Releases in discography table
    "release": re.compile(
        r'<tr.*?><td class="c">(\d{4}|—)</td>.*?<a class="wrap-anywhere" href="([^"]+)"><bdi>([^<]+)</bdi></a>.*?<td><bdi>.*?>([^<]+)</a>',
        re.S
    ),

    # Last updated
    "last_updated": re.compile(r'<p class="lastupdate">Last updated on ([^<]+)</p>')
}


def parse_profile(path):
    with open(path, encoding="utf-8") as f:
        html = f.read()

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
    m = PROFILE_RE["rating"].search(html)
    if m:
        data["rating_percent"] = m.group(1)
        data["rating_value"] = float(m.group(2))
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

    # External links (as name + URL)
    links = []
    ext_block = PROFILE_RE["ext_links"].search(html)
    if ext_block:
        for url, name in PROFILE_RE["ext_item"].findall(ext_block.group(1)):
            links.append({"name": name.strip(), "url": url})
    data["external_links"] = links

    wiki_cached = re.search(r'"cachedWikipediaExtract":(null|".+?")', html)
    if wiki_cached:
        if wiki_cached.group(1) == "null":
            data["wikipedia_text"] = None
            data["wikipedia_note"] = "Wikipedia extract not included (loaded dynamically)"
        else:
            data["wikipedia_text"] = wiki_cached.group(1).strip('"')
            data["wikipedia_note"] = None

    # Releases
    releases = []
    for year, href, title, artist in PROFILE_RE["release"].findall(html):
        releases.append({
            "year": year.strip(),
            "title": title.strip(),
            "artist": artist.strip(),
            "url": "https://musicbrainz.org" + href
        })
    data["releases"] = releases

    # Last updated
    data["last_updated"] = get("last_updated")

    return data


# use for single profile parsing test

# if __name__ == "__main__":
#     profile_path = "raw_html/cc197bad-dc9c-440d-a5b5-d52ba2e14234/profile.html"
#     if os.path.exists(profile_path):
#         parsed = parse_profile(profile_path)
#         # save to file
#         with open("parsed_profile.json", "w", encoding="utf-8") as f:
#             json.dump(parsed, f, ensure_ascii=False, indent=4)
