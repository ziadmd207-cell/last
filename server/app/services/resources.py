"""
Resources fetcher - YouTube (Data API v3 with view/like quality ranking,
HTML-scraping fallback) + Docs via HTML parsing + ranking.
"""
import httpx
import re
import time
import urllib.parse

try:
    from dotenv import load_dotenv
    import os as _os
    load_dotenv(_os.path.join(_os.path.dirname(__file__), "../../.env"))
except Exception:
    pass

_cache: dict = {}
TTL = 24 * 60 * 60

# Quality gates: skip dead/unwatched videos so lessons link real content
MIN_VIEWS = 1000
MIN_LIKES = 5

# No hardcoded API keys: DB admin_settings > YOUTUBE_API_KEY env wins.
# Empty key falls back to HTML scraping (no quota). Never commit a real key.
YOUTUBE_API_FALLBACK_KEY = ""


def _yt_key() -> str:
    import os
    try:
        from ..core.database import engine
        from sqlmodel import Session
        from ..models import AdminSetting
        with Session(engine) as session:
            s = session.get(AdminSetting, "default")
            if s and s.youtube_api_key:
                return s.youtube_api_key.strip()
    except Exception:
        pass
    try:
        from ..core.config import settings
        return (os.getenv("YOUTUBE_API_KEY", "") or settings.youtube_api_key or YOUTUBE_API_FALLBACK_KEY).strip()
    except Exception:
        return (os.getenv("YOUTUBE_API_KEY", "") or YOUTUBE_API_FALLBACK_KEY).strip()


_STOPWORDS = {
    "في", "من", "على", "الي", "إلي", "إلى", "عن", "مع", "و", "أو", "ما", "لا", "كل",
    "تعلم", "شرح", "مقدمة", "اساسيات", "أساسيات", "كورس", "دورة", "كاملة", "كامل",
    "the", "a", "an", "to", "of", "for", "in", "on", "and", "with", "learn",
    "learning", "course", "tutorial", "tutorials", "introduction", "intro",
    "complete", "full", "beginners", "beginner", "crash", "basics", "guide",
}


def _rel_words(text: str) -> set:
    return {w for w in re.findall(r"[\w\u0600-\u06FF]{3,}", (text or "").lower())} - _STOPWORDS


def _relevance(title: str, *contexts: str) -> int:
    """Shared meaningful words between a video title and our topic."""
    tw = _rel_words(title)
    if not tw:
        return 0
    score = 0
    for ctx in contexts:
        score += len(tw & _rel_words(ctx))
    return score


async def _search_youtube_api(query: str, lang: str, max_results=3, must_match: str = ""):
    """YouTube Data API v3: order by views, then rank by views+likes.

    Costs ~101 quota units per call (search=100 + videos=1); results are
    cached 24h per node so repeated lesson opens cost nothing.
    Raises/falls back silently (returns []) on quota/key errors.
    """
    key = _yt_key()
    if not key:
        return []
    q = f"{query} {'شرح عربي' if lang == 'ar' else 'tutorial'}"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            s = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "key": key, "q": q, "part": "snippet", "type": "video",
                    "maxResults": 10, "order": "viewCount",
                    "relevanceLanguage": "ar" if lang == "ar" else "en",
                    "safeSearch": "moderate", "videoEmbeddable": "true",
                },
            )
            if s.status_code != 200:
                print(f"youtube api search {s.status_code}: {s.text[:200]}")
                return []
            ids = [it["id"]["videoId"] for it in s.json().get("items", []) if it.get("id", {}).get("videoId")]
            if not ids:
                return []
            v = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"key": key, "id": ",".join(ids), "part": "statistics,snippet,contentDetails"},
            )
            if v.status_code != 200:
                print(f"youtube api videos {v.status_code}: {v.text[:200]}")
                return []
            out = []
            for it in v.json().get("items", []):
                vid = it.get("id", "")
                stats = it.get("statistics", {}) or {}
                try:
                    views = int(stats.get("viewCount", 0) or 0)
                except Exception:
                    views = 0
                try:
                    likes = int(stats.get("likeCount", 0) or 0)
                except Exception:
                    likes = 0
                # Quality gates: must be actually watched AND liked
                if views < MIN_VIEWS or likes < MIN_LIKES:
                    continue
                title = ((it.get("snippet", {}) or {}).get("title")) or query
                dur = _parse_iso8601_duration(((it.get("contentDetails", {}) or {}).get("duration")) or "")
                out.append({
                    "videoId": vid, "views": views, "likes": likes,
                    "duration_sec": dur, "duration_display": _fmt_duration(dur),
                    "relevance": _relevance(title, query, must_match),
                    "url": f"https://www.youtube.com/watch?v={vid}", "title": title,
                })
            # Rank: topic relevance FIRST (a viral driving video must never win
            # an AI lesson), then views, then likes as engagement proof.
            if must_match and any(v.get("relevance", 0) > 0 for v in out):
                out = [v for v in out if v.get("relevance", 0) > 0]
            out.sort(key=lambda x: (x.get("relevance", 0), x["views"], x["likes"]), reverse=True)
            return out[:max_results]
    except Exception as e:
        print(f"youtube api error: {e}")
        return []

