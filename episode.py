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
    "Marcus": ("Puck", "single, travels solo, big basketball and football fan, quick jokes"),
    "Elena": ("Aoede", "married with two kids in Brooklyn, sharp analyst, loves baseball and soccer, teases Marcus"),
}
H1, H2 = list(HOSTS)
LAUNCH_MONDAY = dt.date(2026, 11, 16)  # week 1 -> Marcus tells the travel story


def http_json(url, body, headers, timeout=600):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
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
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 15}]
    r = http_json("https://api.anthropic.com/v1/messages", body,
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    u = r["usage"]
    print(f"   tokens in={u['input_tokens']} out={u['output_tokens']} stop={r.get('stop_reason')} "
          f"blocks={sorted({b['type'] for b in r['content']})}")
    return "".join(b.get("text", "") for b in r["content"] if b["type"] == "text").strip()


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

Output a plain list of short, verified facts. Exact scores, full player names, stat lines.
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
    return claude(
        f"""Write today's episode of "Last Night on Sports", a 5-minute daily sports podcast for listeners across the US.

Hosts (AI characters, friends who live in NYC):
{personas}

Structure:
{travel}- Quick NYC weather + one local note from the hosts' city (~20 seconds, keep it light; the audience is national)
- Sports recap (~3 minutes): back-and-forth banter, reactions, friendly disagreements. Lead with the biggest stories.
- Close (~30 seconds): tease tomorrow's games, sign off.

Rules:
- Use ONLY the facts below. Never invent scores, stats, quotes, or results. Skip anything marked [UNCONFIRMED].
- Exactly 650-750 words of dialogue (that's 5 minutes spoken).
- Sound like two friends over coffee, not newsreaders. Short lines, interruptions, laughs written as (laughs).
- Write numbers how people say them ("one-oh-eight to one-oh-two" is fine, or "108 to 102").
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


def speak(script, out_path):
    print("4/4 Recording voices...")
    lines = [l.strip() for l in script.splitlines() if re.match(rf"^({H1}|{H2}):", l.strip())]
    chunks, cur = [], []
    for l in lines:  # ~1 minute per TTS call keeps each request well under the model's output limit
        cur.append(l)
        if sum(len(x) for x in cur) > 900:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    voices = [{"speaker": n, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}} for n, (v, _) in HOSTS.items()]
    pcm = b""
    for i, c in enumerate(chunks, 1):
        text = ("Read this as a lively, warm morning sports show between two friends in New York. "
                "Natural pace, real reactions.\n\n" + "\n".join(c))
        r = http_json(f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent",
                      {"contents": [{"parts": [{"text": text}]}],
                       "generationConfig": {"responseModalities": ["AUDIO"],
                                            "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": voices}}}},
                      {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        pcm += base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        pcm += b"\x00" * 24000  # 0.5 s pause between chunks
        print(f"   part {i}/{len(chunks)} done")
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    return len(pcm) / 48000


if __name__ == "__main__":
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today() - dt.timedelta(days=1)
    os.makedirs(os.path.join(HERE, "episodes"), exist_ok=True)
    base = os.path.join(HERE, "episodes", f"{day + dt.timedelta(days=1)}")
    facts = research(day) + "\n\nNYC WEATHER FORECAST (National Weather Service, for this morning): " + nyc_weather()
    open(base + "_facts.txt", "w", encoding="utf-8").write(facts)
    script, meta = fact_check(write_script(day, facts), facts)
    open(base + "_script.txt", "w", encoding="utf-8").write(script)
    json.dump(meta, open(base + "_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    secs = speak(script, base + ".wav")
    print(f"\nDone: {base}.wav  ({secs / 60:.1f} min, {len(script.split())} words)")
