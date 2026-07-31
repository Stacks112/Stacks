# 플레이북 1 — 인프라 세팅 가이드 (Stacks에서 증류)

> Stacks(stacksdaily.com) 개발 9일+2주 운영에서 검증된 인프라 구성을,
> 새 서비스(예: 맛집 지도)를 제로에서 라이브까지 올리는 순서로 정리한 문서.
> 새 프로젝트 지식에 넣고, 새 세션이 인프라 작업을 시작할 때 이 문서부터 읽게 하면 된다.

## 0. 전체 아키텍처 한 장 요약

```
GitHub 레포 (public)
 ├─ index.html          ← 서비스 본체. 단일 파일 정적 앱 (GitHub Pages로 서빙)
 ├─ assets/             ← 파일이 커지면 분할 (Stacks는 666KB→505KB로 분할했음)
 ├─ data/items.json     ← 콘텐츠 데이터 (맛집 지도라면 places.json)
 ├─ worker/index.js     ← Cloudflare Worker (동적 기능: 댓글·조회수·구독 등)
 ├─ scripts/*.py        ← 빌드·자동화 스크립트
 └─ .github/workflows/  ← GitHub Actions (정적 페이지 생성, 배포, 정기 작업)

Cloudflare
 ├─ Registrar: 도메인 (연 ~$10)
 ├─ DNS (전부 "DNS only" 회색구름 — GitHub Pages가 서빙하므로 프록시 불필요)
 ├─ Worker: 동적 API (무료 티어로 충분)
 └─ D1: SQLite DB (댓글, 카운터, 구독자 등)

외부 서비스
 ├─ Resend: 이메일 발송 (뉴스레터·환영 메일)
 ├─ OneSignal: 웹 푸시
 ├─ GoatCounter: 애널리틱스 (무료, 프라이버시 우선)
 └─ Google AdSense: 수익화 (선택)
```

핵심 판단: **정적 호스팅(GitHub Pages) + 서버리스(Worker/D1)** 조합이면 서버 비용 0원으로
댓글·구독·푸시까지 되는 서비스를 운영할 수 있다. 맛집 지도도 같은 구조가 그대로 맞는다
(지도 타일만 Leaflet+OSM 또는 카카오/네이버 지도 SDK 추가).

## 1. 레포 + GitHub Pages

1. public 레포 생성 → `index.html` 단일 파일로 시작 (빠른 반복에 유리).
2. Settings → Pages → main 브랜치 루트 서빙.
3. **처음부터 `.gitignore`를 만들 것** — Stacks는 이게 없어서 보안 점검에서 지적받았다.
   최소: `.env*`, `.dev.vars*`, `*.pem`, `.netrc`, `__pycache__/`.
4. Secret/Push protection 활성화. Actions 기본 토큰은 읽기 전용으로.
5. 단일 파일이 500KB를 넘어가면 UI 블록을 `assets/`로 분할 (Stacks는 3단계로 분할했고 문제없었다).

## 2. 커스텀 도메인 (반나절 작업)

Stacks 실측 절차 (2026-07-17, 하루 안에 완료):

1. **Cloudflare Registrar**에서 도메인 구매 (연 $10.46 수준, auto-renew ON).
2. DNS 레코드 — 전부 **DNS only(회색구름)**:
   - A `@` → 185.199.108.153 / 109.153 / 110.153 / 111.153 (GitHub Pages 고정 IP 4개)
   - CNAME `www` → `<계정>.github.io`
3. 레포 루트에 `CNAME` 파일 (내용 = 도메인).
4. GitHub Pages 설정에서 Enforce HTTPS ON, DNS check 통과 확인.
5. 옛 `*.github.io` 주소는 GitHub이 자동 301 리다이렉트 — 지우지 말 것 (SEO 손실 방지).
6. `index.html`에 canonical/og:url 추가, 빌드 스크립트가 있으면 BASE 상수를 새 도메인으로.

## 3. 검색 등록 (도메인 이전과 같은 날 하는 게 좋다)

- **Google Search Console**: 도메인 속성(sc-domain:) + TXT 레코드 인증, sitemap.xml 제출.
- **네이버 서치어드바이저**: meta 태그 인증, sitemap + feed 제출. (한국 대상 서비스면 필수 — 맛집 지도는 특히.)
- **IndexNow**: 빌드 스크립트에서 갱신 URL을 api.indexnow.org로 핑 (구글은 안 쓰지만 빙/네이버 계열에 유효).
- SEO용 정적 페이지: JS 렌더 전 첫 크롤 패스에 잡히도록 정적 `<h1>`·앱 이름을 HTML에 직접 넣을 것.
  JSON-LD(Organization/WebSite + alternateName)는 브랜드 검색에 실제로 효과 있었다.
