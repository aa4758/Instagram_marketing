# Instagram 홍보 피드 자동화 프로그램 기획서

> 가칭: **InstaPromo** — 앱/웹페이지 설명을 입력하면 홍보 게시글(캡션·해시태그)과 이미지를 생성하고, 검토를 거쳐 Instagram 피드에 자동 업로드하는 프로그램

---

## 1. 목표와 범위

### 1.1 목표
- 홍보 대상(앱 또는 웹페이지)의 설명·URL만 주면 **기획 → 문구 작성 → 이미지 제작 → 업로드 → 성과 수집**까지 한 흐름으로 처리한다.
- 사람이 매번 디자인하고 글을 쓰는 시간을 줄이되, **브랜드 톤과 사실 정확성은 사람이 통제**할 수 있게 한다.

### 1.2 MVP 범위 (1차)
| 포함 | 제외 (2차 이후) |
|---|---|
| 단일 이미지 / 캐러셀 피드 게시 | 릴스(동영상), 스토리 |
| 제품 설명·URL 기반 콘텐츠 생성 | 댓글 자동 응답, DM |
| 템플릿 + AI 이미지 합성 | 여러 SNS 동시 게시 |
| 승인 후 예약 게시 | 광고(유료 프로모션) 집행 |
| 기본 성과 지표 수집 | A/B 테스트 자동 최적화 |

### 1.3 사용자
- 1인 개발자·소규모 팀이 자기 앱/웹 서비스를 꾸준히 홍보하는 상황을 1차 대상으로 한다.
- **확정: 홍보 전용 본인 계정 1개를 새로 만들어 사용한다.** 다른 사람 계정을 대신 관리하는 서비스가 아니므로 Meta 앱 검수, 다계정 로그인(OAuth) 화면, 계정별 권한 관리는 만들지 않는다.

---

## 2. 전체 흐름

```
[1. 제품 입력] ──► [2. 제품 분석] ──► [3. 콘텐츠 기획] ──► [4. 캡션 생성]
                                                         │
                                                         ▼
[8. 성과 수집] ◄── [7. 게시] ◄── [6. 검토/승인] ◄── [5. 이미지 생성]
      │
      └──► 다음 기획에 반영 (잘 된 주제·형식 우선)
```

1. **제품 입력**: 이름, 한 줄 소개, 상세 설명, URL, **GitHub 저장소(README를 읽어 자동 입력·참고 자료로 사용)**, 앱스토어 링크, 타깃 고객, 톤(친근/전문적 등), 금지 표현, 로고·브랜드 색상.
2. **제품 분석**: URL이 있으면 페이지를 크롤링하고 스크린샷을 찍어 핵심 기능·장점·타깃·차별점을 구조화된 "제품 프로필"로 정리.
3. **콘텐츠 기획**: 프로필을 바탕으로 N개(예: 2주치) 게시물 아이디어를 만든다. 주제 유형을 섞는다 — 기능 소개, 문제/해결, 사용 팁, 비포/애프터, 후기 스타일, 업데이트 소식, 이벤트.
4. **캡션 생성**: 훅(첫 줄) → 본문 → CTA("프로필 링크에서 다운로드") → 해시태그. 2,200자·해시태그 30개 제한 준수.
5. **이미지 생성**: 아래 3절 참고.
6. **검토/승인**: 웹 대시보드에서 미리보기, 수정, 재생성, 승인/반려.
7. **게시**: 승인된 게시물을 예약 시간에 Instagram Graph API로 업로드.
8. **성과 수집**: 도달·좋아요·저장·공유·댓글 수를 주기적으로 수집해 다음 기획 프롬프트에 반영.

---

## 3. 이미지 생성 전략

AI 이미지 모델은 **글자(특히 한글)를 정확히 그리지 못하는 경우가 많다.** 그래서 "배경/일러스트는 AI, 글자와 레이아웃은 템플릿"으로 역할을 나눈다.

| 방식 | 용도 | 구현 |
|---|---|---|
| **A. 템플릿 렌더링** (기본) | 제목·문구·로고가 들어간 카드뉴스, 캐러셀 | HTML/CSS 템플릿에 문구·색상·이미지를 채워 Playwright로 PNG 캡처 |
| **B. AI 생성 이미지** | 배경, 분위기 컷, 일러스트, 라이프스타일 사진 | **Gemini 이미지 모델** (기본, `gemini-2.5-flash-image`). `ImageProvider` 인터페이스로 OpenAI 등 교체 가능 |
| **C. 실제 화면 캡처** | 기능 시연, 앱 UI 강조 | 웹페이지 Playwright 스크린샷 / 사용자가 올린 앱 스크린샷을 폰 목업에 합성 |

