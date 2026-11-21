"""Builds feed.xml (the podcast RSS feed) from the MP3s in episodes/."""
import datetime as dt, glob, json, os, subprocess
from email.utils import format_datetime
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://last-night-on-sports.eudismatos.workers.dev"
TITLE = "Last Night On Sports"
EMAIL = "eudismatos@yahoo.es"
AUTHOR = "Last Night On Sports"
DESCRIPTION = (
    "Your daily 5-minute sports recap. Every morning, Marcus and Elena break down last night's biggest games, "
    "scores and storylines across the NFL, NBA, NHL, MLB, college sports, soccer and more, like two friends "
    "talking sports over coffee. New episodes every morning. "
    "Note: the hosts are AI-generated voices, and episodes are produced with AI tools and fact-checked "
    "against the day's results."
)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    s = int(float(out or 0))
    return f"{s // 60}:{s % 60:02d}"


def item(mp3):
    date = os.path.basename(mp3)[:10]  # YYYY-MM-DD (the morning it airs)
    d = dt.date.fromisoformat(date)
    meta = {}
    meta_path = os.path.join(HERE, "episodes", date + "_meta.json")  # private notes, not published
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
    title = f"{TITLE} {d.month}/{d.day}/{d:%y}"
    if meta.get("headline"):
        title += f": {meta['headline']}"
    summary = meta.get("summary") or f"Last night's biggest sports stories, recapped in 5 minutes."
    pub = dt.datetime(d.year, d.month, d.day, 10, 30, tzinfo=dt.timezone.utc)
    url = f"{SITE}/episodes/{os.path.basename(mp3)}"
    return f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(summary + " Hosts are AI-generated voices.")}</description>
      <enclosure url="{url}" length="{os.path.getsize(mp3)}" type="audio/mpeg"/>
      <guid isPermaLink="false">lnos-{date}</guid>
      <pubDate>{format_datetime(pub)}</pubDate>
      <itunes:duration>{duration(mp3)}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
    </item>"""


def build():
    mp3s = sorted(glob.glob(os.path.join(HERE, "docs", "episodes", "*.mp3")), reverse=True)
    items = "\n".join(item(m) for m in mp3s)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{TITLE}</title>
    <link>{SITE}/</link>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
    <language>en-us</language>
    <description>{escape(DESCRIPTION)}</description>
    <itunes:summary>{escape(DESCRIPTION)}</itunes:summary>
    <itunes:author>{AUTHOR}</itunes:author>
    <itunes:owner><itunes:name>{AUTHOR}</itunes:name><itunes:email>{EMAIL}</itunes:email></itunes:owner>
    <itunes:image href="{SITE}/art/cover.jpg"/>
    <image><url>{SITE}/art/cover.jpg</url><title>{TITLE}</title><link>{SITE}/</link></image>
    <itunes:category text="Sports"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:new-feed-url>{SITE}/feed.xml</itunes:new-feed-url>
{items}
  </channel>
</rss>
"""
    open(os.path.join(HERE, "docs", "feed.xml"), "w", encoding="utf-8").write(xml)
    print(f"feed.xml written with {len(mp3s)} episode(s)")


if __name__ == "__main__":
    build()
