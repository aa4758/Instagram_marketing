# Instagram_marketing

인스타그램 홍보 피드 자동화 프로그램 **InstaPromo**.
앱/웹페이지 설명을 넣으면 Claude가 게시물을 기획하고 캡션을 쓰고, Gemini가 배경 이미지를 만들고,
HTML 템플릿으로 한글 문구를 얹은 슬라이드를 만든 뒤, 승인한 게시물을 Instagram에 올립니다.

- 기획서: [docs/PLAN.md](docs/PLAN.md)
- 현재 단계: **1단계 CLI 프로토타입**

## 흐름

```
products/*.yaml ─► generate ─► output/<폴더>/ (slide_XX.jpg, caption.txt, post.json)
                                   │  검토·caption.txt 수정
                                   ▼
                               approve ─► publish (S3/R2 업로드 → Instagram Graph API)
```

## 설치

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[s3,dev]'
playwright install chromium      # 슬라이드 렌더링용 브라우저
cp .env.example .env             # 키 입력
```

| 환경변수 | 용도 | 필요한 명령 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 게시물 기획·캡션 생성 | generate |
| `GEMINI_API_KEY` | 배경 이미지 생성 ([Google AI Studio](https://aistudio.google.com/)에서 발급) | generate (`--no-images` 면 불필요) |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram 게시 | publish, quota, refresh-token |
| `S3_*` | 이미지를 공개 URL로 올리는 저장소 (Cloudflare R2 등) | publish |

Instagram 계정·토큰 준비 방법은 [기획서 5.1절](docs/PLAN.md#51-사전-준비-홍보-전용-본인-계정-기준)을 참고하세요.

## 사용법

```bash
# 1) 제품 정보 작성
cp products/sample_app.yaml products/my_app.yaml   # 내용 수정

# 2) 게시물 생성 (기본 1개)
instapromo generate --product products/my_app.yaml --count 3
instapromo generate --product products/my_app.yaml --no-images   # Gemini 없이 브랜드 그라데이션 배경

# 3) 검토: 이미지 확인, 필요하면 caption.txt 직접 수정
instapromo show output/<폴더>

# 4) 승인 후 게시
instapromo approve output/<폴더>
instapromo publish output/<폴더> --dry-run   # 업로드 없이 확인
instapromo publish output/<폴더>

# 기타
instapromo quota           # 24시간 게시 한도 확인
instapromo refresh-token   # 장기 토큰 갱신 (약 60일 유효, 만료 전에 실행)
```

슬라이드 규격은 1080×1350(4:5) JPEG이며, 레이아웃은 `cover`(표지) · `feature`(기능) · `cta`(행동 유도) 세 가지입니다.
템플릿은 `src/instapromo/templates/slide.html` 에서 고칠 수 있습니다.
문구가 영역을 넘치거나 금지 표현·캡션 길이 제한에 걸리면 `post.json` 의 `warnings` 와 화면에 경고가 표시됩니다.

## 테스트

```bash
pytest
```

API 키 없이 실행됩니다. Claude·Gemini·Instagram 호출은 가짜 클라이언트로 대체합니다.
Chromium이 없으면 렌더링 테스트는 건너뜁니다.