- 현실적 기대치: 새 도메인은 순위 자리잡기까지 몇 주~몇 달. 브랜드 단독 검색어보다
  "브랜드+주제어" 조합이 먼저 먹힌다.

## 4. Cloudflare Worker + D1 (동적 기능 백엔드)

Stacks의 워커 하나(`stacks-comments`)가 댓글, 조회수 카운터, 공유 리다이렉트(/s/:id → OG 태그 서빙),
구독자 관리, 급변동 감시 cron까지 전부 담당. 맛집 지도라면: 리뷰/평점 저장, 방문 기록, 제보 접수 등.

세팅 요점:
- `wrangler.toml`에 D1 바인딩 + cron 트리거 정의. 레포에 `deploy-worker.yml` Actions를 두면
  push → 자동 배포 (CLOUDFLARE_API_TOKEN은 GitHub Secrets에).
- 테이블은 워커 시작 시 `ensureTables()`로 idempotent하게 생성.
- **모든 D1 쿼리는 `?N` + `.bind()`** — Stacks 보안 점검에서 SQL 인젝션 0건이었던 이유.
- CORS는 `ALLOWED_ORIGINS` 화이트리스트 (와일드카드 금지).

보안 점검(2026-07-25)에서 배운 것 — 새 워커는 처음부터 반영할 것:
- POST/DELETE에서 `Origin` 헤더 검증 (Content-Type: text/plain 심플 리퀘스트는 프리플라이트를 건너뛴다).
- 자주 조회하는 컬럼(예: `ip_hash, created_at`)에 인덱스 — 없으면 쓰기마다 풀스캔.
- 스팸 방어: 레이트리밋 + 동일 내용 중복 차단 + (필요시) Turnstile.
- 응답 시간으로 가입 여부가 새는 타이밍 오라클 주의 → 메일 발송은 `ctx.waitUntil()`로.
- 수신거부 등 상태 변경 GET 라우트는 확인 페이지로 (메일 스캐너가 링크를 따라간다).
- 시크릿은 URL 쿼리가 아니라 POST 바디/헤더로.

## 5. 이메일 (Resend) — 뉴스레터·알림 메일

Stacks 검증 구조 (Stibee에서 갈아탄 뒤 안정):
- **구독자 명단은 D1에 직접 저장** (`subscribers(email, lang, unsubscribed, ...)`) —
  Resend는 발송 트랜스포트로만. (Resend Audiences는 deprecated라 의존하지 말 것.)
- 구독: 사이트 폼 → 워커 `POST /subscribe` → D1 upsert → 환영 메일 즉시 발송
  (재구독 시 중복 발송 가드 필요).
- 해지: HMAC 서명 링크 (`hmac24(UNSUB_SECRET, email)`) + RFC 8058 원클릭 헤더.
- **도메인 인증 필수** — 안 하면 sandbox 모드라 본인에게만 발송된다(Stacks는 이걸 몰라서
  실발송 직전에 발각됐다). Cloudflare DNS에 4개 레코드:
  DKIM TXT `resend._domainkey` / SPF TXT `send`="v=spf1 include:amazonses.com ~all" /
  MX `send`→feedback-smtp.<리전>.amazonses.com / DMARC TXT `_dmarc`="v=DMARC1; p=none;".
- 발송 스크립트가 워커 API를 호출할 때 **브라우저 User-Agent 헤더 필수** —
  python-urllib 기본 UA는 Cloudflare가 봇으로 차단한다 (Stacks에서 "푸시가 안 나가는" 오래된
  미스터리의 원인이 이거였다).

## 6. 푸시 (OneSignal) · 애널리틱스 (GoatCounter)

- OneSignal: Site URL을 도메인 루트로, 서비스워커 scope 분리(`/onesignal/`). 무료 티어로 충분.
- GoatCounter: 스크립트 한 줄. `goatcounter.count({path:"이벤트명", event:true})`로 커스텀
  이벤트(버튼 클릭, 기능 사용) 추적 가능 — 실제 URL이 아닌 행동 로그로 쓴다.
- **한계를 알고 시작할 것**: GoatCounter는 프라이버시 설계상 재방문율을 원리적으로 못 잰다.
  재방문 측정이 필요하면 처음부터 localStorage 방문일 키 기반 커스텀 이벤트
  (`visit/new`, `visit/return-1d/7d/30d` 버킷)를 심어라 — Stacks는 이걸 2주 뒤에야 붙여서
  초기 데이터가 없다. **게이트(성공 기준)를 세우면 계측기를 같은 날 달아라.**

