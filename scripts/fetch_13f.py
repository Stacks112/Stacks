"""Stacks 13F sync — runs on GitHub Actions (schedule: quarterly-ish, e.g. weekly is fine).

Pulls the two most recent 13F-HR filings for a fixed roster of well-known
institutional investors from SEC EDGAR, aggregates each filing's
information-table rows by CUSIP (a single issuer is very often split across
many rows — one per internal manager/account — and must be summed, not left
as separate rows), diffs the aggregated holdings against the prior quarter,
and writes a single snapshot to portfolios.json.

Data source: SEC EDGAR (data.sec.gov + www.sec.gov/Archives). No scraping of
disallowed endpoints (cgi-bin/browse-edgar is robots-disallowed and is never
used here). Only the documented JSON/XML endpoints are used:
  - https://data.sec.gov/submissions/CIK{10-digit}.json
  - https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}/index.json
  - the information-table XML referenced from that index

Stdlib only (urllib + xml.etree.ElementTree) so this has no extra pip
dependency beyond what's already vendored for the rest of the pipeline.

Failure handling follows fetch_feeds.py's convention: one investor failing
to fetch must not take down the whole run. If portfolios.json already has a
good entry for that slug, it is kept as-is except for ok/error/checked_at.
If literally everything fails, the previous file is left untouched.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = "Stacks/1.0 (stacksdaily.com; contact@stacksdaily.com)"
REQUEST_SLEEP = 0.2  # SEC asks for <=10 req/s; this keeps us well under that
TOP_N = 25

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORTFOLIOS_PATH = os.path.join(ROOT, "portfolios.json")
CUSIP_MAP_PATH = os.path.join(ROOT, "cusip_map.json")
ITEMS_PATH = os.path.join(ROOT, "items.json")

INVESTORS = [
    {
        "slug": "berkshire",
        "cik": "0001067983",
        "filer": "BERKSHIRE HATHAWAY INC",
        "name": {"ko": "버크셔 해서웨이", "en": "Berkshire Hathaway", "ja": "バークシャー・ハサウェイ"},
        "manager": {"ko": "워런 버핏", "en": "Warren Buffett", "ja": "ウォーレン・バフェット"},
        "entity_key": None,  # not present in items.json entities (checked 2026-08-05)
        "desc": {
            "ko": "워런 버핏이 이끄는 지주회사로, 보험·철도·에너지 자회사와 함께 대규모 상장주식 포트폴리오를 운용한다. 13F 보고 대상 미국 주식 포지션은 분기 말 기준 수백억 달러 규모이며, 소수 종목에 집중된 장기 보유 스타일이 특징이다.",
            "en": "Warren Buffett's holding company, which runs insurance, rail and energy subsidiaries alongside a large public-equity portfolio. Its 13F-reportable U.S. stock positions total in the hundreds of billions of dollars and are concentrated in a small number of long-held names.",
            "ja": "ウォーレン・バフェット率いる持株会社。保険・鉄道・エネルギー子会社に加え、大規模な上場株式ポートフォリオを運用する。13F報告対象の米国株ポジションは四半期末時点で数百億ドル規模で、少数銘柄への長期集中保有が特徴。",
        },
    },
    {
        "slug": "pershing-square",
        "cik": "0001336528",
        "filer": "Pershing Square Capital Management, L.P.",
        "name": {"ko": "퍼싱스퀘어", "en": "Pershing Square", "ja": "パーシング・スクエア"},
        "manager": {"ko": "빌 애크먼", "en": "Bill Ackman", "ja": "ビル・アックマン"},
        "entity_key": None,
        "desc": {
            "ko": "빌 애크먼이 운용하는 액티비스트 헤지펀드로, 10개 안팎의 종목에 초집중 투자하는 전략을 쓴다. 13F 보고 포트폴리오는 소수의 대형 포지션이 대부분을 차지한다.",
            "en": "An activist hedge fund run by Bill Ackman that concentrates on roughly a dozen or fewer positions at a time. Its 13F portfolio is dominated by a handful of large stakes.",
            "ja": "ビル・アックマンが運用するアクティビスト・ヘッジファンドで、10銘柄前後への超集中投資を戦略とする。13F報告ポートフォリオは少数の大型ポジションが大半を占める。",
        },
    },
    {
        "slug": "ark",
        "cik": "0001697748",
        "filer": "ARK INVESTMENT MANAGEMENT LLC",
        "name": {"ko": "ARK 인베스트", "en": "ARK Invest", "ja": "アーク・インベスト"},
        "manager": {"ko": "캐시 우드", "en": "Cathie Wood", "ja": "キャシー・ウッド"},
        "entity_key": None,
        "desc": {
            "ko": "캐시 우드가 이끄는 액티브 운용사로, 혁신·성장 테마의 상장지수펀드(ARKK 등)를 통해 파괴적 혁신 기업에 집중 투자한다. 13F 포트폴리오는 수백 개 종목에 걸쳐 있으며 회전율이 높은 편이다.",
            "en": "An active manager led by Cathie Wood, best known for thematic innovation-growth ETFs such as ARKK. Its 13F portfolio spans a large number of names and turns over relatively quickly.",
            "ja": "キャシー・ウッド率いるアクティブ運用会社。ARKKなどのイノベーション・成長テーマ型ETFを通じて破壊的イノベーション企業に集中投資する。13Fポートフォリオは多数の銘柄にまたがり、回転率も比較的高い。",
        },
    },
    {
        "slug": "duquesne",
        "cik": "0001536411",
        "filer": "Duquesne Family Office LLC",
        "name": {"ko": "듀케인 패밀리 오피스", "en": "Duquesne Family Office", "ja": "デュケーヌ・ファミリーオフィス"},
        "manager": {"ko": "스탠리 드러켄밀러", "en": "Stanley Druckenmiller", "ja": "スタンレー・ドラッケンミラー"},
        "entity_key": None,
        "desc": {
            "ko": "스탠리 드러켄밀러가 자신의 자산을 운용하는 패밀리 오피스로, 매크로 관점에 따라 종목·비중을 자주 바꾸는 것으로 알려져 있다. 13F 포트폴리오는 옵션 포지션을 포함해 회전율이 높다.",
            "en": "Stanley Druckenmiller's family office, known for shifting names and sizing frequently around a top-down macro view. Its 13F filings include options positions and turn over quickly.",
            "ja": "スタンレー・ドラッケンミラーが自身の資産を運用するファミリーオフィス。マクロ観に基づき銘柄・比率を頻繁に入れ替えることで知られる。13Fポートフォリオはオプションポジションを含み回転率が高い。",
        },
    },
    # Bridgewater was deliberately dropped (june's call, 2026-08-05): it's a
    # thousand-plus-position macro book (hence a 583KB infotable), which
    # doesn't fit a "what did the famous investor buy" feature, and Ray Dalio
    # is no longer in a day-to-day investment role there. Do not re-add
    # without a product decision to do so.
    {
        "slug": "appaloosa",
        "cik": "0001656456",
        "filer": "Appaloosa LP",
        "name": {"ko": "아팔루사", "en": "Appaloosa", "ja": "アパルーサ"},
        "manager": {"ko": "데이비드 테퍼", "en": "David Tepper", "ja": "デビッド・テッパー"},
        "entity_key": None,
        "desc": {
            "ko": "데이비드 테퍼가 운용하는 헤지펀드로, 대형 기술주와 매크로 베팅 위주의 집중 포트폴리오로 알려져 있다. 13F 보고 종목 수는 수십 개 안팎이다.",
            "en": "A hedge fund run by David Tepper, known for a concentrated portfolio weighted toward large-cap tech and macro-driven bets. Its 13F typically lists on the order of a few dozen positions.",
            "ja": "デビッド・テッパーが運用するヘッジファンドで、大型テック株とマクロ主導のベットに偏った集中ポートフォリオで知られる。13F報告銘柄数はおおむね数十程度。",
        },
    },
    {
        # CIK/filer name verified against data.sec.gov/submissions/CIK0002045724.json
        # (2026-08-05): entity name "Situational Awareness LP", 13F-HR filings
        # 0002045724-26-000008 (period 2026-03-31) and 0002045724-26-000002
        # (period 2025-12-31). This is a genuinely options-heavy filer (most of
        # its top positions are PUT/CALL rows sharing a CUSIP with the common
        # stock), which is exactly the case task 2 (put/call handling) exists for.
        "slug": "situational-awareness",
        "cik": "0002045724",
        "filer": "Situational Awareness LP",
        "name": {
            "ko": "시추에이셔널 어웨어니스",
            "en": "Situational Awareness LP",
            "ja": "シチュエーショナル・アウェアネス",
        },
        "manager": {"ko": "레오폴드 아셴브레너", "en": "Leopold Aschenbrenner", "ja": "レオポルド・アッシェンブレナー"},
        "entity_key": None,
        "desc": {
            "ko": "전 OpenAI 연구원 레오폴드 아셴브레너가 2024년 에세이 'Situational Awareness'로 AGI 임박론을 편 뒤 차린 헤지펀드로, AI 인프라·반도체·전력 관련 종목에 집중 베팅한다. 콜·풋 옵션으로 방향성을 강하게 표현해, 보통주만 봐서는 포지션의 실제 색깔(강세/약세)을 읽기 어렵다.",
            "en": "A hedge fund founded by former OpenAI researcher Leopold Aschenbrenner after his 2024 essay 'Situational Awareness' argued AGI was near. It concentrates on AI infrastructure, semiconductors and power names, and leans heavily on call and put options to express direction, so reading the common-stock rows alone misses most of what the fund is actually betting on.",
            "ja": "元OpenAI研究者のレオポルド・アッシェンブレナーが、2024年のエッセイ『Situational Awareness』でAGI到来が近いと論じた後に設立したヘッジファンド。AIインフラ・半導体・電力関連銘柄に集中し、コール・プットオプションで方向性を強く表現するため、普通株の行だけを見てもポジションの本当の強気・弱気は読み取れない。",
        },
    },
    # Added 2026-08-07: active, recognizable managers with a current
    # 2026-03-31 13F-HR and a concentrated enough public-equity book to fit
    # this product. CIKs and filer names were checked against SEC submissions.
    {
        "slug": "third-point",
        "cik": "0001040273",
        "filer": "Third Point LLC",
        "name": {"ko": "서드포인트", "en": "Third Point", "ja": "サード・ポイント"},
        "manager": {"ko": "대니얼 로엡", "en": "Daniel Loeb", "ja": "ダニエル・ローブ"},
        "entity_key": None,
        "desc": {
            "ko": "대니얼 로엡이 이끄는 이벤트 드리븐·행동주의 투자사로, 기업 분할·경영 개선·자본 배분 변화 같은 촉매가 있는 종목에 집중한다. 13F는 공개된 미국 주식 포지션만 보여준다.",
            "en": "An event-driven and activist investment firm led by Daniel Loeb, focused on catalysts such as spin-offs, operational change and shifts in capital allocation. Its 13F shows only the firm's reportable U.S. equity positions.",
            "ja": "ダニエル・ローブ率いるイベントドリブン・アクティビスト投資会社。スピンオフや経営改善、資本配分の変化などのカタリストに注目する。13Fは報告対象の米国株ポジションのみを示す。",
        },
    },
    {
        "slug": "baupost",
        "cik": "0001061768",
        "filer": "BAUPOST GROUP LLC/MA",
        "name": {"ko": "바우포스트", "en": "Baupost", "ja": "バウポスト"},
        "manager": {"ko": "세스 클라먼", "en": "Seth Klarman", "ja": "セス・クラーマン"},
        "entity_key": None,
        "desc": {
            "ko": "세스 클라먼이 이끄는 가치투자 운용사로, 안전마진과 부실·특수상황 투자에 초점을 둔다. 13F는 전체 전략 중 공개된 미국 상장주식 부분만 보여준다.",
            "en": "A value-oriented investment firm led by Seth Klarman, focused on margin of safety and distressed or special situations. Its 13F captures only the public U.S. equity portion of a broader strategy.",
            "ja": "セス・クラーマン率いるバリュー投資会社。安全余裕度とディストレスト・特殊状況投資を重視する。13Fは幅広い戦略のうち公開された米国上場株部分のみを示す。",
        },
    },
    {
        "slug": "tci",
        "cik": "0001647251",
        "filer": "TCI Fund Management Ltd",
        "name": {"ko": "TCI 펀드", "en": "TCI Fund Management", "ja": "TCIファンド・マネジメント"},
        "manager": {"ko": "크리스 혼", "en": "Chris Hohn", "ja": "クリス・ホーン"},
        "entity_key": None,
        "desc": {
            "ko": "크리스 혼이 설립한 장기 행동주의 투자사로, 지속 가능한 경쟁우위를 가진 소수의 대형 기업에 집중하고 지배구조·자본배분 개선을 요구한다.",
            "en": "A long-term activist investment firm founded by Chris Hohn, concentrating on a small number of high-quality companies with durable competitive advantages and pushing for better governance and capital allocation.",
            "ja": "クリス・ホーンが設立した長期アクティビスト投資会社。持続的な競争優位を持つ少数の大型企業に集中し、ガバナンスと資本配分の改善を求める。",
        },
    },
    {
        "slug": "coatue",
        "cik": "0001135730",
        "filer": "COATUE MANAGEMENT LLC",
        "name": {"ko": "코투", "en": "Coatue", "ja": "コートゥー"},
        "manager": {"ko": "필리프 라퐁", "en": "Philippe Laffont", "ja": "フィリップ・ラフォン"},
        "entity_key": None,
        "desc": {
            "ko": "필리프 라퐁이 이끄는 기술·성장주 중심 투자 플랫폼으로, 공개시장과 비공개시장에서 기술·미디어·통신·소비재 기업에 투자한다.",
            "en": "A technology- and growth-focused investment platform led by Philippe Laffont, investing across public and private markets in technology, media, communications and consumer companies.",
            "ja": "フィリップ・ラフォン率いるテクノロジー・成長株中心の投資プラットフォーム。公開市場と未公開市場の両方で、テクノロジー、メディア、通信、消費関連企業に投資する。",
        },
    },
    {
        "slug": "soros",
        "cik": "0001029160",
        "filer": "SOROS FUND MANAGEMENT LLC",
        "name": {"ko": "소로스 펀드", "en": "Soros Fund Management", "ja": "ソロス・ファンド・マネジメント"},
        "manager": {"ko": "조지 소로스", "en": "George Soros", "ja": "ジョージ・ソロス"},
        "entity_key": None,
        "desc": {
            "ko": "조지 소로스가 설립한 투자 운용사로, 글로벌 매크로와 이벤트 드리븐 관점에서 주식·채권·통화 등 여러 자산을 운용한다. 13F는 공개된 미국 주식 포지션 일부만 보여준다.",
            "en": "An investment firm founded by George Soros that has historically combined global macro and event-driven views across equities, bonds and currencies. Its 13F shows only part of the firm's public U.S. equity positions.",
            "ja": "ジョージ・ソロスが設立した投資運用会社。グローバルマクロとイベントドリブンの視点で株式・債券・通貨などを運用する。13Fは公開された米国株ポジションの一部のみを示す。",
        },
    },
    {
        # CIK/filer name verified against data.sec.gov/submissions/CIK0000921669.json
        # (2026-08-07): latest 13F period 2026-03-31.
        "slug": "carl-icahn",
        "cik": "0000921669",
        "filer": "ICAHN CARL C",
        "name": {"ko": "아이칸 엔터프라이즈", "en": "Icahn Enterprises", "ja": "アイカーン・エンタープライジズ"},
        "manager": {"ko": "칼 아이칸", "en": "Carl Icahn", "ja": "カール・アイカーン"},
        "entity_key": None,
        "desc": {
            "ko": "칼 아이칸이 지배하는 투자회사로, 행동주의 투자와 기업 지배구조·자본배분 변화 요구로 잘 알려져 있다. 13F는 다양한 전략 중 공개된 미국 상장주식 포지션만 보여준다.",
            "en": "An investment company controlled by Carl Icahn, known for activist campaigns and pushing companies to change governance and capital allocation. Its 13F shows only the public U.S. equity portion of a broader set of strategies.",
            "ja": "カール・アイカーンが支配する投資会社。アクティビスト投資や企業のガバナンス・資本配分の変更要求で知られる。13Fは幅広い戦略のうち公開された米国上場株ポジションのみを示す。",
        },
    },
    {
        # CIK/filer name verified against data.sec.gov/submissions/CIK0001167483.json
        # (2026-08-07): latest 13F period 2026-03-31.
        "slug": "tiger-global",
        "cik": "0001167483",
        "filer": "TIGER GLOBAL MANAGEMENT LLC",
        "name": {"ko": "타이거 글로벌", "en": "Tiger Global", "ja": "タイガー・グローバル"},
        "manager": {"ko": "체이스 콜먼", "en": "Chase Coleman", "ja": "チェース・コールマン"},
        "entity_key": None,
        "desc": {
            "ko": "체이스 콜먼이 이끄는 글로벌 성장주 투자사로, 인터넷·소프트웨어·소비자 플랫폼 기업에 장기적으로 투자해 왔다. 13F는 공개된 미국 주식 포트폴리오만 보여준다.",
            "en": "A global growth investor led by Chase Coleman that has backed internet, software and consumer-platform companies across public and private markets. Its 13F shows only the public U.S. equity portfolio.",
            "ja": "チェース・コールマン率いるグローバル成長株投資会社。インターネット、ソフトウェア、消費者向けプラットフォーム企業に公開・非公開市場の両方で投資してきた。13Fは公開された米国株ポートフォリオのみを示す。",
        },
    },
    {
        # CIK/filer name verified against data.sec.gov/submissions/CIK0001103804.json
        # (2026-08-07): latest 13F period 2026-03-31.
        "slug": "viking",
        "cik": "0001103804",
        "filer": "VIKING GLOBAL INVESTORS LP",
        "name": {"ko": "바이킹 글로벌", "en": "Viking Global", "ja": "バイキング・グローバル"},
        "manager": {"ko": "안드레아스 할보르센", "en": "Andreas Halvorsen", "ja": "アンドレアス・ハルヴォルセン"},
        "entity_key": None,
        "desc": {
            "ko": "안드레아스 할보르센이 공동 설립한 글로벌 롱·숏 투자사로, 기업의 펀더멘털과 산업 변화에 기반해 소수의 고확신 포지션을 운용한다. 13F는 공개된 미국 주식 롱 포지션만 보여준다.",
            "en": "A global long-short investment firm co-founded by Andreas Halvorsen, building high-conviction positions around company fundamentals and industry change. Its 13F shows only disclosed U.S. equity long positions.",
            "ja": "アンドレアス・ハルヴォルセンが共同設立したグローバル・ロングショート投資会社。企業のファンダメンタルズと産業の変化を軸に、高い確信度のポジションを運用する。13Fは公開された米国株ロングポジションのみを示す。",
        },
    },
    {
        # CIK/filer name verified against the 2026-03-31 Oaktree 13F filing.
        "slug": "oaktree",
        "cik": "0000949509",
        "filer": "OAKTREE CAPITAL MANAGEMENT LP",
        "name": {"ko": "오크트리 캐피털", "en": "Oaktree Capital Management", "ja": "オークツリー・キャピタル・マネジメント"},
        "manager": {"ko": "하워드 막스", "en": "Howard Marks", "ja": "ハワード・マークス"},
        "entity_key": None,
        "desc": {
            "ko": "하워드 막스가 공동 설립한 대체투자 운용사로, 리스크·사이클·안전마진을 중시하는 투자 철학으로 유명하다. 13F는 채권·사모·부실채권 등 전체 전략 중 공개된 미국 주식 부분만 보여준다.",
            "en": "An alternative investment firm co-founded by Howard Marks, known for its focus on risk, cycles and margin of safety. Its 13F captures only the public U.S. equity portion of a broader credit, private-market and distressed-investing platform.",
            "ja": "ハワード・マークスが共同設立したオルタナティブ投資会社。リスク、サイクル、安全余裕度を重視する投資哲学で知られる。13Fはクレジット、プライベート市場、不良債権など幅広い戦略のうち公開された米国株部分のみを示す。",
        },
    },
    {
        # Scion's latest available 13F is 2025-09-30 as of 2026-08-07;
        # the UI exposes the filing period so the staleness is explicit.
        "slug": "scion",
        "cik": "0001649339",
        "filer": "Scion Asset Management, LLC",
        "name": {"ko": "사이온 애셋 매니지먼트", "en": "Scion Asset Management", "ja": "サイオン・アセット・マネジメント"},
        "manager": {"ko": "마이클 버리", "en": "Michael Burry", "ja": "マイケル・バーリ"},
        "entity_key": None,
        "desc": {
            "ko": "마이클 버리가 이끄는 투자사로, 영화 ‘빅쇼트’로 널리 알려진 역발상·가치투자 스타일을 추구한다. SEC에 공개된 최신 13F는 회사 전체 전략이 아닌 보고 대상 미국 주식 포지션만 보여준다.",
            "en": "An investment firm led by Michael Burry, widely known for the contrarian and value-oriented style portrayed in The Big Short. Its latest available SEC 13F shows only reportable U.S. equity positions, not the firm's full strategy.",
            "ja": "『マネー・ショート 華麗なる大逆転』で広く知られるマイケル・バーリ率いる投資会社。逆張り・バリュー投資を志向し、SECで公開された最新13Fは会社全体の戦略ではなく報告対象の米国株ポジションのみを示す。",
        },
    },
]


def http_get(url: str, retries: int = 3) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            time.sleep(REQUEST_SLEEP)
            return data
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 404):
                raise
            time.sleep(1 + attempt)
        except Exception as e:  # noqa: BLE001 - network errors, retry
            last_err = e
            time.sleep(1 + attempt)
    raise last_err


def local_tag(el) -> str:
    """Strip an XML namespace off an element tag: '{uri}infoTable' -> 'infoTable'."""
    t = el.tag
    return t.split("}", 1)[1] if "}" in t else t


def find_child_text(el, name: str):
    for child in el:
        if local_tag(child) == name:
            return child
    return None


def find_two_recent_13f_hr(cik: str):
    """Return up to 2 most recent 13F-HR filings (excluding /A amendments),
    most recent first, as dicts with reportDate/filingDate/accessionNumber.
    """
    data = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = data["filings"]["recent"]
    forms = recent["form"]
    out = []
    for i, form in enumerate(forms):
        if form == "13F-HR":
            out.append({
                "reportDate": recent["reportDate"][i],
                "filingDate": recent["filingDate"][i],
                "accessionNumber": recent["accessionNumber"][i],
            })
            if len(out) == 2:
                break
    # Older filers may need the paginated "files" list if fewer than 2 were
    # found in "recent" (recent caps at 1000 entries; not an issue for any
    # of our roster today, but keep this from silently returning 0/1).
    return out


def find_infotable_url(cik_int: str, accession_nodash: str) -> str:
    """Find the information-table XML inside a filing's directory.

    The filename is NOT standardized across filers/filing agents: it may be
    "infotable.xml", a filer-chosen name like "form13f_20260331.xml", a
    CamelCase name like "Form13FInfoTable.xml", or a bare accession-like
    number such as "53405.xml" (seen on Berkshire's own filings). We pick
    every *.xml candidate that isn't primary_doc.xml, and if more than one
    remains, fetch each and keep the one whose root element (by local name,
    namespace stripped) is informationTable / infoTable.
    """
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}"
    idx = json.loads(http_get(f"{base}/index.json"))
    items = idx["directory"]["item"]
    candidates = [
        it["name"] for it in items
        if it["name"].lower().endswith(".xml") and it["name"].lower() != "primary_doc.xml"
    ]
    if not candidates:
        raise ValueError(f"no infotable xml candidate found under {base}")
    if len(candidates) == 1:
        return f"{base}/{candidates[0]}"
    for name in candidates:
        url = f"{base}/{name}"
        try:
            head = http_get(url)[:2000].decode("utf-8", "ignore").lower()
        except Exception:
            continue
        if "informationtable" in head or "infotable" in head:
            return url
    # Fall back to the first candidate rather than crashing the whole investor.
    return f"{base}/{candidates[0]}"


def parse_infotable(xml_bytes: bytes):
    """Return a list of raw rows: dict(issuer, cusip, titleOfClass, value,
    shares, sshType, putCall)."""
    root = ET.fromstring(xml_bytes)
    rows = []
    # infoTable elements can appear anywhere under the root, namespaced or not.
    for el in root.iter():
        if local_tag(el) != "infoTable":
            continue
        issuer_el = find_child_text(el, "nameOfIssuer")
        cusip_el = find_child_text(el, "cusip")
        title_el = find_child_text(el, "titleOfClass")
        value_el = find_child_text(el, "value")
        shrs_el = find_child_text(el, "shrsOrPrnAmt")
        put_call_el = find_child_text(el, "putCall")
        ssh_amt, ssh_type = None, None
        if shrs_el is not None:
            amt_el = find_child_text(shrs_el, "sshPrnamt")
            type_el = find_child_text(shrs_el, "sshPrnamtType")
            ssh_amt = amt_el.text.strip() if amt_el is not None and amt_el.text else None
            ssh_type = type_el.text.strip() if type_el is not None and type_el.text else None
        rows.append({
            "issuer": (issuer_el.text or "").strip() if issuer_el is not None else "",
            "cusip": (cusip_el.text or "").strip() if cusip_el is not None else "",
            "titleOfClass": (title_el.text or "").strip() if title_el is not None and title_el.text else "",
            "value": int(round(float(value_el.text.strip()))) if value_el is not None and value_el.text else 0,
            "shares": int(round(float(ssh_amt))) if ssh_amt else 0,
            "sshType": ssh_type,
            # Normalized to "PUT" / "CALL" / None. SEC filers write "Put"/"Call"
            # (see parse output for Situational Awareness LP); we uppercase so
            # downstream grouping/display doesn't depend on filer capitalization.
            "putCall": ((put_call_el.text or "").strip().upper() or None) if put_call_el is not None and put_call_el.text else None,
        })
    return rows


class ValueUnitError(Exception):
    """Raised when a filing's <value> field can't be trusted even after the
    thousands-vs-dollars rescale (see fix_value_units). The caller treats
    this like any other per-investor fetch failure: ok=False + error, and
    nothing gets published for that filer rather than a bogus number."""


def fix_value_units(rows, filer_label: str = ""):
    """Detect filings whose <value> is reported in thousands of dollars
    instead of whole dollars (a legacy convention some filing agents still
    use even though current SEC guidance calls for whole dollars) and
    rescale.

    Heuristic: for common-stock rows with a nonzero share count, the
    implied price-per-share (value / shares) should be a plausible equity
    price. If the *median* implied price across the filing is under $2,
    real institutional 13F holdings essentially never look like that in
    aggregate, so we assume the filer reported thousands and multiply by
    1000. This only ever fires filing-wide (never per row), so it can't
    partially corrupt a table that's genuinely dollar-denominated.

    Safety net: if the median implied price is still implausible after
    this correction (under $1 or over $10,000), we don't guess further -
    we raise so the investor is marked failed instead of publishing a
    number that's probably wrong.
    """
    prices = []
    for r in rows:
        if r["sshType"] == "SH" and r["shares"] > 0 and not r["putCall"]:
            prices.append(r["value"] / r["shares"])
    if not prices:
        return rows
    prices.sort()
    median = prices[len(prices) // 2]
    scaled = False
    if median < 2:
        print(f"[warn] {filer_label}: value field looks like thousands of dollars "
              f"(median implied price/share was ${median:.4f}) - rescaling x1000",
              file=sys.stderr)
        for r in rows:
            r["value"] *= 1000
        scaled = True
        prices = [p * 1000 for p in prices]
        median = prices[len(prices) // 2]
    if median < 1 or median > 10000:
        raise ValueUnitError(
            f"{filer_label}: median implied price/share is ${median:,.2f} even after "
            f"the thousands-rescale check (rescaled={scaled}) - value field looks "
            f"wrong, refusing to publish this filer's numbers"
        )
    return rows


def group_by_cusip(rows):
    """Sum value/shares per (CUSIP, putCall), excluding non-share amounts
    (sshPrnamtType != 'SH', e.g. bond face value 'PRN').

    ★ Options are included, not dropped. A PUT or CALL row shares the same
    CUSIP as the underlying common stock (the CUSIP identifies the security
    class, not long-vs-derivative direction), so grouping by CUSIP alone
    would silently net long stock against short-via-puts, or merge two
    economically opposite bets into one number. That used to be exactly what
    this function did (any row with putCall set was skipped entirely), which
    is fine for a filer with no options but produces an empty or badly wrong
    portfolio for one that expresses most of its view through options (see
    Situational Awareness LP). Grouping by the (cusip, putCall) pair keeps
    common stock, puts and calls on the same issuer as three separate
    positions, which is what they economically are.
    """
    groups = {}
    for r in rows:
        if r["sshType"] != "SH":
            continue
        if not r["cusip"]:
            continue
        put_call = r["putCall"]
        key = (r["cusip"], put_call)
        g = groups.setdefault(key, {"issuer": r["issuer"], "titleOfClass": r["titleOfClass"], "put_call": put_call, "value": 0, "shares": 0})
        g["value"] += r["value"]
        g["shares"] += r["shares"]
        # Keep the longest issuer name variant seen (rows sometimes differ in
        # punctuation/truncation); doesn't affect the number crunching.
        if len(r["issuer"]) > len(g["issuer"]):
            g["issuer"] = r["issuer"]
        if not g["titleOfClass"] and r["titleOfClass"]:
            g["titleOfClass"] = r["titleOfClass"]
    return groups


VALID_TICKER_SUFFIXES = (".us", ".ks", ".kq", ".jp", ".t")
VALID_TICKER_RE = re.compile(r"^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$")

# nameOfIssuer occasionally embeds a share-class marker itself (not just in
# titleOfClass); strip it before using the name as a merged/representative
# label so "FOO INC CLASS A" and "FOO INC CLASS C" collapse to "FOO INC".
_CLASS_SUFFIX_RE = re.compile(r"\s+(CLASS\s+[A-Z]|CL\s+[A-Z]|SER(?:IES)?\s+[A-Z])$", re.IGNORECASE)


def strip_class_suffix(name: str) -> str:
    return _CLASS_SUFFIX_RE.sub("", name).strip()


def normalize_ticker(raw):
    """Coerce a cusip_map ticker into the '{lowercase-symbol}.{suffix}' shape
    the worker's yahooSymbol() expects (worker/index.js:739 special-cases the
    '.us' suffix; other markets keep their own suffix).

    - Already-suffixed values (.us/.ks/.kq/.jp/.t) are just lowercased.
    - A bare alphanumeric symbol (e.g. "AMD", "BAC") gets ".us" appended,
      since every filer in INVESTORS is a US institutional manager and every
      13F holding is, by definition, a US-listed reportable security.
    - A class separator in a ticker (e.g. "LEN.B") is retained and gets the
      .us suffix. This is needed for OpenFIGI's class-level CUSIP results.
    - Anything else (dual-listing notations like "688981 / 0981", stray
      whitespace, etc.) is not a usable single ticker and is dropped (None)
      rather than guessed at.
    """
    if not raw:
        return None
    t = raw.strip()
    if not t or " " in t:
        return None
    # OpenFIGI uses LEN/B and MOG/A for US share classes. Yahoo accepts the
    # equivalent LEN-B/MOG-A form after the worker removes the .us suffix.
    if t.count("/") == 1 and re.fullmatch(r"[A-Za-z0-9]+/[A-Za-z0-9]+", t):
        t = t.replace("/", "-")
    elif "/" in t:
        return None
    low = t.lower()
    if low.endswith(VALID_TICKER_SUFFIXES):
        return low
    if VALID_TICKER_RE.fullmatch(t):
        return f"{low}.us"
    return None


def merge_share_classes(groups: dict, cusip_map: dict):
    """Second aggregation pass on top of group_by_cusip().

    CUSIP-level grouping alone still leaves genuine duplicates on screen:
    the same company issues multiple share classes under different CUSIPs
    (Alphabet's GOOGL/GOOG being the obvious one). Two different fixes for
    two different situations:

      - If we have a ticker for the CUSIP (cusip_map), that ticker is the
        real identity: sum value/shares across every CUSIP that maps to the
        same ticker, keep the highest-value CUSIP as the representative
        "cusip" field, and use a class-suffix-stripped issuer name.
      - If there's no ticker (not in cusip_map) and two or more CUSIPs
        happen to share the exact issuer name, they are NOT merged (they
        really are different securities) but get titleOfClass appended in
        parens so the UI can tell them apart, e.g.
        "LIBERTY LIVE HOLDINGS INC (COM SHS SER C)".

    Returns a dict keyed by ("T", ticker, putCall) or ("C", cusip, putCall) ->
    {cusip, issuer, ticker, entity_key, put_call, value, shares}. The key (not
    just the cusip) is what quarter-over-quarter change detection matches on,
    so a company keeps its identity across quarters even if which specific
    class-CUSIP dominates shifts.

    ★ putCall rides along inside the key. Common stock, puts and calls on the
    same ticker/CUSIP must never merge into one bucket (a long stock position
    and a put on the same name are opposite bets), so every key here is really
    a (identity, putCall) pair. For filings without options putCall is always
    None on every row, so this collapses back to the old ("T", ticker) /
    ("C", cusip) keying - no behavior change for those portfolios.
    """
    by_ticker = {}
    standalone = []
    for (cusip, put_call), g in groups.items():
        mapping = cusip_map.get(cusip, {})
        ticker = normalize_ticker(mapping.get("ticker"))
        if ticker:
            bucket_key = (ticker, put_call)
            bucket = by_ticker.setdefault(bucket_key, {"members": [], "value": 0, "shares": 0})
            bucket["members"].append((cusip, g, mapping.get("entity_key")))
            bucket["value"] += g["value"]
            bucket["shares"] += g["shares"]
        else:
            standalone.append((cusip, put_call, g, mapping.get("entity_key")))

    merged = {}
    for (ticker, put_call), bucket in by_ticker.items():
        rep_cusip, rep_g, rep_entity_key = max(bucket["members"], key=lambda m: m[1]["value"])
        merged[("T", ticker, put_call)] = {
            "cusip": rep_cusip,
            "issuer": strip_class_suffix(rep_g["issuer"]),
            "ticker": ticker,
            "entity_key": rep_entity_key,
            "put_call": put_call,
            "value": bucket["value"],
            "shares": bucket["shares"],
        }

    name_counts = {}
    for cusip, put_call, g, _ in standalone:
        key = (g["issuer"].strip().upper(), put_call)
        name_counts[key] = name_counts.get(key, 0) + 1
    for cusip, put_call, g, entity_key in standalone:
        issuer = g["issuer"]
        if name_counts[(issuer.strip().upper(), put_call)] > 1 and g.get("titleOfClass"):
            issuer = f"{issuer} ({g['titleOfClass']})"
        merged[("C", cusip, put_call)] = {
            "cusip": cusip,
            "issuer": issuer,
            "ticker": None,
            "entity_key": entity_key,
            "put_call": put_call,
            "value": g["value"],
            "shares": g["shares"],
        }
    return merged


def holding_record(key, g: dict, prev_merged, sector_map: dict, *, value=None, shares=None, change=None, prev_shares=None):
    """Serialize one merged position for either the full or visible list."""
    if value is None:
        value = g["value"]
    if shares is None:
        shares = g["shares"]
    if change is None and prev_merged is not None:
        prev = prev_merged.get(key)
        if prev is None:
            change = "new"
        else:
            prev_shares = prev["shares"]
            if shares > prev["shares"]:
                change = "add"
            elif shares < prev["shares"]:
                change = "trim"
            else:
                change = "hold"
    return {
        "cusip": g["cusip"],
        "issuer": g["issuer"],
        "ticker": g["ticker"],
        "entity_key": g["entity_key"],
        "put_call": g.get("put_call"),  # "PUT" / "CALL" / None (common stock)
        "sector": sector_map.get(g["entity_key"]) if g.get("entity_key") else None,
        "value": value,
        "shares": shares,
        "weight": None,
        "change": change,
        "prev_shares": prev_shares,
    }


def compute_holdings(merged: dict, prev_merged, sector_map: dict):
    total_value = sum(g["value"] for g in merged.values())
    ranked = sorted(merged.items(), key=lambda kv: -kv[1]["value"])
    all_holdings = []
    for key, g in ranked:
        row = holding_record(key, g, prev_merged, sector_map)
        row["weight"] = round(g["value"] / total_value, 4) if total_value else 0
        all_holdings.append(row)

    holdings = []
    seen_keys = set()
    for idx, (key, g) in enumerate(ranked[:TOP_N]):
        seen_keys.add(key)
        holdings.append(all_holdings[idx])
    # Positions that were in the *previous* quarter's top-N but vanished
    # entirely this quarter get an explicit exit row appended.
    if prev_merged is not None:
        prev_ranked_keys = [k for k, _ in sorted(prev_merged.items(), key=lambda kv: -kv[1]["value"])[:TOP_N]]
        for key in prev_ranked_keys:
            if key in seen_keys or key in merged:
                continue
            prev = prev_merged[key]
            exit_row = dict(prev)
            exit_row.update({"value": 0, "shares": 0, "weight": 0, "change": "exit", "prev_shares": prev["shares"]})
            holdings.append(exit_row)
    return holdings, all_holdings, total_value, len(merged)


def compute_activity(merged: dict, prev_merged, unavailable_reason=None):
    """Full-portfolio activity stats.

    ★ Must be computed over `merged`/`prev_merged` (every position in the
    filing), never over the truncated top-N `holdings` list that
    compute_holdings() returns - `holdings` only keeps the top TOP_N positions
    plus explicit exits from the *previous* top-N, so counting "new" or
    "exited" from it undercounts anything that entered or left outside the
    top 25 (e.g. ARK, which has 147 total positions this quarter but only 25
    stored).

    ★ Never returns a bare null for the caller to store. `available` is False
    when the previous-quarter comparison could not be produced (either the
    prior 13F-HR fetch/parse genuinely failed - see `unavailable_reason` - or
    this filer has no previous 13F-HR at all, e.g. its first-ever filing).
    Either way the frontend gets an explicit `{"available": false, "reason":
    "..."}` shape instead of a silent blank, per product requirement: a quiet
    empty field is worse than a labeled "no prior-quarter data" state. The
    current-quarter-only fields (`options_count`, `top10_pct`) are always
    computable and included regardless of availability.
    """
    total_value = sum(g["value"] for g in merged.values())
    ranked_values = sorted((g["value"] for g in merged.values()), reverse=True)
    top10_value = sum(ranked_values[:10])
    top10_pct = round(top10_value / total_value, 4) if total_value else 0.0
    options_count = sum(1 for g in merged.values() if g.get("put_call"))

    new_count = added_count = exited_count = reduced_count = None
    total_value_prev = None
    value_change_pct = None
    turnover_pct = None
    available = False
    reason = None
    if prev_merged is not None and unavailable_reason is None:
        total_value_prev = sum(g["value"] for g in prev_merged.values())
        if total_value_prev:
            value_change_pct = round((total_value - total_value_prev) / total_value_prev, 4)
        new_count = added_count = exited_count = reduced_count = 0
        for key, g in merged.items():
            prev = prev_merged.get(key)
            if prev is None:
                new_count += 1
            elif g["shares"] > prev["shares"]:
                added_count += 1
            elif g["shares"] < prev["shares"]:
                reduced_count += 1
        for key in prev_merged:
            if key not in merged:
                exited_count += 1
        # Turnover definition (explicit per product spec, do not redefine
        # without updating the frontend copy that explains this number):
        #   turnover_pct = (new_count + exited_count) / total distinct
        #   positions considered this quarter, where "total distinct
        #   positions" is the union of this quarter's and last quarter's
        #   position keys (a plain len(merged) would undercount the
        #   denominator, since exited positions by definition aren't in
        #   `merged` anymore).
        universe = len(set(merged) | set(prev_merged))
        turnover_pct = round((new_count + exited_count) / universe, 4) if universe else 0.0
        available = True
    else:
        reason = unavailable_reason or "no previous quarter 13F-HR filing available"

    return {
        "available": available,
        "reason": reason,
        "new_count": new_count,
        "added_count": added_count,
        "exited_count": exited_count,
        "reduced_count": reduced_count,
        "options_count": options_count,
        "top10_pct": top10_pct,
        "total_value_prev": total_value_prev,
        "value_change_pct": value_change_pct,
        "turnover_pct": turnover_pct,
    }


def compute_ticker_coverage(merged: dict):
    """Fraction of non-option portfolio value with a resolvable ticker.

    PUT/CALL rows are deliberately excluded: their 13F ``shares`` field is
    the contract's underlying share count, not a common-stock share count, so
    multiplying it by a stock close would create a fictional portfolio value.
    """
    eligible = [g for g in merged.values() if not g.get("put_call")]
    total_value = sum(g["value"] for g in eligible)
    if not total_value:
        return 0.0
    ticker_value = sum(g["value"] for g in eligible if g.get("ticker"))
    return round(ticker_value / total_value, 4)


def compute_sector_alloc(merged: dict, sector_map: dict):
    """Sector allocation across the *full* portfolio (not just top-N),
    with covered_pct telling the frontend what fraction of total value is
    even attributable to a known sector - cusip_map only maps a curated
    subset of names, so allocation is necessarily partial and must say so
    rather than imply completeness.
    """
    total_value = sum(g["value"] for g in merged.values())
    buckets = {}  # sector "en" label -> {"sector": dict, "value": int}
    covered_value = 0
    for g in merged.values():
        sector = sector_map.get(g.get("entity_key")) if g.get("entity_key") else None
        if not sector:
            continue
        covered_value += g["value"]
        key = sector.get("en") or json.dumps(sector, sort_keys=True)
        bucket = buckets.setdefault(key, {"sector": sector, "value": 0})
        bucket["value"] += g["value"]
    sectors = sorted(
        (
            {
                "sector": b["sector"],
                "value": b["value"],
                "weight": round(b["value"] / total_value, 4) if total_value else 0,
            }
            for b in buckets.values()
        ),
        key=lambda s: -s["value"],
    )
    covered_pct = round(covered_value / total_value, 4) if total_value else 0.0
    return {"covered_pct": covered_pct, "sectors": sectors}


def load_sector_map():
    """entity_key -> {en,ko,ja} sector label, sourced from items.json's
    `entities` (the same registry cusip_map's entity_key values point into).
    Only `kind: "company"` entities carry a real sector; other kinds (term,
    etc.) reuse the `sector` field as a display-category label ("Glossary")
    that isn't a stock sector and must not leak into holdings.
    """
    items = load_json(ITEMS_PATH, {"entities": {}})
    out = {}
    for key, val in items.get("entities", {}).items():
        if not isinstance(val, dict) or val.get("kind") != "company":
            continue
        sector = val.get("sector")
        if sector:
            out[key] = sector
    return out


def fetch_one(investor: dict, cusip_map: dict, sector_map: dict):
    slug = investor["slug"]
    cik = investor["cik"]
    cik_int = str(int(cik))
    filings = find_two_recent_13f_hr(cik)
    if not filings:
        raise ValueError("no 13F-HR filings found")
    latest = filings[0]
    prev_merged = None
    prev_unavailable_reason = None
    if len(filings) > 1:
        try:
            prev_accession_nodash = filings[1]["accessionNumber"].replace("-", "")
            prev_url = find_infotable_url(cik_int, prev_accession_nodash)
            prev_rows = fix_value_units(parse_infotable(http_get(prev_url)), filer_label=f"{slug} (prev quarter)")
            prev_groups = group_by_cusip(prev_rows)
            prev_merged = merge_share_classes(prev_groups, cusip_map)
        except Exception as e:  # noqa: BLE001 - the prior-quarter comparison is
            # best-effort; a fetch/parse failure there must not blank out this
            # quarter's own holdings, which are otherwise perfectly fine.
            prev_unavailable_reason = f"{type(e).__name__}: {e}"
            print(f"[warn] {slug}: previous-quarter fetch failed, activity comparison unavailable ({prev_unavailable_reason})")

    accession_nodash = latest["accessionNumber"].replace("-", "")
    infotable_url = find_infotable_url(cik_int, accession_nodash)
    rows = fix_value_units(parse_infotable(http_get(infotable_url)), filer_label=slug)
    groups = group_by_cusip(rows)
    merged = merge_share_classes(groups, cusip_map)
    holdings, all_holdings, total_value, holdings_count = compute_holdings(merged, prev_merged, sector_map)
    activity = compute_activity(merged, prev_merged, unavailable_reason=prev_unavailable_reason)
    sector_alloc = compute_sector_alloc(merged, sector_map)
    ticker_coverage_pct = compute_ticker_coverage(merged)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "slug": investor["slug"],
        "cik": cik,
        "filer": investor["filer"],
        "name": investor["name"],
        "manager": investor["manager"],
        "entity_key": investor["entity_key"],
        "period": latest["reportDate"],
        "filed": latest["filingDate"],
        "accession": latest["accessionNumber"],
        "source_url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/",
        "total_value": total_value,
        "holdings_count": holdings_count,
        "holdings": holdings,
        # Keep the visible top-25-plus-exits list above for a compact UI, but
        # retain every current position for the full portfolio value chart
        # and the next CUSIP-mapping pass. This is especially important for
        # ARK/Duquesne, where the stored top-N list was not the whole book.
        "all_holdings": all_holdings,
        "activity": activity,
        "sector_alloc": sector_alloc,
        "ticker_coverage_pct": ticker_coverage_pct,
        "desc": investor["desc"],
        "checked_at": now,
        "ok": True,
        "error": None,
    }


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    cusip_map_raw = load_json(CUSIP_MAP_PATH, {})
    cusip_map = {}
    for k, v in cusip_map_raw.items():
        if k.startswith("_"):
            continue
        v = dict(v)
        v["ticker"] = normalize_ticker(v.get("ticker"))  # defense in depth; see normalize_ticker()
        cusip_map[k] = v

    sector_map = load_sector_map()

    prev_file = load_json(PORTFOLIOS_PATH, {"investors": []})
    prev_by_slug = {inv["slug"]: inv for inv in prev_file.get("investors", [])}

    now = datetime.now(timezone.utc).isoformat()
    results = []
    any_ok = False
    for investor in INVESTORS:
        slug = investor["slug"]
        try:
            result = fetch_one(investor, cusip_map, sector_map)
            any_ok = True
            print(f"[ok] {slug}: {result['holdings_count']} holdings, "
                  f"total_value={result['total_value']:,} period={result['period']}")
            results.append(result)
        except Exception as e:  # noqa: BLE001 - one bad filer must not kill the run
            err = f"{type(e).__name__}: {e}"
            print(f"[fail] {slug}: {err}")
            prev = prev_by_slug.get(slug)
            if prev is not None:
                prev = dict(prev)
                prev["checked_at"] = now
                prev["ok"] = False
                prev["error"] = err
                results.append(prev)
            else:
                results.append({
                    "slug": slug,
                    "cik": investor["cik"],
                    "filer": investor["filer"],
                    "name": investor["name"],
                    "manager": investor["manager"],
                    "entity_key": investor["entity_key"],
                    "period": None,
                    "filed": None,
                    "accession": None,
                    "source_url": None,
                    "total_value": None,
                    "holdings_count": None,
                    "holdings": [],
                    "activity": {"available": False, "reason": err},
                    "sector_alloc": None,
                    "ticker_coverage_pct": None,
                    "desc": investor["desc"],
                    "checked_at": now,
                    "ok": False,
                    "error": err,
                })

    if not any_ok and prev_file.get("investors"):
        # Every single fetch failed: leave the existing file alone rather
        # than overwrite good data with an all-error snapshot.
        print("[attention] every investor failed to fetch; leaving portfolios.json untouched")
        return

    out = {"generated_at": now, "investors": results}
    with open(PORTFOLIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {PORTFOLIOS_PATH}")


if __name__ == "__main__":
    main()
