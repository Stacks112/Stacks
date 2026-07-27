"""Stacks static-page + sitemap + RSS generator.

Reads items.json and produces, for search engines and syndication:
  p/{id}.html   one crawlable article page per item (title, summary in
                all 3 languages, structured data) that also links into
                the app for humans.
  articles.html a plain hub page linking every article (crawl entry).
  sitemap.xml   every page with lastmod, for Google/Naver.
  robots.txt    allow all + sitemap pointer.
  feed.xml      Stacks' own RSS (enables feed readers + no-code auto-
                posting to X/Threads/Telegram via Zapier/IFTTT/Make).

Run by GitHub Actions whenever items.json changes, so the SEO layer and
the RSS feed stay in lockstep with published content. No external deps.
"""

import html
import json
import re
import hashlib
from datetime import datetime, timezone

BASE = "https://stacksdaily.com/"
SITE = "Stacks"
TAGLINE = {
    "ko": "전 세계 투자 고수들의 글을, 당신의 언어로",
    "en": "The world's best investing minds, in your language",
    "ja": "世界の投資の達人たちの記事を、あなたの言語で",
}
LANG_LABEL = {"ko": "한국어", "en": "English", "ja": "日本語"}
E = html.escape


def LD(obj):
    """Serialise a JSON-LD object for an inline <script> block.

    json.dumps escapes quotes and backslashes but never "<", so a title
    containing "</script>" closes the block early and everything after it is
    parsed as live HTML. Card text is produced by an automated publisher that
    reads third-party feeds, which is exactly the path an injected payload
    would take. Escaping the three characters as \\uXXXX keeps the JSON
    byte-identical to a parser while making it inert to the HTML tokenizer.
    """
    return (json.dumps(obj, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026"))


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{3,8}$")


def hexcolor(v, fallback):
    """A cover colour goes straight into a <style> block, so anything that is
    not a plain hex literal could close the declaration and add rules of its
    own (or a url() that phones home)."""
    v = str(v or "").strip()
    return v if HEX_RE.match(v) else fallback


def safe_href(u, fallback="#"):
    """Only plain http(s) links survive; javascript:/data: become dead."""
    s = str(u or "").strip()
    return s if re.match(r"^https?://", s, re.I) else fallback


NAME_ALIAS = {"메르": "메르 (ranto28)"}
def dispname(x):
    return NAME_ALIAS.get(x, x)


# ---- gist markers (see claude/prompts/publish-v4.3.md [4-E]) ----
# The publishing routine writes structure into the gist as line-leading
# markers so a new block type never needs a schema change. The app renders
# them in gistRich(); these pages have to do the same, or the raw markers show
# up as literal text on every SEO page and in every meta description.

# Emitted per page only when the body actually contains one of these blocks.
# Article pages inline their CSS, so an unconditional 1.3 KB would land in all
# 462 of them for the handful of cards that use a check or compare panel.
BLOCK_CSS = """.gist+.gist{margin-top:1em}
h2.gsub{font-size:17px;line-height:1.4;margin:1.6em 0 .5em;padding-left:9px;border-left:3px solid #3B82F6}
.srcq{margin:0 0 20px;padding:12px 16px;border-left:3px solid #3B82F6;background:#F6F7F9;border-radius:0 10px 10px 0}
.srcq blockquote{margin:0;quotes:none}
.srcq p{margin:0 0 6px;font-size:15px;line-height:1.62;color:#3E414B}
.srcq-c{font-size:12.5px;color:#8E93A0}
.srcq-c a{color:#8E93A0}
.chk{margin:16px 0;border:1px solid #ECEDF1;border-radius:12px;overflow:hidden}
.chk-g{display:flex;flex-wrap:wrap}
.chk-c{flex:1 1 33%;min-width:110px;padding:12px 10px;text-align:center;border-right:1px solid #ECEDF1}
.chk-c i{display:block;font-style:normal;font-size:11.5px;color:#8E93A0;margin-bottom:4px}
.chk-c b{display:block;font-size:18px}
.chk-n{margin:0;padding:11px 13px;border-top:1px solid #ECEDF1;font-size:14.5px;line-height:1.6}
.chk-s{margin:0;padding:0 13px 10px;font-size:12px;color:#8E93A0}
.cmp{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
.cmp-c{flex:1 1 240px;padding:12px 14px;border:1px solid #ECEDF1;border-radius:12px}
.cmp-c.cmp-b{border-color:#3B82F6}
.cmp-c i{display:block;font-style:normal;font-size:11.5px;font-weight:800;color:#8E93A0;margin-bottom:6px}
.cmp-c p{margin:0;font-size:14.5px;line-height:1.6}
.cmp-vs{align-self:center;width:32px;height:32px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:12px;color:#fff;background:linear-gradient(135deg,#EF4444,#3B82F6)}
.gimg{margin:16px 0}
.gimg img{display:block;width:100%;max-width:520px;border:1px solid #ECEDF1;border-radius:12px;background:#fff}
.gimg figcaption{margin-top:6px;font-size:12px;color:#8E93A0}
.gimg figcaption a{color:#8E93A0}
.gref{margin:6px 0 14px;font-size:13px}
.gref a{color:#8E93A0}
.gcardw{margin:12px 0 16px;max-width:520px}
.gcard{position:relative;display:block;border:1px solid #ECEDF1;border-radius:14px;overflow:hidden;text-decoration:none;background:#F6F7F9}
.gcard img{display:block;width:100%;max-height:250px;object-fit:cover}
.gcard-t{position:absolute;left:10px;right:10px;bottom:10px;padding:5px 10px;border-radius:8px;background:rgba(0,0,0,.65);color:#fff;font-size:13px;line-height:1.4;font-weight:600}
.gcard-src{margin-top:6px;font-size:12px;color:#8E93A0}
@media(prefers-color-scheme:dark){.srcq,.cmp-c{background:#1A1B21}.srcq p{color:#C9CDD6}
  .chk,.chk-c,.chk-n,.cmp-c{border-color:#26272E}.otherlang{border-color:#26272E}}"""


def block_css_for(body):
    if not any(k in body for k in ('class="gsub"', 'class="srcq"', 'class="chk"', 'class="cmp"', 'class="gimg"', 'class="gref"', 'class="gcard')):
        return ""
    return BLOCK_CSS


def strip_markers(text):
    """Plain prose. Subheadings keep their text (they are real sentences);
    the data rows of a check/compare block are dropped, since a description
    made of "4.71%|2.28%" reads as noise in a search result."""
    out = []
    for line in str(text or "").split("\n"):
        if line.startswith("## "):
            out.append(line[3:].strip())
        elif line.startswith("@@"):
            # any block marker: CHK, CMP, IMG, future ones
            continue
        else:
            out.append(line)
    return "\n".join(out)


def lang_text(v, lang):
    """sum3 and split were Korean-only when introduced, so older cards store a
    bare string. A string still means Korean (hidden in en/ja, as the app does);
    an {en,ko,ja} dict gives each language its own text. No migration needed.
    Mirrors langText() in index.html -- if one changes, change both."""
    if not v:
        return ""
    if isinstance(v, str):
        return v if lang == "ko" else ""
    return (v.get(lang) or "") if isinstance(v, dict) else ""


def sum3_block(item, lang, U):
    """The three-line standing of the story. The app shows this above 'why' on
    lab cards; the indexed page had nothing, which is where it is worth the most
    -- it is the part a search result can actually use."""
    if not item.get("lab"):
        return ""
    txt = lang_text(item.get("sum3"), lang)
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    if not lines:
        return ""
    return ('<div class="sum3"><b>%s</b><ul>%s</ul></div>'
            % (E(U["sum3"]), "".join("<li>%s</li>" % E(l) for l in lines)))


def split_block(item, lang, U):
    """What would have to happen for either reading to be right. Only on cards
    that do not resolve the argument, and never on lab cards -- the app hides it
    there too, so the two renderers agree."""
    if item.get("lab"):
        return ""
    txt = lang_text(item.get("split"), lang)
    if not txt:
        return ""
    body = "".join("<p>%s</p>" % E(l) for l in txt.split("\n") if l.strip())
    return '<div class="splitb"><b>%s</b>%s</div>' % (E(U["split"]), body)


SUM3_CSS = """.sum3,.splitb{margin:20px 0 0;padding:13px 15px;border-radius:12px}
.sum3{background:#F6F7F9;border:1px solid #ECEDF1}
.splitb{border:1px dashed #D7DAE0}
.sum3>b,.splitb>b{display:block;font-size:12px;letter-spacing:.02em;color:#5B6070;margin-bottom:7px}
.sum3 ul{list-style:none;margin:0;padding:0}
.sum3 li{position:relative;padding-left:15px;margin:0 0 7px;font-size:15px;line-height:1.62}
.sum3 li:last-child{margin-bottom:0}
.sum3 li:before{content:"\u00B7";position:absolute;left:3px;color:#8E93A0;font-weight:700}
.splitb p{margin:0 0 5px;font-size:14.5px;line-height:1.6}
.splitb p:last-child{margin-bottom:0}"""


def gist_blocks(gist):
    """Marked-up gist -> page HTML. Same three markers as the app."""
    html, buf = [], []

    def flush():
        t = "\n".join(buf).strip("\n")
        del buf[:]
        if t:
            html.append('<p class="gist">%s</p>' % E(t))

    for line in str(gist or "").split("\n"):
        if line.startswith("## "):
            flush()
            html.append("<h2 class=\"gsub\">%s</h2>" % E(line[3:].strip()))
        elif line.startswith("@@CHK@@"):
            flush()
            parts = line[7:].split("@@")
            cells = (parts[0] or "").split("|")
            rows = "".join(
                "<div class=\"chk-c\"><i>%s</i><b>%s</b></div>" % (E(cells[j]), E(cells[j + 1]))
                for j in range(0, len(cells) - 1, 2)
            )
            html.append(
                '<div class="chk"><div class="chk-g">%s</div>%s%s</div>' % (
                    rows,
                    ('<p class="chk-n">%s</p>' % E(parts[1])) if len(parts) > 1 and parts[1] else "",
                    ('<p class="chk-s">%s</p>' % E(parts[2])) if len(parts) > 2 and parts[2] else "",
                )
            )
        elif line.startswith("@@CMP@@"):
            flush()
            c = (line[7:].split("|") + ["", "", "", ""])[:4]
            html.append(
                '<div class="cmp"><div class="cmp-c"><i>%s</i><p>%s</p></div>'
                '<div class="cmp-vs">VS</div>'
                '<div class="cmp-c cmp-b"><i>%s</i><p>%s</p></div></div>'
                % (E(c[0]), E(c[1]), E(c[2]), E(c[3]))
            )
        elif line.startswith("@@REF@@"):
            flush()
            r = (line[7:].split("|") + ["", "", ""])[:3]
            host = ""
            m2 = re.match(r"https?://(?:www\.)?([^/]+)", r[1] or "")
            if m2:
                host = m2.group(1)
            if r[2]:
                html.append(
                    '<div class="gcardw"><a class="gcard" href="%s" rel="noopener" target="_blank">'
                    '<img src="%s" alt="" loading="lazy"><span class="gcard-t">%s</span></a>'
                    '%s</div>'
                    % (E(r[1] or "#"), E(r[2]), E(r[0]),
                       ('<div class="gcard-src">출처: %s</div>' % E(host)) if host else ""))
            else:
                html.append('<div class="gref"><a href="%s" rel="noopener" target="_blank">%s &#8599;</a></div>'
                            % (E(r[1] or "#"), E(r[0])))
        elif line.startswith("@@IMG@@"):
            flush()
            m = (line[7:].split("|") + ["", "", "", ""])[:4]
            cap = ""
            if m[1]:
                credit = (' · <a href="%s" rel="noopener" target="_blank">%s</a>'
                          % (E(m[3] or "#"), E(m[2]))) if m[2] else ""
                cap = "<figcaption>%s%s</figcaption>" % (E(m[1]), credit)
            html.append('<figure class="gimg"><img src="%s" alt="%s" loading="lazy">%s</figure>'
                        % (E(m[0]), E(m[1]), cap))
        else:
            buf.append(line)
    flush()
    return "".join(html)


def quote_block(item, lang):
    """The author's own words, above our reading.

    Shown on ALL three language pages, always in the source language. `quote`
    is written once and never translated: translating it would defeat the point
    of showing it, and an English reader arriving at /p/en/ has the same right
    to see what the take is based on as a Korean one. (Until 2026-07-27 this
    returned "" for en/ja, so 30 pages carried the reading with no evidence.)

    Marked up as figure + blockquote + figcaption so the caption is bound to
    the quotation rather than merely sitting next to it, with the source URL in
    the `cite` attribute. `lang` on the blockquote matters here specifically
    because the quote is often NOT in the page's language."""
    q = item.get("quote") or {}
    lines = [l for l in (q.get("lines") or []) if l]
    if not lines:
        return ""
    cite = q.get("cite") or item.get("source") or ""
    href = safe_href(item.get("sourceUrl"), "")
    slang = (item.get("sourceLang") or "").lower()
    lattr = ' lang="%s"' % E(slang) if slang in ("ko", "en", "ja") else ""
    cattr = ' cite="%s"' % E(href) if href else ""
    body = "".join("<p>%s</p>" % E(l) for l in lines)
    tail = ('<a href="%s" rel="nofollow noopener" target="_blank">%s</a>'
            % (E(href), E(cite))) if href else E(cite)
    return ('<figure class="srcq"><blockquote%s%s>%s</blockquote>'
            '<figcaption class="srcq-c">%s</figcaption></figure>'
            % (cattr, lattr, body, tail))


def clip(text, n):
    t = re.sub(r"\s+", " ", text or "").strip()
    return t[: n - 1].rstrip() + "…" if len(t) > n else t


# ---- entity (company / person) association + slugs ----
SLUG_OVERRIDE = {"메르": "meru"}


# 슬러그 소유권 레지스트리 (같은 키는 항상 같은 슬러그, 충돌은 결정적으로 분리)
_SLUG_BY_KEY = {}
_KEY_BY_SLUG = {}


def _ascii_slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _claim(key, base):
    """base 슬러그를 key에 배정. 다른 키가 이미 그 슬러그를 쓰면 접미사로 분리."""
    slug = base
    if _KEY_BY_SLUG.get(slug, key) != key:
        slug = base + "-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:6]
    _SLUG_BY_KEY[key] = slug
    _KEY_BY_SLUG[slug] = key
    return slug


def register_slugs_from_aliases(entities):
    """비ASCII 엔티티 키의 슬러그를 엔티티 aliases의 영어 표기에서 자동 도출한다.
    (SLUG_OVERRIDE를 손으로 유지할 필요 없음.) 정렬 순서로 처리해 실행 간 안정적."""
    for key in sorted(entities):
        if key in _SLUG_BY_KEY:
            continue
        if key in SLUG_OVERRIDE:
            _claim(key, SLUG_OVERRIDE[key])
            continue
        base = _ascii_slug(key)
        if base:  # ASCII 키는 기존 슬러그 그대로 (하위호환)
            _claim(key, base)
            continue
        cand = ""  # 비ASCII: 첫 ASCII 별칭에서 슬러그 도출
        for al in (entities.get(key) or {}).get("aliases", []):
            s = _ascii_slug(al)
            if s:
                cand = s
                break
        if not cand:  # 쓸 만한 영어 별칭이 없으면 안정적 해시로 폴백
            cand = "k-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
        _claim(key, cand)


_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[぀-ヿ]")
_CJK = re.compile(r"[一-鿿]")
_LATIN_ONLY = re.compile(r"^[\x20-\x7e]+$")


def ent_label(key, ent, lang):
    """엔티티 칩 라벨을 페이지 언어에 맞게 고른다.

    ko는 이미 색인된 표기를 흔들지 않으려고 키를 그대로 쓴다.
    라틴 문자 키(NVIDIA 등)는 어느 언어에서든 그대로 쓰는 게 자연스럽다.
    그 외(밸류에이션 같은 한글 키)만 aliases에서 언어에 맞는 표기를 찾는다.
    """
    if lang == "ko" or _LATIN_ONLY.match(key or ""):
        return key
    aliases = (ent or {}).get("aliases") or []
    if lang == "en":
        for a in aliases:
            if _LATIN_ONLY.match(a):
                return a
        return key
    for a in aliases:  # ja: 가나 우선, 한글 없는 한자 표기까지 허용
        if _KANA.search(a) or (_CJK.search(a) and not _HANGUL.search(a)):
            return a
    for a in aliases:
        if _LATIN_ONLY.match(a):
            return a
    return key


def slugify(key):
    cached = _SLUG_BY_KEY.get(key)
    if cached is not None:
        return cached
    if key in SLUG_OVERRIDE:
        base = SLUG_OVERRIDE[key]
    else:
        base = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
        if not base:
            # 별칭 등록 전 비ASCII 키가 여기 오면 안정적 해시로 폴백.
            base = "k-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    return _claim(key, base)


def build_matcher(entities):
    """[(compiled_regex, key)] over every alias. Word boundaries only where
    the adjacent character is ASCII \\w — otherwise \\b can never match
    (e.g. trailing \\b after 하이닉스 in "SK하이닉스")."""
    pats = []
    for key, e in entities.items():
        for a in e.get("aliases", []) or []:
            if not a:
                continue
            head = r"\b" if re.match(r"[A-Za-z0-9]", a) else ""
            tail = r"\b" if re.search(r"[A-Za-z0-9]$", a) else ""
            pats.append((re.compile(head + re.escape(a) + tail, re.I), key))
    return pats


def item_entities(item, entities, pats):
    s = set()
    cov = (item.get("cover") or {}).get("label")
    if cov in entities:
        s.add(cov)
    for t in item.get("tags", []) or []:
        if t in entities:
            s.add(t)
    if item.get("source") in entities:
        s.add(item["source"])
    text = " ".join(
        [item["title"].get(l, "") or "" for l in ("en", "ko", "ja")]
        + [item["gist"].get(l, "") or "" for l in ("en", "ko", "ja")]
        + [item["why"].get(l, "") or "" for l in ("en", "ko", "ja")]
    )
    for rx, key in pats:
        if rx.search(text):
            s.add(key)
    return s


def rfc822(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        d = datetime.now(timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


# ---- social share images (1200x630 PNG per article) ----
OG_W, OG_H = 1200, 630


def _hex(c, fb=(17, 18, 20)):
    c = (c or "").lstrip("#")
    try:
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except Exception:
        return fb


def _og_setup():
    """Return drawing helpers if Pillow + a CJK font are available, else None."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa
    except Exception:
        try:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                            "--break-system-packages", "pillow"], check=True)
            from PIL import Image, ImageDraw, ImageFont  # noqa
        except Exception:
            return None
    import glob, os
    def pick(*globs):
        for g in globs:
            for p in sorted(glob.glob(g, recursive=True)):
                if os.path.exists(p):
                    return p
        return None
    bold = pick("/usr/share/fonts/**/NotoSansCJK*Bold*.ttc",
                "/usr/share/fonts/**/NotoSansCJK*.ttc",
                "/usr/share/fonts/**/*CJK*.ttc")
    reg = pick("/usr/share/fonts/**/NotoSansCJK*Regular*.ttc") or bold
    if not bold:
        return None
    return (Image, ImageDraw, ImageFont, bold, reg)


def _wrap(draw, text, font, max_w, max_lines):
    words = list(text.strip())  # char-level wrap works for KO/JA/EN alike
    lines, cur = [], ""
    for ch in words:
        t = cur + ch
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = ch
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1] + "…", font=font) > max_w:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def _og_tile(Image, ImageDraw, src_path, is_logo, size):
    """A rounded-square thumbnail: photos are cover-filled; logos sit on a
    white tile, contained with padding."""
    im = Image.open(src_path).convert("RGBA")
    if is_logo:
        tile = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        pad = int(size * 0.17)
        maxd = size - 2 * pad
        w0, h0 = im.size
        sc = min(maxd / w0, maxd / h0)
        nw, nh = max(1, int(w0 * sc)), max(1, int(h0 * sc))
        im2 = im.resize((nw, nh), Image.LANCZOS)
        tile.paste(im2, ((size - nw) // 2, (size - nh) // 2), im2)
    else:
        w0, h0 = im.size
        s = min(w0, h0)
        tile = im.crop(((w0 - s) // 2, (h0 - s) // 2, (w0 - s) // 2 + s, (h0 - s) // 2 + s)).resize((size, size), Image.LANCZOS).convert("RGBA")
    rad = int(size * 0.13)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=rad, fill=255)
    tile.putalpha(mask)
    return tile


AV_CACHE = {}  # url -> local ogsrc path (downloaded author avatars)


def _download_avatars(items):
    """Author avatarImg may be a full URL (e.g. unavatar.io). Cache each one
    locally under ogsrc/ so share cards can show the face. Best-effort."""
    import os, hashlib, urllib.request
    os.makedirs("ogsrc", exist_ok=True)
    urls = {i.get("avatarImg") for i in items
            if (i.get("avatarImg") or "").startswith("http")}
    for u in urls:
        loc = "ogsrc/av-" + hashlib.md5(u.encode()).hexdigest()[:12] + ".png"
        if os.path.exists(loc):
            AV_CACHE[u] = loc
            continue
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=20).read()
            if len(data) > 500:
                open(loc, "wb").write(data)
                AV_CACHE[u] = loc
        except Exception as e:
            print(f"[avatar-skip] {u}: {e}")


def _og_source(item):
    """Return (path, is_logo) for the card thumbnail, or (None, False)."""
    import os
    av = item.get("avatarImg")
    if av and os.path.exists(av):
        return av, False
    if av and av.startswith("http") and os.path.exists(AV_CACHE.get(av, "")):
        return AV_CACHE[av], False
    ph = f"ogsrc/{item['id']}.photo.png"
    lg = f"ogsrc/{item['id']}.logo.png"
    if os.path.exists(ph):
        return ph, False
    if os.path.exists(lg):
        return lg, True
    return None, False


def make_og(item, og):
    Image, ImageDraw, ImageFont, boldp, regp = og
    import os
    W, H, M = OG_W, OG_H, 64
    frm = _hex((item.get("cover") or {}).get("from"))
    to = _hex((item.get("cover") or {}).get("to"))
    # diagonal gradient (small then upscaled = smooth + fast)
    sm = (64, 34)
    gmask = Image.new("L", sm)
    gmask.putdata([int(255 * ((x / (sm[0] - 1)) + (y / (sm[1] - 1))) / 2)
                   for y in range(sm[1]) for x in range(sm[0])])
    base = Image.new("RGB", (W, H), frm)
    top = Image.new("RGB", (W, H), to)
    img = Image.composite(top, base, gmask.resize((W, H)))
    # darken bottom for legible text
    ov = Image.new("L", (1, H))
    ov.putdata([int(205 * max(0, (y - H * 0.30) / (H * 0.70))) for y in range(H)])
    img = Image.composite(Image.new("RGB", (W, H), (12, 13, 16)), img, ov.resize((W, H)))

    # subject thumbnail on the LEFT (photo of the person/company the story is about)
    src, is_logo = _og_source(item)
    TH = 384
    ty0 = (H - TH) // 2
    tx0 = M
    have_img = False
    if src:
        try:
            tile = _og_tile(Image, ImageDraw, src, is_logo, TH)
            # soft shadow
            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle((tx0, ty0 + 8, tx0 + TH, ty0 + TH + 8), radius=int(TH * 0.13), fill=(0, 0, 0, 90))
            img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"), (0, 0))
            img.paste(tile, (tx0, ty0), tile)
            have_img = True
        except Exception:
            have_img = False

    d = ImageDraw.Draw(img)
    textX = (tx0 + TH + 52) if have_img else M
    textW = W - textX - M
    fTitle = ImageFont.truetype(boldp, 54 if have_img else 60)
    fMeta = ImageFont.truetype(regp, 28)
    fBrand = ImageFont.truetype(boldp, 30)
    fLabel = ImageFont.truetype(boldp, 40 if have_img else 44)
    # brand + cover label (top of the text column)
    d.text((textX, M - 6), "◆ STACKS", font=fBrand, fill=(255, 255, 255))
    label = (item.get("cover") or {}).get("label", "")
    if label:
        d.text((textX, M + 42), _wrap(d, label, fLabel, textW, 1)[0], font=fLabel, fill=(232, 232, 238))
    # title, bottom-aligned above the source line
    title = item["title"].get("ko") or item["title"]["en"]
    lh = 68 if have_img else 74
    lines = _wrap(d, title, fTitle, textW, 3)
    ty = H - M - 42 - lh * len(lines)
    for i, ln in enumerate(lines):
        d.text((textX, ty + i * lh), ln, font=fTitle, fill=(255, 255, 255))
    # source · date
    meta = f"{dispname(item.get('source',''))}  ·  {item.get('date','')}"
    d.text((textX, H - M - 2), meta, font=fMeta, fill=(226, 232, 240))
    os.makedirs("og", exist_ok=True)
    img.save(f"og/{item['id']}.png", optimize=True)


MIN_RATE_N = 5  # 적중률을 공개할 최소 채점 표본


def week_window(items):
    """(wk_items, label) for the last 7 days, same rule week_page() uses."""
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=7)).isoformat()
    wk = [i for i in items if i.get("date", "") >= cutoff]
    if len(wk) < 3:
        wk = items[:6]
    iso = today.isocalendar()
    return sorted(wk, key=lambda x: x.get("date", ""), reverse=True), f"{iso[0]} W{iso[1]:02d}"


def scoreboard_stats(items):
    """Weekly numbers behind the share card.

    적중률은 채점이 끝난 콜(hit/miss)에서만 계산한다. 채점 대기(pending)를 분모에
    넣으면 초반에 0%처럼 보여서 오히려 신뢰를 깎아먹는다.
    """
    wk, label = week_window(items)
    rows, agg = {}, dict(posts=len(wk), calls=0, hit=0, miss=0, pending=0)
    for i in wk:
        name = i.get("source", "")
        r = rows.setdefault(name, dict(name=name, calls=0, hit=0, miss=0, pending=0,
                                       avatar=i.get("avatarImg") or ""))
        if i.get("stance") in ("bull", "bear"):
            r["calls"] += 1
            agg["calls"] += 1
        st = (i.get("outcome") or {}).get("status")
        if st in ("hit", "miss", "pending"):
            r[st] += 1
            agg[st] += 1
    order = sorted((r for r in rows.values() if r["name"]),
                   key=lambda r: (-(r["hit"] + r["miss"]), -r["calls"], -r["pending"], r["name"]))
    return dict(label=label, agg=agg, rows=order, week=wk)


def make_scoreboard(items, og, out="og/scoreboard.png"):
    """Render the weekly 1200x630 scoreboard card (this-week.html의 og:image).

    이 카드가 없으면 this-week.html 공유 시 twitter:card summary_large_image가
    빈 이미지로 뜬다. 매 빌드마다 다시 그려서 항상 이번 주 숫자를 보여준다.
    """
    if not og:
        return False
    Image, ImageDraw, ImageFont, boldp, regp = og
    import os
    s = scoreboard_stats(items)
    a = s["agg"]
    W, H, M = OG_W, OG_H, 64
    frm, to = _hex("#0B1220"), _hex("#26324A")
    sm = (64, 34)
    gmask = Image.new("L", sm)
    gmask.putdata([int(255 * ((x / (sm[0] - 1)) + (y / (sm[1] - 1))) / 2)
                   for y in range(sm[1]) for x in range(sm[0])])
    img = Image.composite(Image.new("RGB", (W, H), to), Image.new("RGB", (W, H), frm),
                          gmask.resize((W, H)))
    d = ImageDraw.Draw(img)
    fBrand = ImageFont.truetype(boldp, 30)
    fKick = ImageFont.truetype(regp, 26)
    fH1 = ImageFont.truetype(boldp, 54)
    fNum = ImageFont.truetype(boldp, 56)
    fLab = ImageFont.truetype(regp, 24)
    fName = ImageFont.truetype(boldp, 32)
    fRec = ImageFont.truetype(regp, 26)
    fFoot = ImageFont.truetype(regp, 24)

    d.text((M, 50), "◆ STACKS", font=fBrand, fill=(255, 255, 255))
    kick = s["label"]
    d.text((W - M - d.textlength(kick, font=fKick), 56), kick, font=fKick, fill=(148, 163, 184))
    d.text((M, 106), "이번 주 필진 스코어보드", font=fH1, fill=(255, 255, 255))

    # 표본이 얇을 때 "100%"를 띄우면 자랑이 아니라 허세로 읽힌다.
    # 채점 5건 미만이면 적중률 대신 대기 건수를 보여준다.
    graded = a["hit"] + a["miss"]
    if graded >= MIN_RATE_N:
        val4, lab4, col4 = f"{round(100 * a['hit'] / graded)}%", "적중률", (52, 211, 153)
    else:
        val4, lab4, col4 = str(a["pending"]), "채점 대기", (255, 255, 255)
    stats = [(str(a["posts"]), "글", (255, 255, 255)), (str(a["calls"]), "방향성 콜", (255, 255, 255)),
             (str(graded), "채점 완료", (255, 255, 255)), (val4, lab4, col4)]
    for n, (val, lab, col) in enumerate(stats):
        x = M + n * 272
        d.text((x, 192), val, font=fNum, fill=col)
        d.text((x, 260), lab, font=fLab, fill=(148, 163, 184))
    d.line((M, 312, W - M, 312), fill=(51, 65, 85), width=2)

    y, TH = 332, 60
    for r in s["rows"][:3]:
        src, is_logo = _og_source({"id": "_sb", "avatarImg": r["avatar"]})
        tx = M
        if src:
            try:
                tile = _og_tile(Image, ImageDraw, src, is_logo, TH)
                img.paste(tile, (tx, y), tile)
            except Exception:
                src = None
        g = r["hit"] + r["miss"]
        rec = (f"적중 {r['hit']} · 빗나감 {r['miss']}" if g
               else f"콜 {r['calls']} · 채점 대기 {r['pending']}")
        recw = d.textlength(rec, font=fRec)
        nx = tx + (TH + 22 if src else 0)
        name = _wrap(d, dispname(r["name"]), fName, W - M - recw - 28 - nx, 1)[0]
        d.text((nx, y + 12), name, font=fName, fill=(255, 255, 255))
        d.text((W - M - recw, y + 18), rec, font=fRec,
               fill=(52, 211, 153) if g and r["hit"] > r["miss"] else (203, 213, 225))
        y += 76

    foot = "누가 맞았는지 기록으로 남는다 · stacksdaily.com/this-week.html"
    d.text((M, H - M - 4), foot, font=fFoot, fill=(148, 163, 184))
    os.makedirs("og", exist_ok=True)
    img.save(out, optimize=True)
    print(f"[og] scoreboard: 글 {a['posts']} · 콜 {a['calls']} · 채점 {graded} · {lab4} {val4}")
    return True


# ---- one publisher identity, reused by every JSON-LD block on the site ----
# Google treats `publisher` as an entity: giving it a stable @id, the site URL
# and a logo lets Search tie all 400+ pages to a single brand instead of a
# bare name string that matches nothing else on the web.
def publisher_ld():
    # @id MUST match the Organization node already declared in index.html
    # (https://stacksdaily.com/#org) so the homepage graph and all 400+ article
    # pages resolve to one entity instead of two unrelated ones.
    return {
        "@type": "Organization",
        "@id": BASE + "#org",
        "name": SITE,
        # Every name this site is known by. "Stacks" is a common noun and an
        # existing brand elsewhere, so Google needs the domain-shaped forms
        # ("Stacks Daily", "stacksdaily.com") tied to the same entity as the
        # brand name, or it falls back to showing the bare domain.
        "alternateName": ["Stacks Daily", "StacksDaily", "stacksdaily.com",
                          "\uc2a4\ud0dd\uc2a4", "\uc2a4\ud0dd\uc2a4\ub370\uc77c\ub9ac", "\u30b9\u30bf\u30c3\u30af\u30b9"],
        "url": BASE,
        "logo": {"@type": "ImageObject", "url": BASE + "icon-512.png",
                 "width": 512, "height": 512},
        "sameAs": ["https://x.com/InfraThesis", "https://infrathesis.substack.com"],
    }


# ---- static article page chrome, per language ----
# The p/ layer used to be one Korean page carrying all three languages at once,
# which reads to Google as "a Korean page with foreign text in it" and leaves the
# English/Japanese search markets unreachable. Each language now gets its own URL
# (p/{id}.html, p/en/{id}.html, p/ja/{id}.html) and the three are tied together
# with reciprocal hreflang.
UI = {
    "ko": dict(app="Stacks 앱에서 보기 →", src="원문 보기 ↗", paid="$ 원문은 유료 구독",
               origlang="원문", ents="관련 종목·인물", related="관련 글",
               other="다른 언어로 읽기", why="투자 포인트", ask="짚어볼 점",
               sum3="세 줄 요약", split="구분 기준",
               home=SITE + " 홈", allp="전체 글", about="소개",
               disc="요약·해설은 " + SITE + "의 창작물입니다. 원문의 저작권은 원저작자에게 있으며, "
                    "각 항목은 출처를 표기하고 원문으로 링크합니다. 투자 자문이 아니며, "
                    "투자 판단과 그 책임은 이용자 본인에게 있습니다."),
    "en": dict(app="Open in the Stacks app →", src="Read the original ↗",
               paid="$ Original is paywalled", origlang="original",
               ents="Companies & people", related="Related",
               other="Read this in another language", why="Why it matters",
               sum3="In three lines", split="How to tell which",
               ask="Worth asking", home=SITE + " home", allp="All articles", about="About",
               disc="Summaries and commentary are original work by " + SITE + ". Copyright in the "
                    "source material remains with its author; every item credits the source and "
                    "links to the original. This is information and commentary, not investment advice."),
    "ja": dict(app="Stacksアプリで見る →", src="元記事を読む ↗", paid="$ 元記事は有料購読",
               origlang="原文", ents="関連銘柄・人物", related="関連記事",
               other="他の言語で読む", why="Why it matters", ask="考えるべき点",
               sum3="3行まとめ", split="見分ける基準",
               home=SITE + " ホーム", allp="記事一覧", about="Stacksについて",
               disc="要約・解説は" + SITE + "の著作物です。元記事の著作権は原著者に帰属し、各項目は"
                    "出典を明記して原文にリンクしています。投資助言ではなく、投資判断とその責任は"
                    "利用者本人にあります。"),
}

# ---- record blocks (author track record / graded outcome / opposing cards) ----
# The app already owns all three; until now they lived only behind the SPA, so
# the pages Google actually indexes carried the summary and nothing else. These
# put the record on the crawlable page. They borrow no prose from the source
# post: every line is our own aggregate over items.json, which is the point
# (claude/strategy-originality-2026-07-25.md - "요약은 미끼고 기록이 제품이다").
REC_UI = {
    "ko": dict(rec="이 필진의 기록", posts="글", calls="방향성 콜",
               bull="강세", bear="약세", watch="관점", hit="적중", miss="빗나감",
               more="전체 기록 보기 →", oc="그 후 어떻게 됐나",
               pending="채점 대기", opp="같은 사안, 다른 관점"),
    "en": dict(rec="This author's record", posts="posts", calls="directional calls",
               bull="Bull", bear="Bear", watch="Watch", hit="Hit", miss="Miss",
               more="See the full record →", oc="What happened next",
               pending="Awaiting grading", opp="Same story, other views"),
    "ja": dict(rec="この筆者の記録", posts="記事", calls="方向性コール",
               bull="強気", bear="弱気", watch="観点", hit="的中", miss="外れ",
               more="記録をすべて見る →", oc="その後どうなったか",
               pending="採点待ち", opp="同じ話題、別の見方"),
}
LANGS = ("ko", "en", "ja")
LANG_DIR = {"ko": "p", "en": "p/en", "ja": "p/ja"}
LANG_REL = {"ko": "../", "en": "../../", "ja": "../../"}
OG_LOCALE = {"ko": "ko_KR", "en": "en_US", "ja": "ja_JP"}
FEED_FILE = {"ko": "feed.xml", "en": "feed-en.xml", "ja": "feed-ja.xml"}


def page_url(iid, lang):
    """Canonical URL of one article in one language. Korean keeps the original
    p/{id}.html path so every existing backlink and indexed URL stays valid."""
    return BASE + ("p/%s.html" % iid if lang == "ko" else "p/%s/%s.html" % (lang, iid))


def item_langs(item):
    """Languages this item can actually be published in (needs a summary)."""
    return [lg for lg in LANGS if (item.get("gist") or {}).get(lg)]


def hreflang_tags(iid, langs):
    """Reciprocal hreflang set. Every page in the cluster lists every page in the
    cluster (itself included) or Google ignores the annotation entirely."""
    if len(langs) < 2:
        return ""
    tags = "".join(
        '<link rel="alternate" hreflang="%s" href="%s">' % (lg, E(page_url(iid, lg)))
        for lg in langs
    )
    dflt = "ko" if "ko" in langs else langs[0]
    return tags + '<link rel="alternate" hreflang="x-default" href="%s">' % E(page_url(iid, dflt))


# Filled once by main(); read by the record blocks below. Module state for the
# same reason AV_CACHE is: threading four more parameters through page_html()
# for data that is identical on every page buys nothing.
TITLES = {}      # id -> {"ko":..., "en":..., "ja":...}
ITEM_META = {}   # id -> {"stance":..., "date":..., "source":...}
REC_OF = {}      # author display name -> aggregate dict (see build_records)
OPP_OF = {}      # id -> {"k": ticker key, "ids": [...]} from build_data


def title_of(iid, lang):
    """Headline in `lang`, falling back to any language we do have. Opposing and
    related cards may not exist in all three languages, and a blank link label
    is worse than a Korean headline on an English page."""
    t = TITLES.get(iid) or {}
    return t.get(lang) or t.get("ko") or t.get("en") or t.get("ja") or ""


def stance_tag(st, R):
    if st == "bull":
        return '<i class="bl">%s</i>' % E(R["bull"])
    if st == "bear":
        return '<i class="be">%s</i>' % E(R["bear"])
    return '<i class="wa">%s</i>' % E(R["watch"])


def _card_rows(ids, lang, R, limit=3):
    rows = ""
    for iid in ids[:limit]:
        t = title_of(iid, lang)
        if not t:
            continue
        m = ITEM_META.get(iid, {})
        rows += ('<li>%s<a href="%s.html">%s</a><time>%s</time></li>'
                 % (stance_tag(m.get("stance"), R), E(iid), E(clip(t, 80)),
                    E((m.get("date") or "")[5:])))
    return rows


def record_block(item, lang, R, REL):
    """Author track record: how many calls this writer has made, which way they
    lean, how the graded ones landed. None of this is in the source post."""
    rec = REC_OF.get(item.get("source") or "")
    if not rec or rec["total"] < 3:
        return ""
    chips = ('<span><b>%d</b>%s</span><span><b>%d</b>%s</span>'
             % (rec["total"], E(R["posts"]), len(rec["calls"]), E(R["calls"])))
    if rec["bull"]:
        chips += '<span class="bl"><b>%d</b>%s</span>' % (rec["bull"], E(R["bull"]))
    if rec["bear"]:
        chips += '<span class="be"><b>%d</b>%s</span>' % (rec["bear"], E(R["bear"]))
    if rec["hits"] or rec["miss"]:
        chips += ('<span class="bl"><b>%d</b>%s</span><span class="be"><b>%d</b>%s</span>'
                  % (rec["hits"], E(R["hit"]), rec["miss"], E(R["miss"])))
    rows = _card_rows([i for i in rec["calls"] if i != item["id"]], lang, R)
    lst = '<ul class="rec-l">%s</ul>' % rows if rows else ""
    more = '<a class="rec-m" href="%sr/%s.html">%s</a>' % (REL, E(rec["slug"]), E(R["more"]))
    return ('<section class="rec"><h3>%s</h3><div class="rec-s">%s</div>%s%s</section>'
            % (E(R["rec"]), chips, lst, more))


def outcome_block(item, lang, R):
    """This card's own prediction and, once the weekly grader has run, whether
    it landed. `outcome` is written by the publishing routine, graded later."""
    oc = item.get("outcome") or {}
    note = (oc.get("note") or {}).get(lang) or (oc.get("note") or {}).get("ko") or ""
    if not note:
        return ""
    st = oc.get("status") or "pending"
    label = {"hit": R["hit"], "miss": R["miss"]}.get(st, R["pending"])
    return ('<section class="oc oc-%s"><h3>%s</h3><p><i>%s</i>%s</p></section>'
            % (E(st), E(R["oc"]), E(label), E(note)))


def opp_block(item, lang, R):
    """Cards that took the other side on the same company. The debate is the
    product, so a reader arriving from search should land on both sides."""
    ids = (OPP_OF.get(item["id"]) or {}).get("ids") or []
    rows = _card_rows(ids, lang, R, limit=2)
    if not rows:
        return ""
    return '<section class="opp"><h3>%s</h3><ul>%s</ul></section>' % (E(R["opp"]), rows)


def _build_data():
    """build_data.py owns the canonical opposite-card pairing and the
    back-catalogue stance map. Import it rather than reimplement either."""
    import os as _os, sys as _sys
    here = _os.path.dirname(_os.path.abspath(__file__))
    if here not in _sys.path:
        _sys.path.insert(0, here)
    try:
        import build_data
        return build_data
    except Exception as e:
        print("[rec] build_data unavailable: " + str(e))
        return None


def author_slug_map():
    """Feed id per display name, so a record link points at r/serenity.html and
    not at a slugified display name. Mirrors build_extra_pages()."""
    try:
        srcmeta = json.load(open("sources.json", encoding="utf-8"))
    except Exception:
        srcmeta = {}
    out = {}
    for k, v in srcmeta.items():
        if isinstance(v, dict) and v.get("source"):
            out.setdefault(v["source"], k)  # first feed wins (serenity, not serenity_substack)
    return out


def build_records(items, entities=None):
    """Populate TITLES / ITEM_META / REC_OF / OPP_OF once for the whole build."""
    TITLES.clear(); ITEM_META.clear(); REC_OF.clear(); OPP_OF.clear()
    entities = entities or {}
    name2slug = author_slug_map()

    # Back-catalogue cards predate the `stance` field; index.html carries a map
    # that fills them in and build_data reads it. Resolve stance the same way
    # here, or the badges disagree with the pairing that put a card in the block.
    bd, stance_map = _build_data(), {}
    if bd:
        try:
            stance_map = bd.load_stance_map(open("index.html", encoding="utf-8").read())
        except Exception as e:
            print("[rec] stance map unavailable: " + str(e))

    def _stance(i):
        return i.get("stance") or stance_map.get(i["id"])

    for i in items:
        TITLES[i["id"]] = i.get("title") or {}
        ITEM_META[i["id"]] = {"stance": _stance(i), "date": i.get("date", ""),
                              "source": i.get("source", "")}

    by_author = {}
    for i in items:  # items arrive newest-first, so call lists stay newest-first
        by_author.setdefault(i.get("source", ""), []).append(i)
    for name, its in by_author.items():
        if not name:
            continue
        calls = [i for i in its if _stance(i) in ("bull", "bear")]
        REC_OF[name] = {
            "slug": name2slug.get(name) or slugify(name),
            "total": len(its),
            "calls": [i["id"] for i in calls],
            "bull": sum(1 for i in its if _stance(i) == "bull"),
            "bear": sum(1 for i in its if _stance(i) == "bear"),
            "hits": sum(1 for i in its if (i.get("outcome") or {}).get("status") == "hit"),
            "miss": sum(1 for i in its if (i.get("outcome") or {}).get("status") == "miss"),
        }

    # Opposing cards are NOT recomputed here. build_data.pick_opposites() is the
    # single source of truth for the pairing (CLAUDE.md "반대편") and it is
    # deliberately strict: both sides must DECLARE the same company in a cover
    # label or tag, both must take a real side, within 45 days, and one post may
    # serve as at most three foils. Matching on merely-mentioned entities - the
    # obvious shortcut - pairs a macro ETF-flows card with an Intel analysis
    # because Intel got named once, and a card that claims two authors disagree
    # when they don't is worse than a card that stays quiet. Reusing it also
    # keeps this page and the app showing the SAME two cards.
    if bd:
        try:
            _rx, alias2key = bd.build_entity_matcher(entities)
            OPP_OF.update(bd.pick_opposites(items, entities, stance_map, alias2key))
        except Exception as e:
            print("[rec] opposites unavailable: " + str(e))


REC_CSS = """.rec,.oc,.opp{margin-top:26px}
.rec h3,.oc h3,.opp h3{font-size:14px;margin:0 0 10px}
.rec-s{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.rec-s span{display:inline-block;padding:7px 12px;border-radius:10px;background:#F6F7F9;border:1px solid #ECEDF1;font-size:12px;color:#8E93A0}
.rec-s b{display:block;font-size:17px;color:#17181C;line-height:1.25}
.rec-s .bl b{color:#1C7A42}.rec-s .be b{color:#B02525}
.rec-l,.opp ul{list-style:none;margin:0;padding:0;font-size:14px}
.rec-l li,.opp li{display:flex;gap:8px;align-items:baseline;padding:8px 0;border-top:1px solid #ECEDF1}
.rec-l li:first-child,.opp li:first-child{border-top:0}
.rec-l i,.opp i{flex:none;font-style:normal;font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px}
.bl{background:#E8F5EC;color:#1C7A42}.be{background:#FDEAEA;color:#B02525}.wa{background:#EEF1F5;color:#4B5563}
.rec-l a,.opp a{color:#17181C;text-decoration:none;flex:1}
.rec-l a:hover,.opp a:hover{text-decoration:underline}
.rec-l time,.opp time{flex:none;font-size:12px;color:#8E93A0}
.rec-m{display:inline-block;margin-top:10px;font-size:13px;font-weight:600;color:#17181C}
.oc p{margin:0;padding:12px 14px;border-radius:12px;background:#F6F7F9;font-size:14.5px}
.oc i{display:inline-block;font-style:normal;font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px;margin-right:8px;background:#FFF4E0;color:#A16207}
.oc-hit i{background:#E8F5EC;color:#1C7A42}.oc-miss i{background:#FDEAEA;color:#B02525}
@media(prefers-color-scheme:dark){.rec-s span{background:#141519;border-color:#2E3037}
  .rec-s b,.rec-l a,.opp a,.rec-m{color:#ECEDF1}
  .rec-l li,.opp li{border-color:#26272E}.oc p{background:#1A1B21}}"""


def page_html(item, ent_links=None, og_img=None, lang="ko", langs=None, rel_titles=None):
    iid = item["id"]
    langs = langs or [lang]
    U = UI[lang]
    REL = LANG_REL[lang]
    url = page_url(iid, lang)
    app_url = (BASE + "#sig-" + iid) if lang == "ko" else (BASE + "?c=" + iid + "&l=" + lang)
    cov = item.get("cover", {}) or {}
    grad = f"linear-gradient(135deg,{hexcolor(cov.get('from'), '#111')},{hexcolor(cov.get('to'), '#333')})"
    title = item["title"].get(lang) or item["title"].get("ko") or item["title"]["en"]
    gist = (item.get("gist") or {}).get(lang) or ""
    why = (item.get("why") or {}).get(lang) or ""
    ask = (item.get("ask") or {}).get(lang) or ""
    desc = clip(strip_markers(gist), 160)
    kw = ", ".join(item.get("tags", []) + [item.get("source", "")])

    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": desc,
        "datePublished": item.get("date", "") + "T00:00:00Z",
        "dateModified": item.get("date", "") + "T00:00:00Z",
        "inLanguage": lang,
        "author": {"@type": "Person", "name": item.get("source", "Stacks")},
        "publisher": publisher_ld(),
        "mainEntityOfPage": url,
        "isBasedOn": safe_href(item.get("sourceUrl"), ""),
        "url": url,
    }
    # isBasedOn carries the bare URL. `citation` says what that URL IS and who
    # wrote it, so "this article quotes an X post by The Kobeissi Letter" is one
    # statement a machine can read, rather than something a human has to infer
    # from the page. Matters for attribution when an AI summary reuses us.
    _src = safe_href(item.get("sourceUrl"), "")
    if _src:
        _cit = {"@type": ("SocialMediaPosting"
                          if re.search(r"//(x\.com|twitter\.com|truthsocial\.com)/", _src)
                          else "Article"),
                "url": _src}
        _name = dispname(item.get("source", ""))
        if _name:
            _cit["author"] = {"@type": "Person", "name": _name}
        ld["citation"] = _cit

    try:
        import build_data as _bd
        gist = _bd.expand_img_markers(gist, lang)
    except Exception:
        pass
    body_blocks = quote_block(item, lang) + gist_blocks(gist)
    block_css = block_css_for(body_blocks)
    block_css = (block_css + "\n") if block_css else ""
    _extra = split_block(item, lang, U) + sum3_block(item, lang, U)
    if _extra:
        body_blocks += _extra
        block_css += SUM3_CSS + "\n"
    if why:
        body_blocks += f'<p class="why"><b>{E(U["why"])}</b> · {E(why)}</p>'
    if ask:
        body_blocks += f'<p class="ask"><b>{E(U["ask"])}</b> · {E(ask)}</p>'

    # record blocks: our own aggregate, not a retelling of the source post. The
    # CSS rides along only when at least one of them rendered, for the same
    # reason BLOCK_CSS is conditional (this is inlined into ~500 pages).
    R = REC_UI[lang]
    rec_html = (outcome_block(item, lang, R) + record_block(item, lang, R, REL)
                + opp_block(item, lang, R))
    if rec_html:
        block_css += REC_CSS + "\n"

    # other languages of the same article (user value + a crawl path between
    # the three URLs that does not depend on the sitemap alone)
    others = [lg for lg in langs if lg != lang]
    other_html = ""
    if others:
        links = " · ".join(
            f'<a href="{E(page_url(iid, lg))}" hreflang="{lg}" lang="{lg}">{E(LANG_LABEL[lg])}</a>'
            for lg in others
        )
        other_html = f'<nav class="otherlang">{E(U["other"])}: {links}</nav>'

    related = ""
    rel_ids = [r for r in (item.get("related") or []) if (rel_titles or {}).get(r)]
    if rel_ids:
        links = "".join(
            f'<li><a href="{E(r)}.html">{E(clip(rel_titles[r], 90))}</a></li>' for r in rel_ids
        )
        related = f'<nav class="related"><h3>{E(U["related"])}</h3><ul>{links}</ul></nav>'

    ent_html = ""
    if ent_links:
        chips = "".join(
            f'<a class="ent-chip" href="{REL}e/{E(slug)}.html">{E(label)}</a>'
            for label, slug in ent_links
        )
        ent_html = (f'<nav class="ent-nav"><h3>{E(U["ents"])}</h3>'
                    f'<div class="ent-chips">{chips}</div></nav>')

    img_url = BASE + "og/" + iid + ".png" if og_img else ""
    # Recommended NewsArticle fields for richer Google results:
    #   image  -> the article's OG card (enables a large thumbnail in Search/News)
    #   author.url -> the author's X profile, when the avatar is an X-handle avatar
    if img_url:
        ld["image"] = img_url
    _m = re.search(r"unavatar\.io/twitter/([A-Za-z0-9_]+)", item.get("avatarImg", "") or "")
    if _m:
        ld["author"]["url"] = "https://x.com/" + _m.group(1)
    og_img_tags = (
        f'<meta property="og:image" content="{E(img_url)}">'
        f'<meta property="og:image:width" content="1200">'
        f'<meta property="og:image:height" content="630">'
        f'<meta name="twitter:image" content="{E(img_url)}">'
    ) if og_img else ""
    tw_card = "summary_large_image" if og_img else "summary"

    paywall = f'<span class="paid">{E(U["paid"])}</span>' if item.get("paywall") else ""
    og_locale = (f'<meta property="og:locale" content="{OG_LOCALE[lang]}">'
                 + "".join(f'<meta property="og:locale:alternate" content="{OG_LOCALE[lg]}">'
                           for lg in others))
    feed_rel = REL + FEED_FILE[lang]

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>/* shared link (?l=xx): bounce a human into the live app in the sharer's language. No ?l = organic/SEO visit, so this stays a normal crawlable page. */
(function(){{try{{var l=new URLSearchParams(location.search).get('l');if(!l)return;location.replace('{BASE}?c={iid}&l='+encodeURIComponent(l));}}catch(e){{}}}})();</script>
<title>{E(title)} · {SITE}</title>
<meta name="description" content="{E(desc)}">
<meta name="keywords" content="{E(kw)}">
<link rel="canonical" href="{E(url)}">
{hreflang_tags(iid, langs)}
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">
{og_locale}
<meta property="article:published_time" content="{item.get('date','')}">
{og_img_tags}
<meta name="twitter:card" content="{tw_card}">
<meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="{REL}favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="{feed_rel}">
<script type="application/ld+json">{LD(ld)}</script>
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,"Segoe UI",Roboto,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.7;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}.card{{background:#141519!important}}.gist{{color:#C9CDD6!important}}}}
.wrap{{max-width:720px;margin:0 auto;padding:0 20px 60px}}
.topbar{{padding:16px 0;font-weight:800}}
.topbar a{{color:inherit;text-decoration:none}}
.cover{{height:120px;border-radius:16px;background:{grad};display:flex;align-items:flex-end;padding:16px;margin:8px 0 20px}}
.cover .label{{font-family:ui-monospace,Menlo,monospace;color:rgba(255,255,255,.85);font-size:26px;letter-spacing:.05em}}
.meta{{font-size:13px;color:#8E93A0;margin-bottom:4px}}
h1{{font-size:26px;line-height:1.3;letter-spacing:-.02em;margin:.2em 0 .6em}}
.gist{{color:#3E414B;white-space:pre-line;font-size:16px}}
@media(prefers-color-scheme:dark){{.gist{{color:#C9CDD6}}}}
{block_css}.why,.ask{{background:#F6F7F9;border-radius:12px;padding:12px 14px;font-size:14.5px}}
.ask{{margin-top:10px}}
@media(prefers-color-scheme:dark){{.why,.ask{{background:#1A1B21}}}}
.otherlang{{margin:22px 0 0;font-size:13px;color:#8E93A0;border-top:1px solid #ECEDF1;padding-top:16px}}
.otherlang a{{color:#17181C;font-weight:600}}
@media(prefers-color-scheme:dark){{.otherlang{{border-color:#26272E}}.otherlang a{{color:#ECEDF1}}}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}}
.btn{{display:inline-block;padding:11px 18px;border-radius:999px;text-decoration:none;font-weight:700;font-size:14px}}
.btn.app{{background:#111214;color:#fff}}
.btn.src{{background:#F6F7F9;color:#17181C;border:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{.btn.app{{background:#1E1F26;color:#fff}}.btn.src{{background:#141519;color:#ECEDF1;border-color:#2E3037}}}}
.paid{{font-size:12px;color:#8E93A0;align-self:center}}
.related{{margin-top:30px;font-size:14px}}
.related ul{{padding-left:18px}}
.ent-nav{{margin-top:28px}}
.ent-nav h3{{font-size:14px;margin:0 0 10px}}
.ent-chips{{display:flex;flex-wrap:wrap;gap:8px}}
.ent-chip{{display:inline-block;padding:6px 12px;border-radius:999px;background:#F6F7F9;border:1px solid #ECEDF1;font-size:13px;font-weight:600;text-decoration:none;color:#17181C}}
.ent-chip:hover{{border-color:#111214}}
@media(prefers-color-scheme:dark){{.ent-chip{{background:#141519;color:#ECEDF1;border-color:#2E3037}}}}
footer{{margin-top:40px;padding-top:20px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar"><a href="{REL}">◆ {SITE}</a></div>
  <div class="cover"><span class="label">{E(cov.get('label',''))}</span></div>
  <div class="meta">{E(dispname(item.get('source','')))} · {E(item.get('date',''))} · {E(U['origlang'])}: {E(item.get('sourceLang',''))}</div>
  <h1>{E(title)}</h1>
  <div class="actions">
    <a class="btn app" href="{E(app_url)}">{E(U['app'])}</a>
    <a class="btn src" href="{E(safe_href(item.get('sourceUrl')))}" target="_blank" rel="noopener nofollow">{E(U['src'])}</a>
    {paywall}
  </div>
  {body_blocks}
  {rec_html}
  {other_html}
  {ent_html}
  {related}
  <footer>
    {E(U['disc'])}<br>
    <a href="{REL}">{E(U['home'])}</a> · <a href="{REL}articles.html">{E(U['allp'])}</a> · <a href="{REL}about.html">{E(U['about'])}</a> · <a href="{feed_rel}">RSS</a>
  </footer>
</div>
</body>
</html>
"""


def entity_page(key, e, ent_items):
    slug = slugify(key)
    url = BASE + "e/" + slug + ".html"
    kind = e.get("kind")
    sector = (e.get("sector", {}) or {}).get("ko") or (e.get("sector", {}) or {}).get("en", "")
    desc = ((e.get("longDesc") or {}).get("ko")
            or (e.get("desc", {}) or {}).get("ko")
            or (e.get("desc", {}) or {}).get("en", ""))
    ticker = (e.get("ticker") or "").upper()
    facts = []
    def _loc(v):  # field may be a {en,ko,ja} object or a plain string
        return (v.get("ko") or v.get("en") or "") if isinstance(v, dict) else str(v)
    for label, k in (("대표", "ceo"), ("설립", "founded"), ("상장", "listed"), ("본사", "hq"), ("거래소", "exchange")):
        if e.get(k):
            facts.append(f"<span><b>{label}</b> {E(_loc(e[k]))}</span>")
    if e.get("website"):
        w = e["website"]
        facts.append(f'<span><b>웹사이트</b> <a href="{E(w)}" target="_blank" rel="noopener nofollow">{E(w.replace("https://","").replace("www.",""))}</a></span>')
    facts_html = f'<p class="facts">{" · ".join(facts)}</p>' if facts else ""
    metadesc = clip(desc or f"{key} 관련 투자 읽을거리 모음", 160)
    rows = "".join(
        f'<li>{("<b class=sp-" + i.get("stance") + ">" + STANCE_KO.get(i.get("stance"), "관점") + "</b> ") if i.get("stance") else ""}'
        f'<a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in ent_items
    )
    # consensus tally + explicit predictions (v79)
    _b = sum(1 for i in ent_items if i.get("stance") == "bull")
    _r = sum(1 for i in ent_items if i.get("stance") == "bear")
    _w = sum(1 for i in ent_items if i.get("stance") == "watch")
    tally_html = ""
    if _b or _r or _w:
        tally_html = ('<div class="tally">'
                      + (f'<b class="bl">강세 {_b}</b>' if _b else "")
                      + (f'<b class="wa">관점 {_w}</b>' if _w else "")
                      + (f'<b class="be">약세 {_r}</b>' if _r else "")
                      + "</div>")
    _st_ko = {"pending": "채점 대기", "hit": "적중", "miss": "빗나감"}
    _preds = [i for i in ent_items if i.get("outcome") and i["outcome"].get("status")]
    preds_html = ""
    if _preds:
        _li = []
        for i in _preds:
            oc = i["outcome"]; note = oc.get("note") or {}
            nt = note.get("ko") or note.get("en") or ""
            _li.append(f'<li><span class="oc oc-{E(oc["status"])}">{_st_ko.get(oc["status"], "채점 대기")}</span> '
                       f'<a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
                       f'<span class="d">{E(nt)}</span></li>')
        preds_html = f'<h2>예측 · 적중 기록 {len(_preds)}건</h2><ul class="preds">{"".join(_li)}</ul>'

    about = {"@type": "Organization" if kind == "company" else ("DefinedTerm" if kind == "term" else "Person"), "name": key}
    if kind == "company" and ticker:
        about["tickerSymbol"] = ticker.split(".")[0]
    if e.get("url"):
        about["url"] = e["url"]
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": key, "description": metadesc, "url": url, "about": about,
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"}, "inLanguage": "ko",
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(ent_items),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1,
                 "url": BASE + "p/" + i["id"] + ".html",
                 "name": i["title"].get("ko") or i["title"]["en"]}
                for n, i in enumerate(ent_items)
            ],
        },
    }
    tk = f'<span class="tk">{E(ticker)}</span>' if ticker else ""
    prof = f'<a class="prof" href="{E(e["url"])}" target="_blank" rel="noopener nofollow">프로필 ↗</a>' if e.get("url") else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(key)} · 관련 글 {len(ent_items)}건 · {SITE}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(key)} · {SITE}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(url)}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{LD(ld)}</script>
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
.top{{font-weight:800;text-decoration:none}}
.sector{{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}}
h1{{font-size:26px;letter-spacing:-.02em;margin:0 0 6px}}
.tk{{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:#8E93A0;margin-left:8px}}
.desc{{color:#3E414B;font-size:15px;margin:8px 0 4px}}
@media(prefers-color-scheme:dark){{.desc{{color:#C9CDD6}}}}
.prof{{display:inline-block;margin:8px 0 2px;font-size:13px;font-weight:600;color:#2E5BFF;text-decoration:none}}
.facts{{font-size:12.5px;color:#8E93A0;line-height:1.9}}
.facts b{{color:#3E414B;font-weight:600;margin-right:2px}}
@media(prefers-color-scheme:dark){{.facts b{{color:#C9CDD6}}}}
.facts a{{color:#2E5BFF;text-decoration:none}}
.tally{{display:flex;gap:8px;margin:14px 0 2px;flex-wrap:wrap}}
.tally b{{padding:6px 14px;border-radius:999px;font-size:13px;color:#fff;font-weight:700}}
.tally .bl{{background:#0E9F5E}}.tally .wa{{background:#6B7280}}.tally .be{{background:#E04438}}
b.sp-bull{{color:#0E9F5E}}b.sp-bear{{color:#E04438}}b.sp-watch{{color:#8E93A0}}
.preds .oc{{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-right:6px}}
.oc-pending{{background:#F1F2F4;color:#6B7280}}.oc-hit{{background:rgba(14,159,94,.12);color:#0E9F5E}}.oc-miss{{background:rgba(224,68,56,.12);color:#E04438}}
@media(prefers-color-scheme:dark){{.oc-pending{{background:#20222A;color:#9AA0AC}}}}
h2{{font-size:16px;margin:26px 0 8px}}
ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
.d{{display:block;font-size:12px;color:#8E93A0;margin-top:3px}}
footer{{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="sector">{E(sector)}</div>
<h1>{E(key)}{tk}</h1>
<p class="desc">{E(desc)}</p>
{facts_html}
{prof}
{tally_html}
{preds_html}
<h2>관련 글 {len(ent_items)}건</h2>
<ul>{rows}</ul>
<footer>
  요약·해설은 The Infrastructure Thesis의 창작물이며, 투자 자문이 아닌 정보 제공·논평입니다. 투자 판단과 그 책임은 이용자 본인에게 있습니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def articles_index(items):
    rows = "".join(
        f'<li><a href="p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in items
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>전체 글 · {SITE}</title>
<meta name="description" content="{E(TAGLINE['ko'])}. 전체 글 목록.">
<link rel="canonical" href="{BASE}articles.html">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="alternate" type="application/rss+xml" title="Stacks" href="feed.xml">
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
h1{{font-size:22px}}
ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
.d{{display:block;font-size:12px;color:#8E93A0;margin-top:3px}}
</style>
</head>
<body>
<h1><a href="./" style="text-decoration:none">◆ {SITE}</a> 전체 글</h1>
<p style="color:#8E93A0">{E(TAGLINE['ko'])}</p>
<ul>{rows}</ul>
</body>
</html>
"""


def week_page(items, entities, item_ents, canonical_slug):
    """Public 'This week on Stacks' recap: shareable + SEO. Regenerated
    every build so this-week.html is always current; dated archives
    accumulate under week/."""
    import os
    from datetime import date, timedelta
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=7)).isoformat()
    wk_items = [i for i in items if i.get("date", "") >= cutoff]
    if len(wk_items) < 3:  # thin week: show the latest handful instead
        wk_items = items[:6]
    wk_items = sorted(wk_items, key=lambda x: x.get("date", ""), reverse=True)
    iso = today.isocalendar()
    wk_label = f"{iso[0]} W{iso[1]:02d}"
    dated_url = BASE + "week/" + canonical_slug + ".html"

    # hottest entity this week (most appearances among week items)
    ent_count = {}
    for i in wk_items:
        for k in item_ents.get(i["id"], []):
            if entities.get(k, {}).get("kind") == "company":
                ent_count[k] = ent_count.get(k, 0) + 1
    hot_ents = sorted(ent_count.items(), key=lambda x: -x[1])[:5]
    # stance tally
    bull = sum(1 for i in wk_items if i.get("stance") == "bull")
    bear = sum(1 for i in wk_items if i.get("stance") == "bear")

    rows = "".join(
        f'<li><a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in wk_items[:10]
    )
    hot_html = ""
    if hot_ents:
        chips = "".join(
            f'<a class="chip" href="../e/{slugify(k)}.html">{E(k)} <b>{n}</b></a>'
            for k, n in hot_ents
        )
        hot_html = f'<h2>이번 주 가장 많이 다뤄진 종목</h2><div class="chips">{chips}</div>'
    stance_html = ""
    if bull or bear:
        stance_html = (f'<p class="stance">이번 주 방향성 콜 '
                       f'<b class="bl">강세 {bull}</b> · <b class="be">약세 {bear}</b>. '
                       f'각 콜의 실제 성과는 <a href="../#">앱의 적중 기록</a>에서 확인.</p>')
    metadesc = clip(f"이번 주 Stacks에 올라온 투자 읽을거리 {len(wk_items)}편 요약: "
                    + ", ".join(i["title"].get("ko") or i["title"]["en"] for i in wk_items[:3]), 160)
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": f"이번 주 Stacks · {wk_label}", "description": metadesc, "url": dated_url,
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"}, "inLanguage": "ko",
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(wk_items[:10]),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1,
                 "url": BASE + "p/" + i["id"] + ".html",
                 "name": i["title"].get("ko") or i["title"]["en"]}
                for n, i in enumerate(wk_items[:10])
            ],
        },
    }
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>이번 주 Stacks · {wk_label}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(dated_url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="이번 주 Stacks · {wk_label}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(dated_url)}">
<meta property="og:image" content="{BASE}og/scoreboard.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{BASE}og/scoreboard.png">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{LD(ld)}</script>
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
.top{{font-weight:800;text-decoration:none}}
.kicker{{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}}
h1{{font-size:28px;letter-spacing:-.02em;margin:0 0 6px}}
.lead{{color:#3E414B;font-size:15px;margin:8px 0 4px}}
@media(prefers-color-scheme:dark){{.lead{{color:#C9CDD6}}}}
h2{{font-size:16px;margin:28px 0 10px}}
ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
li a{{font-weight:600;text-decoration:none}}
.d{{display:block;font-size:12px;color:#8E93A0;margin-top:3px}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{display:inline-flex;align-items:center;gap:6px;text-decoration:none;font-size:13px;font-weight:700;padding:6px 12px;border-radius:999px;border:1px solid #ECEDF1;color:#17181C}}
@media(prefers-color-scheme:dark){{.chip{{border-color:#26272E;color:#ECEDF1}}}}
.chip b{{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:#8E93A0}}
.stance{{font-size:14px;color:#3E414B;margin-top:18px}}
@media(prefers-color-scheme:dark){{.stance{{color:#C9CDD6}}}}
.stance .bl{{color:#0E9F5E}}.stance .be{{color:#E04438}}
.cta{{display:inline-block;margin-top:24px;font-weight:700;text-decoration:none;background:#111;color:#fff;padding:11px 20px;border-radius:999px}}
@media(prefers-color-scheme:dark){{.cta{{background:#fff;color:#111}}}}
footer{{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="kicker">이번 주 · {wk_label}</div>
<h1>이번 주 Stacks</h1>
<p class="lead">한 주 동안 메르·에민·둠버그·Serenity·CEO들의 글에서 추린 투자 읽을거리 {len(wk_items)}편. 같은 종목의 상반된 견해를, 당신의 언어로.</p>
<h2>이번 주 읽을거리</h2>
<ul>{rows}</ul>
{hot_html}
{stance_html}
<a class="cta" href="../">Stacks에서 더 읽기 →</a>
<footer>
  요약·해설은 The Infrastructure Thesis의 창작물이며, 투자 자문이 아닌 정보 제공·논평입니다. 투자 판단과 그 책임은 이용자 본인에게 있습니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def sitemap(items, entity_slugs=None, week_slugs=None, theme_slugs=None, record_slugs=None):
    """Sitemap with xhtml:link alternates on every article URL. Sitemap-level
    hreflang is what lets Google discover the en/ja pages as translations rather
    than as near-duplicate orphans."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # (url, lastmod, priority, alternates) — alternates only for article pages
    # Hand-written static pages belong in here too. about.html and privacy.html
    # are not generated, so nothing else would ever list them, and an AdSense or
    # policy reviewer landing on a single /p/ page has no other route to the
    # site-level context.
    urls = [(BASE, now, "1.0", None), (BASE + "this-week.html", now, "0.7", None),
            (BASE + "articles.html", now, "0.6", None),
            (BASE + "about.html", now, "0.6", None),
            (BASE + "privacy.html", now, "0.3", None)]
    for i in items:
        lgs = item_langs(i)
        alts = lgs if len(lgs) > 1 else None
        for lg in (lgs or ["ko"]):
            urls.append((page_url(i["id"], lg), i.get("date", now),
                         "0.8" if lg == "ko" else "0.7", (i["id"], alts) if alts else None))
    for slug in (entity_slugs or []):
        urls.append((BASE + "e/" + slug + ".html", now, "0.7", None))
    for slug in (week_slugs or []):
        urls.append((BASE + "week/" + slug + ".html", now, "0.6", None))
    for slug in (theme_slugs or []):
        urls.append((BASE + "t/" + slug + ".html", now, "0.8", None))
    for slug in (record_slugs or []):
        urls.append((BASE + "r/" + slug + ".html", now, "0.8", None))

    def _alt(a):
        if not a:
            return ""
        iid, lgs = a
        out = "".join(
            f'<xhtml:link rel="alternate" hreflang="{lg}" href="{E(page_url(iid, lg))}"/>'
            for lg in lgs
        )
        dflt = "ko" if "ko" in lgs else lgs[0]
        return out + f'<xhtml:link rel="alternate" hreflang="x-default" href="{E(page_url(iid, dflt))}"/>'

    body = "".join(
        f"<url><loc>{E(u)}</loc><lastmod>{E(m)}</lastmod><priority>{p}</priority>{_alt(a)}</url>"
        for u, m, p, a in urls
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + body + "</urlset>\n")


def feed(items, lang="ko"):
    """RSS in one language. Feed readers, Telegram/X auto-posting and news
    aggregators all key off <language>, so a single Korean feed was capping
    syndication to Korean-language consumers."""
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    entries = []
    for i in items[:30]:
        if not (i.get("gist") or {}).get(lang):
            continue
        link = page_url(i["id"], lang)
        title = i["title"].get(lang) or i["title"].get("ko") or i["title"]["en"]
        desc = clip(strip_markers(i["gist"][lang]), 400)
        entries.append(
            "<item>"
            f"<title>{E(title)}</title>"
            f"<link>{E(link)}</link>"
            f"<guid isPermaLink=\"true\">{E(link)}</guid>"
            f"<dc:creator>{E(i.get('source',''))}</dc:creator>"
            f"<pubDate>{rfc822(i.get('date',''))}</pubDate>"
            f"<description>{E(desc)}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">\n<channel>'
        f"<title>{SITE}</title><link>{BASE}</link>"
        f"<description>{E(TAGLINE[lang])}</description>"
        f"<language>{lang}</language><lastBuildDate>{now}</lastBuildDate>"
        f'<atom:link xmlns:atom="http://www.w3.org/2005/Atom" href="{BASE}{FEED_FILE[lang]}" rel="self" type="application/rss+xml"/>'
        + "".join(entries)
        + "</channel></rss>\n"
    )


def robots():
    return f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n"


# ---- theme debate pages + author track-record pages (v78 SEO layer) ----
# Keys and keyword patterns MUST stay in sync with THEMES in index.html.
THEMES = {
    "rates":   {"icon": "🏛️", "ko": "금리·인플레", "en": "Rates & inflation", "ja": "金利・インフレ", "flags": re.I,
                "kw": r"기준금리|인플레|국채|연준|\bFed\b|FOMC|inflation|interest rates?|rate (?:cut|hike)|treasur|bond yield|\byields?\b|利上げ|利下げ|インフレ|国債|中央銀行"},
    "dollar":  {"icon": "💵", "ko": "달러·환율", "en": "Dollar & FX", "ja": "ドル・為替", "flags": re.I,
                "kw": r"달러|환율|원화|엔화|\bdollar\b|\bDXY\b|debasement|exchange rate|\byen\b|為替|円安|円高|ドル|통화"},
    "aicapex": {"icon": "⚡", "ko": "AI 투자 사이클", "en": "AI capex", "ja": "AI設備投資", "flags": 0,
                "kw": r"\bAI\b|인공지능|데이터센터|datacenter|data center|\bGPU\b|hyperscaler|capex|설비투자|人工知能|データセンター|設備投資"},
    "semis":   {"icon": "🔬", "ko": "반도체·메모리", "en": "Semis & memory", "ja": "半導体・メモリ", "flags": re.I,
                "kw": r"반도체|메모리|파운드리|semiconductor|\bchips?\b|foundry|\bDRAM\b|\bNAND\b|\bHBM\b|\bCXL\b|lithograph|半導体|メモリ"},
    "energy":  {"icon": "🛢️", "ko": "에너지", "en": "Energy", "ja": "エネルギー", "flags": re.I,
                "kw": r"에너지|원유|천연가스|전력|원전|\boil\b|natural gas|\bLNG\b|uranium|nuclear|power grid|electricity|\benergy\b|原油|エネルギー|電力|原発"},
    "crypto":  {"icon": "🪙", "ko": "크립토·금", "en": "Crypto & gold", "ja": "暗号資産・金", "flags": re.I,
                "kw": r"비트코인|크립토|암호화폐|금값|\bBitcoin\b|\bBTC\b|crypto|stablecoin|\bgold\b|bullion|ビットコイン|暗号資産|金価格"},
    "trade":   {"icon": "🚢", "ko": "관세·무역", "en": "Tariffs & trade", "ja": "関税・貿易", "flags": re.I,
                "kw": r"관세|무역|수출\s?규제|수출통제|tariffs?|trade war|export controls?|sanctions?|보호무역|通商|関税|貿易|制裁"},
    "japan":   {"icon": "🗾", "ko": "일본 시장", "en": "Japan", "ja": "日本市場", "flags": 0,
                "kw": r"일본|닛케이|엔저|\bJapan(?:ese)?\b|\bNikkei\b|\bBOJ\b|日銀|日本株|東証|日経"},
}


def _theme_hay(i):
    g = i.get("gist") or {}
    return " ".join([(i.get("title") or {}).get(l, "") or "" for l in ("en", "ko", "ja")]
                    + [g.get("en", "") or ""] + [" ".join(i.get("tags") or [])])


def theme_matches(items, key):
    th = THEMES[key]
    rx = re.compile(th["kw"], th["flags"])
    return [i for i in items if rx.search(_theme_hay(i))]


STANCE_KO = {"bull": "강세", "bear": "약세", "watch": "관점"}


def _item_rows(its, rel=".."):
    return "".join(
        f'<li>{"<b class=sp-" + i.get("stance","watch") + ">" + STANCE_KO.get(i.get("stance") or "watch","관점") + "</b> " if i.get("stance") else ""}'
        f'<a href="{rel}/p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in its
    )


_HUB_CSS = """
body{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}
@media(prefers-color-scheme:dark){body{background:#0E0F12;color:#ECEDF1}}
a{color:inherit}.top{font-weight:800;text-decoration:none}
.kicker{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}
h1{font-size:26px;letter-spacing:-.02em;margin:0 0 6px}
.lead{color:#3E414B;font-size:15px;margin:8px 0 4px}
@media(prefers-color-scheme:dark){.lead{color:#C9CDD6}}
.tally{display:flex;gap:8px;margin:14px 0}
.tally b{padding:6px 14px;border-radius:999px;font-size:13px;color:#fff}
.tally .bl{background:#0E9F5E}.tally .wa{background:#6B7280}.tally .be{background:#E04438}
h2{font-size:16px;margin:26px 0 8px}
ul{list-style:none;padding:0}
li{padding:12px 0;border-bottom:1px solid #ECEDF1}
@media(prefers-color-scheme:dark){li{border-color:#26272E}}
li a{font-weight:600;text-decoration:none}
.d{display:block;font-size:12px;color:#8E93A0;margin-top:3px}
b.sp-bull{color:#0E9F5E}b.sp-bear{color:#E04438}b.sp-watch{color:#8E93A0}
.cta{display:inline-block;margin-top:24px;font-weight:700;text-decoration:none;background:#111;color:#fff;padding:11px 20px;border-radius:999px}
@media(prefers-color-scheme:dark){.cta{background:#fff;color:#111}}
footer{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}
@media(prefers-color-scheme:dark){footer{border-color:#26272E}}
footer a{color:#8E93A0}
"""


def _hub_page(url, title, metadesc, kicker, h1, lead, body_html, app_url, og_id=None):
    import os
    hub_ld = LD({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": title, "description": metadesc, "url": url, "inLanguage": "ko",
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"},
    })
    og_tags = ""
    tw = "summary"
    if og_id and os.path.exists(f"og/{og_id}.png"):
        img = BASE + "og/" + og_id + ".png"
        og_tags = (f'<meta property="og:image" content="{E(img)}">'
                   f'<meta property="og:image:width" content="1200">'
                   f'<meta property="og:image:height" content="630">'
                   f'<meta name="twitter:image" content="{E(img)}">')
        tw = "summary_large_image"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(url)}">
{og_tags}
<meta name="twitter:card" content="{tw}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{hub_ld}</script>
<style>{_HUB_CSS}</style>
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="kicker">{E(kicker)}</div>
<h1>{h1}</h1>
<p class="lead">{E(lead)}</p>
{body_html}
<a class="cta" href="{E(app_url)}">Stacks 앱에서 라이브로 보기 →</a>
<footer>
  요약·해설은 The Infrastructure Thesis의 창작물이며, 투자 자문이 아닌 정보 제공·논평입니다. 투자 판단과 그 책임은 이용자 본인에게 있습니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def _pseudo_og(og, iid, label, title_ko, avatar_local=None, frm="#0B1220", to="#3B4256"):
    """Render a 1200x630 share card for a hub page via make_og()."""
    import os
    if not og or os.path.exists(f"og/{iid}.png"):
        return
    try:
        make_og({"id": iid, "cover": {"from": frm, "to": to, "label": label},
                 "title": {"ko": title_ko, "en": title_ko},
                 "avatarImg": avatar_local or "", "source": "stacksdaily.com",
                 "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}, og)
    except Exception as e:
        print(f"[og-skip] {iid}: {e}")


def build_extra_pages(items, og):
    """Generate t/{theme}.html + r/{author}.html (+ share cards). Returns
    (theme_slugs, record_slugs)."""
    import os, urllib.parse
    # --- themes ---
    os.makedirs("t", exist_ok=True)
    theme_slugs = []
    for key, th in THEMES.items():
        t_items = sorted(theme_matches(items, key), key=lambda x: x.get("date", ""), reverse=True)
        if not t_items:
            continue
        theme_slugs.append(key)
        b = sum(1 for i in t_items if i.get("stance") == "bull")
        r = sum(1 for i in t_items if i.get("stance") == "bear")
        w = len(t_items) - b - r
        url = BASE + "t/" + key + ".html"
        app_url = BASE + "#theme-" + key
        title = f"{th['ko']} 강세 {b} · 약세 {r} 논쟁 · {SITE}"
        lead = (f"{th['ko']}를 둘러싼 전 세계 투자 논객들의 견해 {len(t_items)}건. "
                f"강세 {b} · 관점 {w} · 약세 {r}. 누가 맞았는지는 적중 기록으로 검증됩니다.")
        metadesc = clip(lead, 160)
        tally = (f'<div class="tally">{"<b class=bl>강세 " + str(b) + "</b>" if b else ""}'
                 f'{"<b class=wa>관점 " + str(w) + "</b>" if w else ""}'
                 f'{"<b class=be>약세 " + str(r) + "</b>" if r else ""}</div>')
        body = tally + f"<h2>관련 글 {len(t_items)}건</h2><ul>" + _item_rows(t_items) + "</ul>"
        _pseudo_og(og, "theme-" + key, th["en"].upper(),
                   f"{th['icon']} {th['ko']} 강세 {b} · 약세 {r}")
        html_out = _hub_page(url, title, metadesc, "THEME DEBATE", f"{th['icon']} {E(th['ko'])}",
                             lead, body, app_url, og_id="theme-" + key)
        open(f"t/{key}.html", "w", encoding="utf-8").write(html_out)
    for fn in os.listdir("t"):
        if fn.endswith(".html") and fn[:-5] not in theme_slugs:
            os.remove(f"t/{fn}")

    # --- author record pages ---
    try:
        srcmeta = json.load(open("sources.json", encoding="utf-8"))
    except Exception:
        srcmeta = {}
    name2slug = {}
    for k, v in srcmeta.items():
        if isinstance(v, dict) and v.get("source"):
            name2slug.setdefault(v["source"], k)  # first feed wins (serenity, not serenity_substack)
    os.makedirs("r", exist_ok=True)
    by_author = {}
    for i in items:
        by_author.setdefault(i.get("source", ""), []).append(i)
    record_slugs = []
    for name, its in by_author.items():
        if not name:
            continue
        slug = name2slug.get(name) or slugify(name)
        record_slugs.append(slug)
        its = sorted(its, key=lambda x: x.get("date", ""), reverse=True)
        calls = [i for i in its if i.get("stance") in ("bull", "bear")]
        hits = sum(1 for i in its if (i.get("outcome") or {}).get("status") == "hit")
        miss = sum(1 for i in its if (i.get("outcome") or {}).get("status") == "miss")
        url = BASE + "r/" + slug + ".html"
        app_url = BASE + "#record-" + urllib.parse.quote(name)
        title = f"{dispname(name)} 적중 기록 · 콜 {len(calls)}건 · {SITE}"
        lead = (f"{dispname(name)}의 글 {len(its)}건, 방향성 콜 {len(calls)}건. "
                + (f"검증된 예측 적중 {hits} · 빗나감 {miss}. " if (hits or miss) else "")
                + "각 콜의 '그 후 수익률'은 앱의 적중 기록에서 실시간으로 확인됩니다.")
        metadesc = clip(lead, 160)
        body = ""
        if calls:
            body += f"<h2>방향성 콜 {len(calls)}건</h2><ul>" + _item_rows(calls) + "</ul>"
        rest = [i for i in its if i not in calls]
        if rest:
            body += f"<h2>전체 글</h2><ul>" + _item_rows(rest[:20]) + "</ul>"
        av = its[0].get("avatarImg") or ""
        av_local = av if (av and not av.startswith("http") and os.path.exists(av)) else AV_CACHE.get(av)
        _pseudo_og(og, "record-" + slug, "TRACK RECORD",
                   f"{dispname(name)} 적중 기록", avatar_local=av_local,
                   frm="#111827", to="#334155")
        html_out = _hub_page(url, title, metadesc, "TRACK RECORD", E(dispname(name)),
                             lead, body, app_url, og_id="record-" + slug)
        open(f"r/{slug}.html", "w", encoding="utf-8").write(html_out)
    for fn in os.listdir("r"):
        if fn.endswith(".html") and fn[:-5] not in record_slugs:
            os.remove(f"r/{fn}")
    print(f"[extra] {len(theme_slugs)} theme pages + {len(record_slugs)} record pages")
    return theme_slugs, record_slugs


def _ping_indexnow(items):
    """Notify IndexNow (Bing, Naver, Yandex...) of recent URLs so new cards are
    discovered fast. Google does NOT use IndexNow (submit via Search Console)."""
    key = "stacks-f26ebf24-6bfbfb6a-bce6cc32-30287033"
    urls = [BASE, BASE + "articles.html"] + [BASE + "p/" + i["id"] + ".html" for i in items[:12]]
    import urllib.request
    payload = json.dumps({"host": "stacksdaily.com", "key": key,
                          "keyLocation": BASE + key + ".txt", "urlList": urls}).encode("utf-8")
    try:
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=payload,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=15) as r:
            print("[indexnow] pinged " + str(len(urls)) + " urls, status " + str(r.status))
    except Exception as e:
        print("[indexnow] skip: " + str(e))


def main():
    import os
    d = json.load(open("items.json", encoding="utf-8"))
    # --- Stacks house rule: em/en dashes are BANNED site-wide. Strip them at
    # build time so the site self-heals no matter what the generator produced. ---
    def _dedash(t, lang):
        if not t:
            return t
        sep = "\u3001" if lang == "ja" else ", "
        t = re.sub(r"\s+[\u2014\u2013\u2015]\s+", sep, t)
        t = re.sub(r"[\u2014\u2013\u2015]", "-", t)
        if lang == "ja":
            t = t.replace("\u3001\u3001", "\u3001")
        else:
            t = re.sub(r",\s*,", ", ", t)
            t = t.replace(" ,", ",")
        return t.strip()
    def _sanitize_dashes(doc):
        changed = False
        for it in doc.get("items", []):
            fields = [it.get("title"), it.get("gist"), it.get("why"), it.get("ask")]
            oc = it.get("outcome")
            if isinstance(oc, dict):
                fields.append(oc.get("note"))
            for val in fields:
                if isinstance(val, dict):
                    for lg in list(val.keys()):
                        nv = _dedash(val.get(lg) or "", lg)
                        if nv != val.get(lg):
                            val[lg] = nv; changed = True
            cov = it.get("cover")
            if isinstance(cov, dict) and isinstance(cov.get("label"), str):
                nl = re.sub(r"[\u2014\u2013\u2015]", " ", cov["label"]).strip()
                if nl != cov["label"]:
                    cov["label"] = nl; changed = True
        ents = doc.get("entities", {})
        if isinstance(ents, dict):
            for e in ents.values():
                if isinstance(e, dict):
                    for fld in ("desc", "longDesc", "sector", "ceo", "hq"):
                        val = e.get(fld)
                        if isinstance(val, dict):
                            for lg in list(val.keys()):
                                nv = _dedash(val.get(lg) or "", lg)
                                if nv != val.get(lg):
                                    val[lg] = nv; changed = True
        return changed
    if _sanitize_dashes(d):
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[dedash] em/en dashes stripped from items.json")
    # --- ts backfill: the app shows "N hours ago" for items <24h old, which needs
    # a per-item publish timestamp. Stamp any item missing `ts`: today's items get
    # "now" (approx. when they were carded, which is when this build runs on publish);
    # older items get their date at noon UTC so the app cleanly falls back to the date.
    # This guarantees ts regardless of which path added the card (scout or the
    # auto-publish session). Items that already carry ts are left untouched. ---
    def _stamp_ts(doc):
        changed = False
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_iso = datetime.now(timezone.utc).isoformat()
        for it in doc.get("items", []):
            if it.get("ts"):
                continue
            dt = it.get("date") or today
            it["ts"] = now_iso if dt == today else (dt + "T12:00:00+00:00")
            changed = True
        return changed
    if _stamp_ts(d):
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[ts] backfilled publish timestamps in items.json")
    items = d["items"]
    entities = d.get("entities", {}) or {}
    # --- Curated static glossary: a durable term index independent of the
    # generator. glossary.json terms are merged into entities so BOTH the app
    # (linkifyEntities tooltips) and the SEO pages link them. This lowers the
    # bar for what gets a definition without editing the publishing routine. ---
    try:
        _gloss = json.load(open("glossary.json", encoding="utf-8"))
    except Exception:
        _gloss = {}
    _gadd = 0
    for _gk, _gv in _gloss.items():
        if _gk not in entities:
            entities[_gk] = _gv; _gadd += 1
    if _gadd:
        d["entities"] = entities
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[glossary] merged " + str(_gadd) + " curated terms into entities")
    items = sorted(items, key=lambda x: x.get("date", ""), reverse=True)
    register_slugs_from_aliases(entities)
    pats = build_matcher(entities)

    # which entities each item touches (for internal links)
    item_ents = {i["id"]: item_entities(i, entities, pats) for i in items}
    # group articles per entity
    ent_items = {}
    for i in items:
        for key in item_ents[i["id"]]:
            ent_items.setdefault(key, []).append(i)

    # aggregates behind the record blocks on every article page
    build_records(items, entities)

    ids = {i["id"] for i in items}
    # social share images (best-effort: skipped if Pillow/fonts unavailable)
    og = _og_setup()
    _download_avatars(items)
    og_ok = set()
    if og:
        os.makedirs("og", exist_ok=True)
        for i in items:
            path = f"og/{i['id']}.png"
            if not os.path.exists(path):
                try:
                    make_og(i, og)
                except Exception as e:
                    print(f"[og-skip] {i['id']}: {e}")
            if os.path.exists(path):
                og_ok.add(i["id"])
        for fn in os.listdir("og"):
            if (fn.endswith(".png") and fn[:-4] not in ids
                    and not fn.startswith(("theme-", "record-"))):
                os.remove(f"og/{fn}")
    else:
        print("[og] Pillow/CJK font unavailable — skipping share images")

    for _lg in LANGS:
        os.makedirs(LANG_DIR[_lg], exist_ok=True)
    # write per-article pages, one URL per available language (with entity links
    # + share image). Titles of related items are resolved per language so the
    # "Related" list shows headlines instead of raw slugs.
    langs_of = {i["id"]: item_langs(i) for i in items}
    title_by_lang = {
        lg: {i["id"]: (i["title"].get(lg) or "") for i in items if lg in langs_of[i["id"]]}
        for lg in LANGS
    }
    written = {lg: set() for lg in LANGS}
    for i in items:
        keys = sorted(k for k in item_ents[i["id"]] if k in ent_items)
        lgs = langs_of[i["id"]] or ["ko"]
        for lg in lgs:
            links = [(ent_label(k, entities.get(k), lg), slugify(k)) for k in keys]
            path = f"{LANG_DIR[lg]}/{i['id']}.html"
            with open(path, "w", encoding="utf-8") as f:
                f.write(page_html(i, links, og_img=(i["id"] in og_ok), lang=lg,
                                  langs=lgs, rel_titles=title_by_lang[lg]))
            written[lg].add(i["id"])
    for lg in LANGS:
        for fn in os.listdir(LANG_DIR[lg]):
            if fn.endswith(".html") and fn[:-5] not in written[lg]:
                os.remove(f"{LANG_DIR[lg]}/{fn}")
    print("[pages] " + " · ".join(f"{lg}:{len(written[lg])}" for lg in LANGS))

    # write per-entity pages (only entities that actually have articles)
    os.makedirs("e", exist_ok=True)
    ent_slugs = {}
    for key, its in ent_items.items():
        slug = slugify(key)
        ent_slugs[slug] = key
        with open(f"e/{slug}.html", "w", encoding="utf-8") as f:
            f.write(entity_page(key, entities[key], its))
    for fn in os.listdir("e"):
        if fn.endswith(".html") and fn[:-5] not in ent_slugs:
            os.remove(f"e/{fn}")

    open("articles.html", "w", encoding="utf-8").write(articles_index(items))

    # theme debate + author record hub pages (SEO for #theme-/#record- views)
    theme_slugs, record_slugs = build_extra_pages(items, og)

    # weekly recap page (current week + dated archive) + its share card.
    # 카드는 매 빌드마다 덮어쓴다 (기사 OG와 달리 "이미 있으면 skip"이 아니다).
    try:
        make_scoreboard(items, og)
    except Exception as e:
        print(f"[og-skip] scoreboard: {e}")
    os.makedirs("week", exist_ok=True)
    iso = datetime.now(timezone.utc).date().isocalendar()
    wk_slug = f"{iso[0]}-w{iso[1]:02d}"
    wk_html = week_page(items, entities, item_ents, wk_slug)
    open(f"week/{wk_slug}.html", "w", encoding="utf-8").write(wk_html)
    open("this-week.html", "w", encoding="utf-8").write(
        wk_html.replace('<a class="top" href="../">', '<a class="top" href="./">')
               .replace('href="../p/', 'href="p/').replace('href="../e/', 'href="e/')
               .replace('href="../"', 'href="./"').replace('href="../articles.html"', 'href="articles.html"')
               .replace('href="../feed.xml"', 'href="feed.xml"').replace('href="../favicon-32.png"', 'href="favicon-32.png"')
    )
    week_slugs = sorted(fn[:-5] for fn in os.listdir("week") if fn.endswith(".html"))

    open("sitemap.xml", "w", encoding="utf-8").write(
        sitemap(items, list(ent_slugs.keys()), week_slugs, theme_slugs, record_slugs))
    for _lg in LANGS:
        open(FEED_FILE[_lg], "w", encoding="utf-8").write(feed(items, _lg))
    open("robots.txt", "w", encoding="utf-8").write(robots())
    _ping_indexnow(items)
    print(f"[ok] {len(items)} article pages + {len(ent_slugs)} entity pages + sitemap + feed + robots")


if __name__ == "__main__":
    main()