## 7. 수익화 (AdSense, 선택)

- ads.txt 등록 → 심사 → 승인 후 광고 단위 생성 순서. 심사에 시간이 걸리니 일찍 신청.
- 인피드 광고는 `ADS_ON` 플래그로 감싸 승인 전 배포 가능 (승인 전 슬롯은 빈 칸만 그린다).
- `<ins>`를 DOM에 넣은 **뒤에** `adsbygoogle.push({})` — 순서 바뀌면 조용히 무시된다.
- 광고 컨테이너에 배경색·고정 높이 지정 금지 (다크모드 흰 블록 / 왜곡).
- 검색 결과·짧은 목록에는 광고를 안 붙이는 게 낫다 (가치 낮고 방해 큼).

## 8. 자동화 골격 (레포 밖까지)

Stacks의 2계층 구조가 안정적이었다:
- **GitHub Actions** = 헤드리스로 안정적으로 돌 수 있는 기계적 작업
  (데이터 수집, 정적 페이지/OG 이미지 빌드, sitemap, 정기 발송). 자동 커밋 포함.
- **Cowork 예약(스케줄 작업)** = 판단이 필요한 작업 (콘텐츠 생성·검수, 채점, 헬스체크).

원칙:
- **같은 파일에 쓰는 자동화는 하나만** ("발행자는 항상 하나"). 새 자동화를 만들기 전에
  기존 것 존재 여부부터 확인.
- 예약은 늘어나기 쉽다 — Stacks는 13개까지 갔다가 6개로 통합했다. 주기가 같은 것끼리 묶되,
  한 세션 안에서 파트는 독립 실행(하나 실패해도 나머지 진행).
- 자동 커밋 Actions가 여럿이면 push 레이스가 난다 → `concurrency:` 그룹은 대기 run을
  취소하므로 쓰지 말고, **push 거절 시 rebase 후 재시도 루프**를 넣어라 (검증된 해법).
- 예약 프롬프트는 **얇은 로더**로: 실행 규칙 본문은 프로젝트 문서(`claude/prompts/*.md`)에 두고
  프롬프트에는 신원·"문서 읽고 그대로 하라"·페일세이프·가드·시크릿만. 규칙 수정이
  project_write 한 번으로 끝난다. 단, 규칙 문서가 새 신뢰 경계가 되므로 문서에 지시형
  사람용 메모를 쓰지 말 것 (봇이 지시로 읽은 실사례 있음).

## 9. 시크릿 관리

- GitHub Actions 시크릿: Settings → Secrets. 워커 시크릿: wrangler 또는 대시보드.
- PAT는 **fine-grained, 해당 레포 단일, Contents Read/write만, 만료일 설정**.
- 로테이션 순서 (무중단): 새 토큰 생성 → 사용처 전부 교체 → 실제 push 성공 확인 → 옛 토큰 삭제.
  **"Regenerate" 버튼 금지** (옛 토큰 즉사 → 교체하는 사이 자동화 실패).
- GitHub 토큰 "Last used" 표시는 믿지 말 것 — 실제 커밋이 증거다.
- Cowork 예약에는 시크릿 저장소가 없다 → 프롬프트에 평문으로 들어가는 구조적 한계.
  가능하면 토큰이 필요한 작업은 Actions로 옮겨 GITHUB_TOKEN을 쓰는 게 낫다.
- 외부 서비스(발송·저장·광고·호스팅)를 바꾸면 **개인정보처리방침 수탁 업체 표 갱신까지가
  한 세트** — Stacks는 사흘 늦어서 법적 리스크를 안았다.

## 10. 맛집 지도에 적용할 때의 차이점 메모

- 콘텐츠 데이터 = `places.json` (좌표, 카테고리, 태그, 리뷰 요약). Stacks의 items.json처럼
  "단일 작성자(자동화 또는 세션 하나)" 규칙을 처음부터.
- 지도 UI: 카카오맵/네이버지도 SDK(국내 정확도)냐 Leaflet+OpenStreetMap(무료·무키)이냐를
  초기에 결정. API 키가 생기면 도메인 제한 걸 것.
- 정적 페이지 생성(`/p/<id>.html` 패턴)은 맛집 상세 페이지 SEO에 그대로 재사용 가능 —
  가게별 페이지 + sitemap + OG 이미지 자동 생성 구조가 특히 로컬 검색에 유리.
- 위치 기반이므로 네이버 SEO 비중이 Stacks보다 훨씬 크다. 서치어드바이저 등록을 1일차에.
