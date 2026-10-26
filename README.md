# Instagram_marketing

인스타그램 홍보 피드 자동화 프로그램 **InstaPromo**.
앱/웹페이지 설명(직접 입력, 웹사이트, GitHub 저장소)을 바탕으로 Claude가 게시물을 기획하고 캡션을 쓰고, Gemini가 배경 이미지를 만들고,
HTML 템플릿으로 한글 문구를 얹은 슬라이드를 만든 뒤, 승인한 게시물을 Instagram에 올립니다.

- 기획서: [docs/PLAN.md](docs/PLAN.md)
- 현재 단계: **1단계 프로토타입** (Windows 프로그램 + 명령줄 도구)

## Windows 프로그램 (InstaPromo.exe)

### 받기
- 저장소의 **Actions → Build Windows exe** 에서 최신 실행 결과를 열고 `InstaPromo-windows` 를 내려받습니다.
- `v` 로 시작하는 태그(예: `v0.1.0`)를 올리면 **Releases** 에도 exe가 첨부됩니다.
- 서명되지 않은 프로그램이라 처음 실행할 때 Windows SmartScreen 경고가 나올 수 있습니다 (추가 정보 → 실행).
- 슬라이드 렌더링에 PC에 설치된 **Microsoft Edge**(Windows 기본 포함) 또는 Chrome을 사용합니다.

### 화면 구성
| 탭 | 하는 일 |
|---|---|
| ① 설정 | Claude·Gemini API 키, Instagram 사용자 ID·토큰, 이미지 저장소(S3/R2), GitHub 토큰(선택), 저장 폴더 입력. 게시 한도 확인, 토큰 갱신 |
| ② 제품 정보 | 제품 이름·소개·기능·말투·금지 표현·브랜드 색·로고·스크린샷 입력. **GitHub에서 가져오기**로 저장소 README를 읽어 빈칸 자동 채우기 |
| ③ 게시물 생성 | 제품과 개수를 고르고 생성. 웹사이트·GitHub 내용도 참고 자료로 Claude에게 전달 |
| ④ 검토·게시 | 슬라이드 미리보기, 캡션 수정, 승인, Instagram 게시 |

설정은 `%APPDATA%\InstaPromo\settings.json`, 제품 정보는 `%APPDATA%\InstaPromo\products\` 에 저장됩니다.
키가 이 파일에 평문으로 저장되므로 PC를 다른 사람과 함께 쓴다면 주의하세요.
만든 게시물은 기본으로 `내 사용자 폴더\InstaPromo\` 에 저장됩니다.

### 직접 빌드하기 (Windows)
```powershell
pip install ".[build]"
pyinstaller --noconfirm --onefile --windowed --name InstaPromo --collect-data instapromo --collect-data playwright packaging/instapromo_gui.py
# 결과: dist\InstaPromo.exe
```

## 흐름

```
products/*.yaml ─► generate ─► output/<폴더>/ (slide_XX.jpg, caption.txt, post.json)
                                   │  검토·caption.txt 수정
                                   ▼
                               approve ─► publish (S3/R2 업로드 → Instagram Graph API)
```

## 명령줄 도구 (개발·자동화용)

### 설치

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[s3,dev]'
playwright install chromium      # 슬라이드 렌더링용 브라우저
cp .env.example .env             # 키 입력
```

명령줄 도구는 Windows 프로그램과 같은 `settings.json` 을 읽고, 같은 이름의 환경변수(`.env`)가 있으면 그 값을 우선합니다.

| 환경변수 | 용도 | 필요한 명령 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 게시물 기획·캡션 생성 | generate |
| `GEMINI_API_KEY` | 배경 이미지 생성 ([Google AI Studio](https://aistudio.google.com/)에서 발급) | generate (`--no-images` 면 불필요) |
| `GITHUB_TOKEN` | (선택) 비공개 저장소·API 요청 한도 | generate (`github` 지정 시) |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram 게시 | publish, quota, refresh-token |
| `S3_*` | 이미지를 공개 URL로 올리는 저장소 (Cloudflare R2 등) | publish |

Instagram 계정·토큰 준비 방법은 [기획서 5.1절](docs/PLAN.md#51-사전-준비-홍보-전용-본인-계정-기준)을 참고하세요.

### 사용법

```bash
# 1) 제품 정보 작성
cp products/sample_app.yaml products/my_app.yaml   # 내용 수정

# 2) 게시물 생성 (기본 1개)
instapromo generate --product products/my_app.yaml --count 3
instapromo generate --product products/my_app.yaml --no-images   # Gemini 없이 브랜드 그라데이션 배경
instapromo generate --product products/my_app.yaml --github https://github.com/owner/repo   # README도 참고

# 3) 검토: 이미지 확인, 필요하면 caption.txt 직접 수정
instapromo show output/<폴더>

# 4) 승인 후 게시
instapromo approve output/<폴더>
instapromo publish output/<폴더> --dry-run   # 업로드 없이 확인
instapromo publish output/<폴더>

# 기타
instapromo quota           # 24시간 게시 한도 확인
instapromo refresh-token   # 장기 토큰 갱신 후 settings.json에 저장 (약 60일 유효)
```

슬라이드 규격은 1080×1350(4:5) JPEG이며, 레이아웃은 `cover`(표지) · `feature`(기능) · `cta`(행동 유도) 세 가지입니다.
템플릿은 `src/instapromo/templates/slide.html` 에서 고칠 수 있습니다.
문구가 영역을 넘치거나 금지 표현·캡션 길이 제한에 걸리면 `post.json` 의 `warnings` 와 화면에 경고가 표시됩니다.

### 테스트

```bash
pytest
```

API 키 없이 실행됩니다. Claude·Gemini·Instagram 호출은 가짜 클라이언트로 대체합니다.
Chromium이 없으면 렌더링 테스트는 건너뜁니다.
