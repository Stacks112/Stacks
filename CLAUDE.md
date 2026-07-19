# Stacks — 아키텍처 매니페스트 / 단일 진실 출처

이 파일이 유일한 진실의 출처다. 코드와 함께 레포에 살아서 세션이 바뀌어도 낡지 않는다. Claude 세션은 Stacks 코드를 건드리기 전에 반드시 이 파일과 해당 라이브 파일(아래 경로)을 먼저 읽는다. 프로젝트(claude.ai) 안의 코드 미러는 낡았을 수 있으니 신뢰하지 말 것 — 라이브 레포가 정답이다.

세션 규칙:
1. 편집 전: 이 매니페스트 + 바꿀 라이브 파일을 raw로 읽어 현재 상태 확인.
2. 2. 편집 후: 아키텍처가 바뀌면 이 파일도 같은 커밋/PR에서 갱신.
   3. 3. 프로젝트 문서에 코드를 복제하지 말 것. 상태 메모만 두고 코드는 레포에.
     
      4. 마지막 확인: 2026-07-19 (Claude 세션, 브라우저로 라이브 인벤토리).
     
      5. ## 배포/도메인
      6. - 레포: Stacks112/Stacks · 도메인: stacksdaily.com
         - - 워커: stacks-comments.wnrakrhdn128.workers.dev (댓글·투표·푸시)
           - - 워커 소스 단일출처: worker/index.js → 커밋 시 deploy-worker.yml이 Cloudflare 자동배포
            
             - ## 워크플로 (.github/workflows/)
             - - feed-sync.yml — "Sync source feeds". scripts/fetch_feeds.py 실행 → feeds/*.json 커밋.
               - - apply-v50.yml — scripts/apply_v50.py (debate board 패처).
                 - - deploy-worker.yml — worker/** 변경 시 Cloudflare 배포.
                   - - og-assets.yml — scripts/fetch_og_assets.py + build_pages.py (OG 카드 이미지).
                     - - stacks-brief.yml — scripts/brief.py (데일리 브리핑 푸시).
                       - - stacks-weekly.yml — scripts/weekly.py (주간 다이제스트).
                        
                         - ## 스크립트 (scripts/)
                         - - fetch_feeds.py — RSS 피드 → feeds/<id>.json 스냅샷. FEEDS 리스트가 소스 목록.
                           - - build_pages.py — items.json → 정적 페이지/카드 생성.
                             - - fetch_og_assets.py — 위키 인물사진/로고 수집.
                               - - apply_v50.py · brief.py · weekly.py — 패처/푸시/다이제스트.
                                 - - 주의: scout.py 는 없음. (과거 프로젝트 미러의 pipeline-scout.yml이 scripts/scout.py를 가리켰지만 라이브엔 존재하지 않음 — 낡은 미러였음.)
                                  
                                   - ## 콘텐츠 데이터
                                   - - items.json (레포 루트) — 발행된 카드 전체. 필진 카드의 진짜 출처.
                                     - - feeds/*.json — 자동 수집된 원문 스냅샷(아직 카드화 전 재료).
                                       - - index.html (루트) — 프론트엔드 SPA.
                                        
                                         - ## 피드 파이프라인 실제 상태 (2026-07-19 실측)
                                         - fetch_feeds.py의 FEEDS = 7개. 실제 feeds/엔 emin/meru/trump 3개만 스냅샷 존재.
                                         - - meru (rss.blog.naver.com/ranto28.xml, KO) — OK
                                           - - emin (note.com/eminyurumazu/rss, JA) — OK
                                             - - trump (trumpstruth.org/feed, EN) — OK
                                               - - doomberg (newsletter.doomberg.com/feed, EN) — 스냅샷 없음(실패)
                                                 - - netinterest (netinterest.co/feed, EN) — 스냅샷 없음(실패)
                                                   - - serenity (rss.app/feeds/Pt8WBnMSdRiX2r4a.xml, X브리지) — 스냅샷 없음(실패)
                                                     - - serenity_substack (aleabitoreddit.substack.com/feed, EN) — 스냅샷 없음(실패)
                                                       - 추정 원인: Substack/rss.app가 봇 UA 차단 또는 rss.app 무료피드 만료 — 점검 필요.
                                                      
                                                       - ## 알려진 병목 / TODO
                                                       - 1. feeds/ → items.json 드래프팅 자동화 부재. feeds에 emin·trump 신선 원문이 쌓이는데 카드로 전환하는 단계가 없어 사실상 메르만 수동 발행됨 → 사이트가 메르 편중. 자동화 복원(scout 워크플로 신설) 필요.
                                                         2. 2. 피드 4개 fetch 실패(doomberg/netinterest/serenity/serenity_substack). UA 교체 또는 rss.app 재발급으로 복구 검토.
                                                            3. 3. 배포 제약: Claude 세션의 GitHub 토큰은 이 레포 API 접근 미개방(403). Claude 직접 push 불가 → GitHub 웹(브라우저) 편집 또는 사용자 커밋으로만 반영.
                                                               4. 
