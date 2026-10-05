#!/usr/bin/env python
"""Build a Magic: The Gathering strategy knowledge base from free, official sources.

Primary source: Reid Duke's "Level One" — the complete strategy course on
magic.wizards.com (46 articles, official, free, ordered from mana basics through role
assignment, damage racing, mulligans, sequencing). That ordering matters: it is a
curriculum, not a glossary.

Usage:
    python tools/fetch_kb.py [--out kb] [--delay 1.5]

Writes kb/level_one/NN-slug.md per article plus kb/INDEX.md, and kb/SOURCES.md listing
everything used with its licence/attribution.
"""
import argparse
import html
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYLLABUS = "https://magic.wizards.com/en/news/feature/level-one-full-course-2015-10-05"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

# supplementary essays that define the vocabulary the Level One articles assume
EXTRA = [
    ("whos-the-beatdown", "https://articles.starcitygames.com/articles/whos-the-beatdown/",
     "Mike Flores, 'Who's the Beatdown?' (1999) — the canonical role-assignment essay"),
    ("eight-core-principles-of-whos-the-beatdown",
     "https://articles.starcitygames.com/articles/eight-core-principles-of-whos-the-beatdown/",
     "StarCityGames, eight core principles of Who's the Beatdown"),
]


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def strip_html(s):
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|li|h[1-6]|div)>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def article_body(page):
    """Pull the article text out of a magic.wizards.com news page."""
    m = re.search(r'class=["\'][^"\']*article-body[^"\']*["\'][^>]*>(.*?)'
                  r'(?=<div class=["\'](?:article-|footer|related)|</article>|$)', page, re.S | re.I)
    if not m:
        return ""
    return strip_html(m.group(1))


def syllabus_links(page):
    urls = re.findall(r'href=["\'](https?://magic\.wizards\.com/en/articles/archive/[^"\']+)["\']', page)
    out, seen = [], set()
    for u in urls:
        u = u.replace("http://", "https://")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def slug(u):
    return u.rstrip("/").split("/")[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "kb"))
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()

    os.makedirs(os.path.join(args.out, "level_one"), exist_ok=True)

    print("fetching the syllabus: %s" % SYLLABUS)
    page = get(SYLLABUS)
    links = syllabus_links(page)
    print("articles listed: %d" % len(links))

    index = ["# Magic: The Gathering strategy knowledge base", "",
             "Source: **Level One** by Reid Duke, magic.wizards.com (official, free).",
             "Ordered as the course is taught — mana, card advantage, attacking and blocking,",
             "tempo, archetypes, then role assignment / damage racing / mulligans.", ""]
    got, failed = 0, []
    for i, u in enumerate(links, 1):
        name = "%02d-%s" % (i, slug(u))
        path = os.path.join(args.out, "level_one", name + ".md")
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            print("  [%02d/%d] cached %s" % (i, len(links), name))
            index.append("%d. [%s](level_one/%s.md)" % (i, slug(u), name))
            got += 1
            continue
        try:
            body = article_body(get(u))
        except Exception as e:
            failed.append((u, str(e)[:80]))
            print("  [%02d/%d] FAILED %s (%s)" % (i, len(links), slug(u), str(e)[:60]))
            time.sleep(args.delay)
            continue
        if len(body) < 1500:
            failed.append((u, "body too short (%d chars)" % len(body)))
            print("  [%02d/%d] thin %s (%d chars)" % (i, len(links), slug(u), len(body)))
            time.sleep(args.delay)
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# %s\n\nSource: %s\n\n%s\n" % (slug(u), u, body))
        index.append("%d. [%s](level_one/%s.md)" % (i, slug(u), name))
        print("  [%02d/%d] %s  %d chars" % (i, len(links), name, len(body)))
        got += 1
        time.sleep(args.delay)

    # supplementary essays
    index += ["", "## Supplementary essays (the vocabulary the course assumes)", ""]
    for name, u, note in EXTRA:
        path = os.path.join(args.out, "level_one", "X-" + name + ".md")
        try:
            body = strip_html(get(u))
            body = re.sub(r"\n{3,}", "\n\n", body)
            if len(body) > 1500:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("# %s\n\n%s\n\nSource: %s\n\n%s\n" % (name, note, u, body))
                index.append("- [%s](level_one/X-%s.md) — %s" % (name, name, note))
                print("  extra: %s  %d chars" % (name, len(body)))
                got += 1
            else:
                failed.append((u, "extra body too short (%d)" % len(body)))
        except Exception as e:
            failed.append((u, str(e)[:80]))
            print("  extra FAILED %s (%s)" % (name, str(e)[:60]))
        time.sleep(args.delay)

    with open(os.path.join(args.out, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index) + "\n")

    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(args.out) for f in fs if f.endswith(".md"))
    print()
    print("wrote %d documents, %.0f KB of text, to %s" % (got, total / 1024.0, args.out))
    if failed:
        print("failures (%d):" % len(failed))
        for u, why in failed:
            print("  %s -> %s" % (u, why))


if __name__ == "__main__":
    main()
