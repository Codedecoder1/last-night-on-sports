"""Daily sports podcast: research -> script -> fact-check -> voices -> WAV.

Usage: python episode.py            (episode about yesterday)
       python episode.py 2026-11-17 (episode about a specific date)
"""
import base64, datetime as dt, json, os, re, sys, urllib.error, urllib.request, wave

HERE = os.path.dirname(os.path.abspath(__file__))
for line in open(os.path.join(HERE, ".env"), encoding="utf-8-sig"):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

CLAUDE_MODEL = "claude-sonnet-5-5"
TTS_MODEL = "gemini-2.5-flash-preview-tts"
HOSTS = {  # name -> (Gemini voice, persona)
    "Marcus": ("Charon", "single, travels solo, big basketball and football fan, quick jokes"),
    "Elena": ("Aoede", "married with two kids in Brooklyn, sharp analyst, loves baseball and soccer, teases Marcus"),
}
H1, H2 = list(HOSTS)
LAUNCH_MONDAY = dt.date(2026, 11, 16)  # week 1 -> Marcus tells the travel story


def http_json(url, body, headers, timeout=600, fatal=True):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        if not fatal:
            raise
        sys.exit(f"HTTP {e.code} from {url.split('/')[2]}: {e.read().decode()[:800]}")


def nyc_weather():
    """Official NWS forecast for Manhattan (free, no key)."""
    hdr = {"User-Agent": "daily-sports-podcast", "Accept": "application/geo+json"}
    get = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=30))
    try:
        url = get("https://api.weather.gov/points/40.7812,-73.9665")["properties"]["forecast"]  # Central Park
        periods = get(url)["properties"]["periods"][:2]
        return " ".join(f"{p['name']}: {p['detailedForecast']}" for p in periods)
    except Exception as ex:
        print("   weather unavailable:", ex)
        return "[UNCONFIRMED] weather unavailable"