def _cache_key(node_id, lang, style):
    return f"{node_id}:{lang}:{style}"

async def _validate_youtube_video(vid: str) -> dict | None:
    """Validate via oEmbed - returns title if valid, None if unavailable."""
    try:
        async with httpx.AsyncClient(timeout=5, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json")
            if r.status_code == 200:
                j = r.json()
                return {"title": j.get("title", ""), "valid": True}
            return None
    except:
        return None

async def _search_youtube_no_key(query: str, lang: str, max_results=3):
    """Fetch youtube search results without API key via HTML parsing + oEmbed validation."""
    q = urllib.parse.quote(f"{query} {'شرح عربي' if lang=='ar' else ''}")
    url = f"https://www.youtube.com/results?search_query={q}"
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []
            text = r.text
            vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', text)
            views = re.findall(r'"viewCountText":\{"simpleText":"([^"]+)"\}', text)
            # Also try to extract titles
            titles = re.findall(r'"title":\{"runs":\[{"text":"([^"]+)"\}\]', text)
            # Deduplicate preserving order
            seen = set()
            uniq_vids = []
            for vid in vids:
                if vid not in seen and len(uniq_vids) < max_results * 5:
                    seen.add(vid)
                    uniq_vids.append(vid)
            # Validate each via oEmbed to ensure it actually exists and is playable
            validated = []
            for idx, vid in enumerate(uniq_vids):
                info = await _validate_youtube_video(vid)
                if not info:
                    continue
                vc = views[idx] if idx < len(views) else "0"
                num = _parse_views(vc)
                # Use real title from oEmbed if available
                title = info.get("title") or (titles[idx] if idx < len(titles) else f"{query}")
                validated.append({"videoId": vid, "views": num, "likes": 0, "url": f"https://www.youtube.com/watch?v={vid}", "title": title})
                if len(validated) >= max_results:
                    break
            validated.sort(key=lambda x: x["views"], reverse=True)
            return validated[:max_results]
    except Exception as e:
        print(f"youtube search error: {e}")
        return []

async def _search_youtube_best(query: str, lang: str, max_results=3, must_match: str = "", exclude: tuple = ()):
    """API first (relevance+view/like-ranked), HTML-scraping fallback when key/quota fails."""
    got = await _search_youtube_api(query, lang, max_results + len(exclude), must_match)
    got = [v for v in got if v.get("videoId") not in (exclude or ())]
    if got:
        return got[:max_results]
    fb = await _search_youtube_no_key(query, lang, max_results + len(exclude))
    fb = [v for v in fb if v.get("videoId") not in (exclude or ())]
    return fb[:max_results]


def _video_id_from_url(url: str) -> str | None:
    """Extract an 11-char YouTube id from watch/embed/shorts/youtu.be URLs."""
    if not url:
        return None
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else None


def _is_youtube_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return ("youtube.com" in u or "youtu.be" in u) and _video_id_from_url(url) is not None


def _parse_iso8601_duration(iso: str) -> int:
    """PT1H2M3S -> seconds (YouTube contentDetails.duration)."""
    if not iso:
        return 0
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso.strip())
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def _fmt_duration(sec: int) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    mi, s = divmod(rem, 60)
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


_embed_cache: dict = {}
_meta_cache: dict = {}


async def _video_meta(vid: str) -> dict:
    """One cached videos.list call: embeddability + duration + title."""
    if not vid:
        return {"embeddable": False, "duration_sec": 0, "title": None}
    if vid in _meta_cache:
        return _meta_cache[vid]
    meta = {"embeddable": False, "duration_sec": 0, "title": None}
    key = _yt_key()
    try:
        if key:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={"key": key, "id": vid, "part": "status,contentDetails,snippet"},
                )
                if r.status_code == 200:
                    items = r.json().get("items", [])
                    if items:
                        it = items[0]
                        st = it.get("status", {}) or {}
                        meta["embeddable"] = bool(st.get("embeddable", False)) and st.get("privacyStatus") in ("public", "unlisted")
                        meta["duration_sec"] = _parse_iso8601_duration(((it.get("contentDetails", {}) or {}).get("duration")) or "")
                        meta["title"] = ((it.get("snippet", {}) or {}).get("title"))
        else:
            meta["embeddable"] = (await _validate_youtube_video(vid)) is not None
    except Exception as e:
        print(f"video meta error: {e}")
    _meta_cache[vid] = meta
    return meta