- 최종 이미지는 **A 템플릿 위에 B·C를 배치**해 합성하는 것이 기본 파이프라인.
- 규격: 1080×1350(4:5, 피드 권장) 또는 1080×1080(1:1), **JPEG**, sRGB.
- 캐러셀: 1장 표지(훅) → 2~N장 내용 → 마지막 장 CTA.
- 템플릿은 브랜드별로 색상·폰트·로고 위치를 설정값으로 관리해 일관성을 유지.
- 생성 후 자동 점검: 해상도/비율, 글자 넘침(텍스트 박스 overflow 감지), 대비(가독성).

---

## 4. 시스템 구성

```
┌──────────────────────── Web 대시보드 (Next.js 또는 FastAPI + 템플릿) ───────────────────────┐
│  제품 등록 · 콘텐츠 캘린더 · 미리보기/수정 · 승인 · 성과 보기                                │
└──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                       │ REST
┌──────────────────────────────────────▼──────────────────────────────────────────────────────┐
│ API 서버 (Python / FastAPI)                                                                  │
│  ├ product_analyzer   : URL 크롤링, 스크린샷, 제품 프로필 생성 (LLM)                          │
│  ├ content_planner    : 게시물 아이디어·캘린더 생성 (LLM)                                     │
│  ├ copywriter         : 캡션·해시태그 생성, 길이/금지어 검사 (LLM)                            │
│  ├ image_generator    : AI 이미지 API 호출 (provider 교체 가능한 인터페이스)                  │
│  ├ renderer           : HTML 템플릿 → PNG/JPEG (Playwright)                                   │
│  ├ publisher          : Instagram Graph API 업로드                                            │
│  └ insights_collector : 성과 지표 수집                                                        │
└───────┬───────────────────────┬───────────────────────────┬─────────────────────────────────┘
        │                       │                           │
  ┌─────▼─────┐          ┌──────▼───────┐           ┌───────▼────────┐
  │ DB        │          │ 작업 큐/스케줄러│           │ 객체 스토리지     │
  │ SQLite →  │          │ APScheduler → │           │ S3 / R2 / GCS   │
  │ Postgres  │          │ Celery/RQ     │           │ (공개 URL 필요)  │
  └───────────┘          └──────────────┘           └────────────────┘
```

### 4.1 기술 스택 제안
| 영역 | 선택 | 이유 |
|---|---|---|
| 언어 | Python 3.12 | LLM·이미지·크롤링 라이브러리가 풍부 |
| 서버 | FastAPI | 가볍고 비동기 지원 |
| 텍스트 생성 | Claude API (`ANTHROPIC_MODEL` 로 모델 지정, 구조화 출력 사용) | 한국어 카피 품질, 구조화 출력(JSON) |
| 이미지 생성 | **Gemini 이미지 모델** (확정), 플러그인 구조 유지 | 저렴하고 참고 이미지(앱 스크린샷) 합성에 강함 |
| 렌더링 | Playwright + HTML/CSS 템플릿, Pillow | 한글 폰트·레이아웃 정확 |
| 크롤링 | Playwright, BeautifulSoup | SPA 페이지도 렌더링 후 분석 |
| 스토리지 | Cloudflare R2 또는 S3 | Instagram API가 **공개 이미지 URL**을 요구 |
| 스케줄 | APScheduler (MVP) → Celery + Redis | 예약 게시, 재시도 |
| DB | SQLite (MVP) → PostgreSQL | |
| 배포 | Docker, 소형 VM 또는 Cloud Run | |

### 4.2 LLM 사용 방식
- 모든 단계에서 **JSON 스키마로 구조화된 출력**을 받아 다음 단계로 넘긴다.
- 프롬프트에 항상 포함: 제품 프로필, 브랜드 톤, 금지 표현, 최근 게시물 요약(중복 방지), 성과 좋았던 게시물 예시.
- **사실 검증 가드**: 캡션에 제품 프로필에 없는 수치·기능·가격·수상 경력 등이 나오면 경고 표시.

---

## 5. Instagram 업로드 (핵심 제약)

공식 **Instagram Graph API (Content Publishing)** 만 사용한다. 비공식 로그인 자동화(아이디/비밀번호로 앱 흉내)는 **계정 정지 위험과 이용약관 위반** 소지가 있어 쓰지 않는다.

### 5.1 사전 준비 (홍보 전용 본인 계정 기준)
본인 계정 하나만 쓰므로 **Meta 앱 검수 없이 개발 모드로 운영**할 수 있다. Facebook 페이지 연결이 필요 없는 **Instagram 로그인 방식 API**를 사용한다.