def claude(prompt, system="", search=False, max_tokens=20000):
    body = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": prompt}]}
    if search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    r = http_json("https://api.anthropic.com/v1/messages", body,
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    u = r["usage"]
    print(f"   tokens in={u['input_tokens']} out={u['output_tokens']} stop={r.get('stop_reason')} "
          f"blocks={sorted({b['type'] for b in r['content']})}")
    return "".join(b.get("text", "") for b in r["content"] if b["type"] == "text").strip()


def producer_notes(air_date):
    """Lines in notes.txt like '2026-11-19 | Grand Theft Auto VI comes out today' for that air date."""
    path = os.path.join(HERE, "notes.txt")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        if "|" in line and not line.lstrip().startswith("#"):
            d, note = line.split("|", 1)
            if d.strip() == air_date.isoformat():
                out.append(note.strip())
    return out


def research(day):
    print(f"1/4 Researching sports + NY news for {day:%A %B %d, %Y}...")
    return claude(
        f"""Search the web for what happened on {day:%A, %B %d, %Y} (US time). Collect FACTS ONLY:

1. SPORTS: final scores and key results in US-relevant sports from that day: NFL, NBA, NHL, MLB, MLS,
   college football and basketball, WNBA, NWSL, plus big global events (Premier League, Champions League, F1,
   tennis, golf, UFC/boxing). Priority order: championships, record-breaking performances, league leaders and
   star players, everything else. Cover the biggest national stories first. Also include New York teams (Knicks, Nets, Giants, Jets, Yankees, Mets, Rangers,
   Islanders, Liberty, NYCFC, Red Bulls) whenever they played. Note top storylines (injuries, trades).
2. NEW YORK: today's NYC weather forecast and 1-2 big local news items.
3. TOMORROW: notable games scheduled for the next day.

SEARCH BUDGET: you have at most 6 searches. Use broad roundups: one scoreboard/recap page per league
(e.g. "NBA scores {day:%B %d %Y}", "NHL scores {day:%B %d %Y}"), not one search per game.

DATE CHECK (critical): only use results from games played on {day:%B %d, %Y}, the {day.year} season/year.
Ignore articles from the same day in other years, and older or newer games. If a source's date is unclear,
leave the result out. "Tomorrow" means {day + dt.timedelta(days=1):%A, %B %d, %Y}.

Output a plain list of short, verified facts. Exact scores, full player names, stat lines.
Start every sports fact with the game date in YYYY-MM-DD form.
Mark anything you could not confirm with [UNCONFIRMED]. Do not write commentary.""",
        search=True, max_tokens=16000)


def write_script(day, facts):
    print("2/4 Writing the script...")
    monday = (day + dt.timedelta(days=1)).weekday() == 0  # episode airs the morning after `day`
    travel = ""
    if monday:
        week = ((day + dt.timedelta(days=1)) - LAUNCH_MONDAY).days // 7
        teller = H1 if week % 2 == 0 else H2
        travel = (f"It's Monday: OPEN with ~1 minute where {teller} tells a short, vivid, invented story "
                  f"about their weekend trip (fits their persona), with the other host reacting.\n")
    personas = "\n".join(f"- {n}: {p}" for n, (_, p) in HOSTS.items())
    air = day + dt.timedelta(days=1)
    notes = producer_notes(air)
    must = ""
    if notes:
        must = ("- MUST MENTION naturally somewhere in the episode (verified by the producer):\n"
                + "\n".join(f"  * {n}" for n in notes) + "\n")
    return claude(
        f"""Write today's episode of "Last Night on Sports", a 5-minute daily sports podcast for listeners across the US.
Today (air date) is {air:%A, %B %d, %Y}. "Last night" means {day:%A, %B %d, %Y}. Only talk about games from last night.

Hosts (AI characters, friends who live in NYC):
{personas}

Structure:
{travel}- Quick NYC weather + one local note from the hosts' city (~20 seconds, keep it light; the audience is national)
- Sports recap (~3 minutes): back-and-forth banter, reactions, friendly disagreements. Lead with the biggest stories.
- Close (~30 seconds): tease tomorrow's games, sign off.

Rules:
{must}- Use ONLY the facts below. Never invent scores, stats, quotes, or results. Skip anything marked [UNCONFIRMED].
- Length follows the news: about 450-750 words (3-5 minutes). Busy night = longer; quiet night = shorter. Never pad or repeat to fill time.
- Sound like two friends over coffee, not newsreaders. Short lines, interruptions, laughs written as (laughs).
- Write ALL numbers, scores, times and percentages out in words, exactly as spoken ("one-oh-eight to one-oh-two", "seventy percent", "one p.m.", "thirty-one points"). No digits, no symbols like % or & (the voice engine skips them).
- Output ONLY dialogue lines in the form "{H1}: ..." / "{H2}: ...". No titles, no stage directions on their own line.

FACTS:
{facts}""")


def fact_check(script, facts):
    print("3/4 Fact-checking every score and name...")
    out = claude(
        f"""You are a strict fact-checker for a sports podcast. Compare EVERY score, name, stat, team, and claim in
the SCRIPT against the FACTS. Fix anything that does not match the facts exactly; remove claims that are not in
the facts. Keep everything else (tone, jokes, length) unchanged.

Return the corrected script between <script></script> tags, then a list of changes between <changes></changes>.
Then write, based ONLY on the corrected script:
- <headline></headline>: the episode's top story in 3-7 punchy words, Title Case, no date, no quotes
  (e.g. Brunson Buries the Raptors). It must be 100% accurate.
- <summary></summary>: 1-2 sentences for the episode description listing the main stories covered.

FACTS:
{facts}

SCRIPT:
{script}""")
    fixed = re.search(r"<script>(.*?)</script>", out, re.S)
    changes = re.search(r"<changes>(.*?)</changes>", out, re.S)
    print("   changes:", (changes.group(1).strip() if changes else "none reported")[:1500])
    tag = lambda t: (m.group(1).strip() if (m := re.search(rf"<{t}>(.*?)</{t}>", out, re.S)) else "")
    meta = {"headline": tag("headline").strip('"'), "summary": tag("summary")}
    print("   headline:", meta["headline"])
    return (fixed.group(1).strip() if fixed else script), meta


def audio_coverage(pcm, lines, key):
    """Gemini listens to the audio; returns the share of script words found in its transcript."""
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    try:
        r = http_json("https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
                      {"contents": [{"parts": [
                          {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(buf.getvalue()).decode()}},
                          {"text": "Transcribe this audio word for word. Write every number as words exactly as spoken (e.g. one-oh-eight, seventy percent, one p.m.), never digits. Output only the transcript."}]}]},
                      key, timeout=180, fatal=False)
        heard = r["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as ex:
        print("   (check skipped:", ex, ")")
        return 1.0  # never block the episode because the checker failed
    norm = lambda s: re.findall(r"[a-z0-9]+", s.lower())
    said = " ".join(re.sub(rf"^({H1}|{H2}):", "", l) for l in lines)
    want, got = norm(re.sub(r"\(.*?\)", "", said)), set(norm(heard))
    return sum(w in got for w in want) / max(1, len(want))


def speak(script, out_path):
    print("4/4 Recording voices...")
    lines = [l.strip() for l in script.splitlines() if re.match(rf"^({H1}|{H2}):", l.strip())]
    chunks, cur = [], []
    for l in lines:  # ~1 minute per TTS call: shorter pieces get cut off less often
        cur.append(l)
        if sum(len(x) for x in cur) > 1100:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    voices = [{"speaker": n, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}} for n, (v, _) in HOSTS.items()]
    key = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    pcm = b""
    for i, c in enumerate(chunks, 1):
        text = ("Read this as a lively, warm morning sports show between two friends in New York. Marcus has a deep, confident, manly sports-radio voice; Elena is warm and sharp. "
                "Natural pace, real reactions. Read every word completely.\n\n" + "\n".join(c))
        best, best_score = None, -1
        for attempt in range(1, 4):  # up to 3 tries if words are missing
            r = http_json(f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent",
                          {"contents": [{"parts": [{"text": text}]}],
                           "generationConfig": {"responseModalities": ["AUDIO"],
                                                "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": voices}}}},
                          key)
            audio = base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            score = audio_coverage(audio, c, key)
            print(f"   part {i}/{len(chunks)} try {attempt}: {score:.0%} of words heard")
            if score > best_score:
                best, best_score = audio, score
            if score >= 0.95:
                break
        pcm += best + b"\x00" * 24000  # 0.5 s pause between chunks
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    return len(pcm) / 48000


if __name__ == "__main__":
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today() - dt.timedelta(days=1)
    os.makedirs(os.path.join(HERE, "episodes"), exist_ok=True)
    base = os.path.join(HERE, "episodes", f"{day + dt.timedelta(days=1)}")
    facts = research(day) + "\n\nNYC WEATHER FORECAST (National Weather Service, for this morning): " + nyc_weather()
    notes = producer_notes(day + dt.timedelta(days=1))
    if notes:
        facts += "\n\nPRODUCER NOTES (verified, keep in the script):\n" + "\n".join(f"- {n}" for n in notes)
    open(base + "_facts.txt", "w", encoding="utf-8").write(facts)
    script, meta = fact_check(write_script(day, facts), facts)
    open(base + "_script.txt", "w", encoding="utf-8").write(script)
    json.dump(meta, open(base + "_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    secs = speak(script, base + ".wav")
    print(f"\nDone: {base}.wav  ({secs / 60:.1f} min, {len(script.split())} words)")