async def _batch_embeddable(vids: list) -> set:
    """One videos.list call for many ids -> set of playable videoIds."""
    vids = [v for v in dict.fromkeys(vids or []) if v]
    if not vids:
        return set()
    known = {v for v in vids if v in _embed_cache}
    unknown = [v for v in vids if v not in _embed_cache]
    ok = {v for v in known if _embed_cache[v]}
    key = _yt_key()
    if unknown and key:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                # 50 ids per call max
                for i in range(0, len(unknown), 50):
                    chunk = unknown[i:i + 50]
                    r = await client.get(
                        "https://www.googleapis.com/youtube/v3/videos",
                        params={"key": key, "id": ",".join(chunk), "part": "status"},
                    )
                    if r.status_code != 200:
                        print(f"youtube batch status {r.status_code}")
                        continue
                    for it in r.json().get("items", []):
                        st = it.get("status", {}) or {}
                        good = bool(st.get("embeddable", False)) and st.get("privacyStatus") in ("public", "unlisted")
                        _embed_cache[it.get("id", "")] = good
                        if good:
                            ok.add(it.get("id", ""))
        except Exception as e:
            print(f"youtube batch error: {e}")
    if unknown and not key:
        for v in unknown:
            good = (await _validate_youtube_video(v)) is not None
            _embed_cache[v] = good
            if good:
                ok.add(v)
    return ok


async def filter_playable(resources: list) -> list:
    """Drop video entries that YouTube won't play in our iframe."""
    vids = [_video_id_from_url(r.get("url", "")) for r in (resources or []) if r.get("type") == "video"]
    playable = await _batch_embeddable(vids)
    return [r for r in (resources or []) if r.get("type") != "video" or _video_id_from_url(r.get("url", "")) in playable]


async def is_embeddable(vid: str) -> bool:
    """True only if YouTube will actually play this video in our iframe.

    Uses the Data API status (embeddable + public/unlisted). Without a key,
    falls back to oEmbed existence (can't prove embeddability, but proves
    the video exists and isn't deleted/private).
    """
    if not vid:
        return False
    if vid in _embed_cache:
        return _embed_cache[vid]
    ok = (await _video_meta(vid)).get("embeddable", False)
    _embed_cache[vid] = ok
    return ok


async def get_video_duration(vid: str) -> int:
    """Duration in seconds (0 when unknown). Cached, 1 quota unit on miss."""
    if not vid:
        return 0
    return int((await _video_meta(vid)).get("duration_sec", 0) or 0)


async def resolve_lesson_video(candidate_url: str, node_title: str, lang: str, goal: str = "", exclude_url: str = ""):
    """YouTube-only, playable, ON-TOPIC video resolution.

    Returns (video_url, video_title or None, duration_sec). Rejects
    non-YouTube URLs, non-embeddable/deleted videos AND off-topic titles
    (relevance to node title + track goal), replacing them with a ranked
    search hit. exclude_url skips the current video so "regenerate" always
    brings a DIFFERENT video about the same topic.
    Returns ("", None, 0) when nothing playable is found (the UI then shows
    "preparing" instead of a dead player).
    """
    excluded = tuple(v for v in [_video_id_from_url(exclude_url or "")] if v)
    topic = f"{node_title} {goal}".strip()
    if _is_youtube_url(candidate_url or "") and not excluded:
        vid = _video_id_from_url(candidate_url)
        if vid:
            meta = await _video_meta(vid)
            if meta.get("embeddable") and _relevance(meta.get("title") or "", node_title, goal) > 0:
                return candidate_url, meta.get("title"), int(meta.get("duration_sec", 0) or 0)
    alt = await _search_youtube_best(f"{node_title} {goal} {lang}".strip(), lang, 3, must_match=topic, exclude=excluded)
    for v in alt:
        if await is_embeddable(v["videoId"]):
            dur = v.get("duration_sec") or await get_video_duration(v["videoId"])
            return v["url"], v.get("title"), int(dur or 0)
    return "", None, 0


def _parse_views(s: str) -> int:
    try:
        s = s.lower().replace(",", "").replace("views", "").strip()
        if "m" in s:
            return int(float(s.replace("m", "")) * 1_000_000)
        if "k" in s:
            return int(float(s.replace("k", "")) * 1000)
        # Arabic: "1.2 مليون"
        if "مليون" in s:
            return int(float(re.findall(r"[\d.]+", s)[0]) * 1_000_000) if re.findall(r"[\d.]+", s) else 0
        if "ألف" in s:
            return int(float(re.findall(r"[\d.]+", s)[0]) * 1000) if re.findall(r"[\d.]+", s) else 0
        num = re.findall(r"[\d.]+", s)
        return int(float(num[0])) if num else 0
    except:
        return 0