1. **새 Instagram 계정 생성** (홍보 전용 이메일 사용 권장, 2단계 인증 설정)
2. 설정에서 **프로페셔널 계정(비즈니스 또는 크리에이터)으로 전환**, 카테고리는 "앱 페이지"·"웹사이트" 등 선택
3. **프로필 완성**: 프로필 사진(로고), 소개글, 웹사이트 링크(앱스토어·랜딩 페이지)
4. Meta for Developers에서 앱 생성 → **Instagram API(Instagram 로그인)** 제품 추가
5. 앱 역할에서 새 계정을 **Instagram 테스터로 추가**하고, Instagram 앱에서 초대 수락
6. 권한 `instagram_business_basic`, `instagram_business_content_publish`, (성과 수집용) `instagram_business_manage_insights` 로 토큰 발급
7. 단기 토큰 → **장기 토큰(약 60일)** 교환, 스케줄러가 만료 전에 자동 갱신
8. 토큰과 `ig_user_id`는 `.env` 또는 시크릿 매니저에 보관 (계정이 하나라 DB 계정 테이블 없이 설정값으로 충분)

### 5.1.1 새 계정 워밍업
새로 만든 계정이 처음부터 API로 매일 여러 개를 올리면 스팸으로 의심받거나 도달이 낮을 수 있다.
- 첫 1~2주: 주 2~3회, **검토 모드**로 게시
- 첫 게시물 3~6개는 계정 소개·대표 기능 위주로 프로필 그리드를 채운다
- 비슷한 분야 계정 팔로우, 댓글 응대 등 사람 활동을 병행한다
- 이후 반응을 보며 게시 빈도를 늘린다

### 5.2 게시 절차
```
단일 이미지:
  POST /{ig-user-id}/media  (image_url, caption)          → container_id
  GET  /{container_id}?fields=status_code  (FINISHED 대기)
  POST /{ig-user-id}/media_publish (creation_id)           → media_id

캐러셀:
  각 이미지마다 POST /media (is_carousel_item=true)        → child_id들
  POST /media (media_type=CAROUSEL, children=[...], caption) → container_id
  POST /media_publish
```

### 5.3 지켜야 할 제약
- 이미지는 **공개 접근 가능한 URL**이어야 함 → 업로드 직전에 스토리지에 올리고 URL 전달
- JPEG, 가로세로비 4:5 ~ 1.91:1
- **24시간당 API 게시 수 제한**이 있음 → `content_publishing_limit` 엔드포인트로 남은 횟수 확인 후 게시
- 캐러셀 장수 제한, 캡션 2,200자, 해시태그 30개, 멘션 20개
- 위 수치는 Meta 정책에 따라 바뀌므로 구현 시 최신 문서로 재확인

### 5.4 안정성
- 실패 시 지수 백오프 재시도, 토큰 만료·권한 오류는 즉시 알림
- 동일 게시물 중복 업로드 방지(게시 상태를 DB에서 잠금 후 처리)

---

## 6. 데이터 모델 (초안)

| 테이블 | 주요 필드 |
|---|---|
| `products` | id, name, tagline, description, url, store_links, target_audience, tone, banned_words, brand_colors, logo_path |
| `product_profiles` | product_id, features[], benefits[], pain_points[], usp, screenshots[], updated_at |
| `content_plans` | id, product_id, period_start, period_end |
| `posts` | id, plan_id, type(single/carousel), theme, caption, hashtags[], status(draft/approved/scheduled/published/failed), scheduled_at, ig_media_id, permalink |
| `post_assets` | post_id, order, prompt, source(ai/template/screenshot), file_path, public_url |
| `post_insights` | post_id, collected_at, reach, likes, comments, saves, shares |
| `templates` | id, name, html, slots(json), aspect_ratio |

게시물 상태 흐름: `draft → (수정) → approved → scheduled → published` / 실패 시 `failed → 재시도`

---

## 7. 운영 모드

| 모드 | 설명 | 권장 |
|---|---|---|
| **검토 모드** (기본) | 생성된 모든 게시물을 사람이 승인해야 게시 | 초기·신규 제품 |
| **반자동 모드** | 2주치 캘린더를 한 번에 승인, 이후 자동 게시 | 안정화 후 |
| **완전 자동 모드** | 생성 즉시 예약 게시, 사후 알림만 | 템플릿·톤이 충분히 검증된 경우에만 |

알림: 승인 대기, 게시 성공/실패, 토큰 만료 임박 → 이메일 또는 Slack/Telegram 웹훅.

---

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| AI가 없는 기능·과장된 효과를 씀 | 제품 프로필 기반 사실 검증, 금지어 필터, 기본 검토 모드 |
| 이미지 속 글자 깨짐 | 글자는 템플릿 렌더링으로만 처리 |
| 게시물이 비슷비슷해짐 | 주제 유형 로테이션, 최근 게시물 요약을 프롬프트에 넣어 중복 회피 |
| 스팸으로 인식/도달 저하 | 하루 게시 수 상한(예: 1~2개), 해시태그 과다 사용 금지 |
| 저작권·초상권 | 실존 인물·타 브랜드 로고·유명 캐릭터 생성 금지 프롬프트, AI 생성 콘텐츠 표기 정책 확인 |
| 토큰 유출 | 토큰 암호화 저장, 환경변수/시크릿 매니저 사용 |
| API 정책 변경 | Publisher를 인터페이스로 분리, 정기적으로 Meta 변경 로그 확인 |
| 비용 증가 | 이미지 생성 횟수 제한, 생성 결과 캐싱, 월 예산 상한 설정 |

---

## 9. 개발 로드맵

| 단계 | 기간(예상) | 결과물 |
|---|---|---|
| **0. 준비** | 2~3일 | 홍보 전용 계정 생성·프로페셔널 전환, Meta 앱(개발 모드)·테스터 등록, 토큰 발급, 테스트 게시 1건 성공 |
| **1. 프로토타입** ✅ 진행 중 | 1주 | Windows 프로그램(InstaPromo.exe: 설정·제품 정보·생성·검토/게시 화면) + 명령줄 도구 `instapromo` |
| **2. 이미지 파이프라인** | 1주 | 템플릿 3~5종, AI 배경 합성, 스크린샷 목업, 캐러셀 |
| **3. 스케줄러·DB** | 1주 | 콘텐츠 캘린더, 예약 게시, 재시도, 게시 한도 확인 |
| **4. 웹 대시보드** | 1~2주 | 제품 등록, 미리보기, 수정, 승인, 상태 확인 |
| **5. 성과 분석** | 1주 | 인사이트 수집, 성과 기반 기획 반영 |
| **6. 확장** | — | 릴스(슬라이드 영상 자동 생성), 스토리, 다계정, 다른 SNS |

### 9.1 1단계 디렉터리 구조 예시
```
instapromo/
├── pyproject.toml
├── .env.example            # ANTHROPIC_API_KEY, IMAGE_API_KEY, IG_USER_ID, IG_ACCESS_TOKEN, S3_*
├── products/
│   └── sample_app.yaml     # 제품 입력 예시
├── templates/
│   ├── cover.html
│   ├── feature.html
│   └── cta.html
├── src/instapromo/
│   ├── cli.py
│   ├── config.py
│   ├── analyzer.py
│   ├── planner.py
│   ├── copywriter.py
│   ├── images/
│   │   ├── base.py         # ImageProvider 인터페이스
│   │   ├── openai_provider.py
│   │   └── renderer.py     # HTML → JPEG
│   ├── storage.py
│   ├── publisher.py        # Instagram Graph API
│   └── models.py
└── tests/
```

### 9.2 제품 입력 파일 예시 (`products/sample_app.yaml`)
```yaml
name: "루틴메이트"
tagline: "작심삼일을 끝내는 습관 트래커"
url: "https://example.com"
app_store: "https://apps.apple.com/..."
target: "자기계발에 관심 있는 20~30대 직장인"
tone: "친근하고 응원하는 말투, 이모지 적당히"
features:
  - "하루 3분 체크인"
  - "친구와 함께하는 챌린지"
  - "주간 리포트"
banned_words: ["최고", "1위", "무조건"]
brand:
  primary_color: "#4F7CFF"
  secondary_color: "#FFD84F"
  font: "Pretendard"
  logo: "assets/logo.png"
posting:
  per_week: 3
  preferred_times: ["12:30", "20:00"]
  mode: review
```

---

## 10. 성공 지표
- 게시물 1건 제작 시간: 수작업 대비 80% 이상 단축
- 승인율(수정 없이 승인된 비율) 60% 이상
- 게시 성공률 99% 이상
- 4주 운영 후 게시물당 평균 도달·저장 수 상승 추세

---

## 11. 결정이 필요한 사항
1. ~~**사용 형태**~~ → **확정: 홍보 전용 본인 계정 1개** (앱 검수·다계정 설계 불필요)
2. ~~**이미지 생성 API**~~ → **확정: Gemini 이미지 모델** (월 30~50장 기준 수 달러 수준 예상, 가격은 공식 페이지에서 확인)
3. **검토 모드 기본 유지 여부** (완전 자동 허용 범위)
4. ~~**인터페이스**~~ → **확정: Windows 데스크톱 프로그램(exe)**. API 키·Instagram 정보는 사용자가 프로그램 설정 화면에서 직접 입력
5. **호스팅**: 로컬 PC 실행 vs 클라우드 상시 실행 (예약 게시에는 상시 실행 필요)