async def _search_docs_no_key(query: str, lang: str, max_results=3):
    """Search docs via DuckDuckGo HTML without API key."""
    q = urllib.parse.quote(f"{query} documentation {'عربي' if lang=='ar' else ''}")
    url = f"https://html.duckduckgo.com/html/?q={q}"
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []
            text = r.text
            # Extract urls: <a class="result__url" href="//duckduckgo.com/l/?uddg=https://...">
            urls = re.findall(r'uddg=(https?[^&"]+)', text)
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)</a>', text)
            results = []
            for idx, u in enumerate(urls):
                try:
                    u = urllib.parse.unquote(u)
                    # Prefer docs domains
                    score = 0
                    if any(d in u for d in ["developer.mozilla.org", "docs.python.org", "react.dev", "vuejs.org", "angular.io", "nodejs.org", "developer.android.com", "developer.apple.com"]):
                        score = 10
                    title = titles[idx].strip() if idx < len(titles) else query
                    results.append({"url": u, "title": title, "score": score})
                    if len(results) >= max_results * 2:
                        break
                except:
                    continue
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:max_results]
    except Exception as e:
        print(f"docs search error: {e}")
        return []

async def get_resources_for_node(node: dict, profile: dict, goal: str = "", exclude: tuple = (), force: bool = False) -> list:
    """Return resources list respecting learning_style and preferred_language.

    Videos are embed-checked (dead players never reach the UI), ranked
    (rank=1..n so the frontend readiness check works), and `exclude` skips
    already-seen videos so manual refresh always brings something new.
    force=True bypasses the 24h cache (manual "refresh" button).
    """
    lang = profile.get("preferred_language", "ar") if isinstance(profile, dict) else "ar"
    if lang not in ("ar", "en"):
        lang = "ar"
    style = profile.get("learning_style", "mixed") if isinstance(profile, dict) else "mixed"
    # Normalize style
    if style in ("video", "visual"):
        style = "video"
    elif style in ("reading", "hands_on"):
        style = "reading"
    else:
        style = "mixed"

    node_id = node.get("id", "unknown")
    cache_key = _cache_key(node_id, lang, style)
    now = time.time()
    use_cache = not force and not exclude
    if use_cache and cache_key in _cache and now - _cache[cache_key].get("_ts", 0) < TTL:
        return _cache[cache_key]["data"]

    query = f"{node.get('title','')} {node.get('objective','')[:60]}"
    topic = f"{node.get('title','')} {goal}".strip()
    excluded = set(exclude or ())
    resources = []

    try:
        if style == "video":
            vids = await _search_youtube_best(query, lang, 3 + len(excluded), must_match=topic, exclude=tuple(excluded))
            for v in vids:
                resources.append({"title": v["title"], "type": "video", "tier": "best_match", "url": v["url"], "duration_sec": v.get("duration_sec", 0), "duration_display": v.get("duration_display", "")})
        elif style == "reading":
            docs = await _search_docs_no_key(query, lang, 3)
            for d in docs:
                resources.append({"title": d["title"], "type": "docs", "tier": "best_match", "url": d["url"]})
        else:  # mixed -> 2+2
            vids = await _search_youtube_best(query, lang, 2 + len(excluded), must_match=topic, exclude=tuple(excluded))
            docs = await _search_docs_no_key(query, lang, 2)
            for v in vids:
                resources.append({"title": v["title"], "type": "video", "tier": "best_match", "url": v["url"], "duration_sec": v.get("duration_sec", 0), "duration_display": v.get("duration_display", "")})
            for d in docs:
                resources.append({"title": d["title"], "type": "docs", "tier": "best_match", "url": d["url"]})
    except Exception as e:
        print(f"get_resources error: {e}")

    # Drop dead players, then rank so frontend readiness (rank field) works
    resources = await filter_playable(resources)
    # Guarantee: every node carries at least one real YouTube video so the
    # roadmap view always has watchable embeds, whatever the style is.
    if not any(r.get("type") == "video" for r in resources):
        try:
            extra = await _search_youtube_best(query, lang, 1, must_match=topic)
            for v in extra:
                if await is_embeddable(v["videoId"]):
                    resources.insert(0, {"title": v["title"], "type": "video", "tier": "best_match", "url": v["url"], "duration_sec": v.get("duration_sec", 0), "duration_display": v.get("duration_display", "")})
                    break
        except Exception as e:
            print(f"video guarantee fail: {e}")
    for i, r in enumerate(resources):
        r["rank"] = i + 1

    # Cache even if empty (negative cache short)
    if use_cache:
        _cache[cache_key] = {"data": resources, "_ts": now}
    return resources
