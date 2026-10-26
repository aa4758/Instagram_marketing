"""InstaPromo 데스크톱 화면 (Tkinter). exe로 배포되는 진입점."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from dataclasses import fields
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from . import service
from .config import Settings, app_dir, settings_path
from .models import Brand, PostDraft, Product, full_caption

PAD = {"padx": 6, "pady": 3}

# (필드, 라벨, 비밀값 여부) — 설정 화면 구성
SETTING_GROUPS: list[tuple[str, list[tuple[str, str, bool]]]] = [
    ("Claude (게시물 기획·캡션)", [
        ("anthropic_api_key", "API 키", True),
        ("anthropic_model", "모델", False),
    ]),
    ("Gemini (배경 이미지)", [
        ("gemini_api_key", "API 키", True),
        ("gemini_image_model", "모델", False),
    ]),
    ("GitHub (선택: 비공개 저장소·요청 한도)", [
        ("github_token", "토큰", True),
    ]),
    ("Instagram", [
        ("ig_user_id", "사용자 ID", False),
        ("ig_access_token", "액세스 토큰", True),
        ("ig_api_version", "API 버전", False),
    ]),
    ("이미지 저장소 (S3 / Cloudflare R2)", [
        ("s3_bucket", "버킷", False),
        ("s3_endpoint_url", "엔드포인트 URL", False),
        ("s3_access_key_id", "Access Key ID", True),
        ("s3_secret_access_key", "Secret Access Key", True),
        ("s3_public_base_url", "공개 URL", False),
    ]),
    ("기타", [
        ("output_dir", "게시물 저장 폴더", False),
        ("chromium_executable", "브라우저 경로 (비우면 자동)", False),
    ]),
]


def products_dir() -> Path:
    return app_dir() / "products"


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("InstaPromo - Instagram 홍보 자동화")
        self.geometry("1040x780")
        self.minsize(900, 680)
        self.settings = Settings.load(use_env=False)
        self._busy = False
        self._log_queue: queue.Queue = queue.Queue()
        self._buttons: list[ttk.Button] = []

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_settings = ttk.Frame(notebook)
        self.tab_product = ttk.Frame(notebook)
        self.tab_generate = ttk.Frame(notebook)
        self.tab_review = ttk.Frame(notebook)
        notebook.add(self.tab_settings, text="① 설정")
        notebook.add(self.tab_product, text="② 제품 정보")
        notebook.add(self.tab_generate, text="③ 게시물 생성")
        notebook.add(self.tab_review, text="④ 검토·게시")
        notebook.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed(notebook))

        self._build_settings_tab()
        self._build_product_tab()
        self._build_generate_tab()
        self._build_review_tab()
        self.after(100, self._drain_log)

        if not self.settings.anthropic_api_key:
            notebook.select(self.tab_settings)
        else:
            notebook.select(self.tab_product)

    # ---------- 공통 ----------

    def button(self, parent, text, command, **kw) -> ttk.Button:
        b = ttk.Button(parent, text=text, command=command, **kw)
        self._buttons.append(b)
        return b

    def run_task(self, work, on_done=None) -> None:
        """시간이 걸리는 작업을 백그라운드에서 실행하고 끝나면 on_done(result)을 화면 스레드에서 호출한다."""
        if self._busy:
            messagebox.showinfo("진행 중", "다른 작업이 진행 중입니다. 끝난 뒤 다시 시도하세요.")
            return
        self._busy = True
        for b in self._buttons:
            b.state(["disabled"])

        def target():
            try:
                result = work()
                self.after(0, lambda: self._finish(on_done, result, None))
            except Exception as e:
                traceback.print_exc()
                self.after(0, lambda: self._finish(None, None, e))

        threading.Thread(target=target, daemon=True).start()

    def _finish(self, on_done, result, error) -> None:
        self._busy = False
        for b in self._buttons:
            b.state(["!disabled"])
        if error:
            self.log(f"❌ 오류: {error}")
            messagebox.showerror("오류", str(error))
        elif on_done:
            on_done(result)

    def log(self, message: str) -> None:
        self._log_queue.put(message)

    def _drain_log(self) -> None:
        while not self._log_queue.empty():
            msg = self._log_queue.get()
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(100, self._drain_log)

    def _on_tab_changed(self, notebook: ttk.Notebook) -> None:
        current = notebook.nametowidget(notebook.select())
        if current is self.tab_generate:
            self._refresh_product_choices()
        elif current is self.tab_review:
            self.refresh_posts()

    # ---------- ① 설정 ----------

    def _build_settings_tab(self) -> None:
        frame = self.tab_settings
        self.setting_vars: dict[str, tk.StringVar] = {}
        secret_entries: list[ttk.Entry] = []
        row = 0
        for title, items in SETTING_GROUPS:
            ttk.Label(frame, text=title, font=("", 10, "bold")).grid(row=row, column=0, columnspan=3,
                                                                    sticky="w", padx=6, pady=(10, 2))
            row += 1
            for name, label, secret in items:
                var = tk.StringVar(value=getattr(self.settings, name))
                self.setting_vars[name] = var
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky="e", **PAD)
                entry = ttk.Entry(frame, textvariable=var, width=70, show="•" if secret else "")
                entry.grid(row=row, column=1, sticky="we", **PAD)
                if secret:
                    secret_entries.append(entry)
                if name == "output_dir":
                    ttk.Button(frame, text="찾아보기",
                               command=lambda v=var: self._pick_dir(v)).grid(row=row, column=2, **PAD)
                row += 1

        show = tk.BooleanVar(value=False)

        def toggle():
            for e in secret_entries:
                e.configure(show="" if show.get() else "•")

        ttk.Checkbutton(frame, text="키·토큰 보기", variable=show, command=toggle).grid(
            row=row, column=1, sticky="w", **PAD)
        row += 1

        bar = ttk.Frame(frame)
        bar.grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=10)
        self.button(bar, "저장", self.save_settings).pack(side="left", padx=4)
        self.button(bar, "게시 한도 확인", self.check_quota).pack(side="left", padx=4)
        self.button(bar, "Instagram 토큰 갱신", self.refresh_token).pack(side="left", padx=4)
        row += 1
        ttk.Label(frame, foreground="gray",
                  text=f"설정 파일: {settings_path()}\n키는 이 PC의 사용자 폴더에만 저장됩니다. "
                       "PC를 다른 사람과 함께 쓴다면 주의하세요.").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=6)
        frame.columnconfigure(1, weight=1)

    def _pick_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if path:
            var.set(path)

    def _settings_from_form(self) -> Settings:
        values = {f.name: self.setting_vars[f.name].get().strip()
                  for f in fields(Settings) if f.name in self.setting_vars}
        return Settings(**values)

    def save_settings(self) -> None:
        self.settings = self._settings_from_form()
        path = self.settings.save()
        messagebox.showinfo("저장됨", f"설정을 저장했습니다.\n{path}")

    def check_quota(self) -> None:
        self.settings = self._settings_from_form()
        self.run_task(lambda: service.quota(self.settings),
                      lambda r: messagebox.showinfo("게시 한도", f"최근 24시간 게시 수: {r[0]} / {r[1]}"))

    def refresh_token(self) -> None:
        self.settings = self._settings_from_form()

        def done(days):
            self.setting_vars["ig_access_token"].set(self.settings.ig_access_token)
            messagebox.showinfo("토큰 갱신", f"새 토큰을 저장했습니다. 약 {days}일 동안 유효합니다.")

        self.run_task(lambda: service.refresh_token(self.settings), done)

    # ---------- ② 제품 정보 ----------

    def _build_product_tab(self) -> None:
        frame = self.tab_product
        top = ttk.Frame(frame)
        top.grid(row=0, column=0, columnspan=3, sticky="we", padx=6, pady=6)
        ttk.Label(top, text="저장된 제품").pack(side="left")
        self.product_choice = ttk.Combobox(top, state="readonly", width=40)
        self.product_choice.pack(side="left", padx=6)
        self.product_choice.bind("<<ComboboxSelected>>", lambda e: self.load_product_file(
            products_dir() / f"{self.product_choice.get()}.yaml"))
        ttk.Button(top, text="새 제품", command=self.new_product).pack(side="left", padx=2)
        ttk.Button(top, text="YAML 불러오기", command=self.import_product_yaml).pack(side="left", padx=2)

        self.pvars: dict[str, tk.StringVar] = {}
        self.ptexts: dict[str, tk.Text] = {}
        row = 1

        def entry(name, label, hint=""):
            nonlocal row
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="e", **PAD)
            var = tk.StringVar()
            ttk.Entry(frame, textvariable=var, width=70).grid(row=row, column=1, sticky="we", **PAD)
            if hint:
                ttk.Label(frame, text=hint, foreground="gray").grid(row=row, column=2, sticky="w", **PAD)
            self.pvars[name] = var
            row += 1
            return var

        def text(name, label, height, hint=""):
            nonlocal row
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="ne", **PAD)
            t = tk.Text(frame, height=height, width=70, wrap="word")
            t.grid(row=row, column=1, sticky="we", **PAD)
            if hint:
                ttk.Label(frame, text=hint, foreground="gray").grid(row=row, column=2, sticky="nw", **PAD)
            self.ptexts[name] = t
            row += 1

        # GitHub 가져오기 줄
        ttk.Label(frame, text="GitHub 저장소").grid(row=row, column=0, sticky="e", **PAD)
        gh = ttk.Frame(frame)
        gh.grid(row=row, column=1, columnspan=2, sticky="we", **PAD)
        self.pvars["github"] = tk.StringVar()
        ttk.Entry(gh, textvariable=self.pvars["github"], width=50).pack(side="left", fill="x", expand=True)
        self.button(gh, "GitHub에서 가져오기", self.import_github).pack(side="left", padx=4)
        row += 1
        ttk.Label(frame, foreground="gray",
                  text="예: https://github.com/owner/repo — README로 아래 빈칸을 채우고, 게시물 생성 때도 참고합니다.").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=6)
        row += 1

        entry("name", "제품 이름 *")
        entry("tagline", "한 줄 소개 *")
        text("description", "상세 설명", 4)
        entry("url", "웹사이트 URL", "내용을 읽어 참고")
        text("store_links", "스토어 링크", 2, "한 줄에 하나")
        entry("target", "타깃 고객")
        entry("tone", "말투")
        text("features", "핵심 기능", 3, "한 줄에 하나")
        entry("banned_words", "금지 표현", "쉼표로 구분")

        ttk.Label(frame, text="스크린샷").grid(row=row, column=0, sticky="e", **PAD)
        self.pvars["screenshots"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self.pvars["screenshots"], width=70).grid(row=row, column=1, sticky="we", **PAD)
        ttk.Button(frame, text="파일 선택", command=self._pick_screenshots).grid(row=row, column=2, sticky="w", **PAD)
        row += 1

        ttk.Label(frame, text="브랜드").grid(row=row, column=0, sticky="e", **PAD)
        brand = ttk.Frame(frame)
        brand.grid(row=row, column=1, columnspan=2, sticky="w", **PAD)
        for name, label in [("primary_color", "주 색상"), ("secondary_color", "보조 색상"), ("text_color", "글자 색")]:
            var = tk.StringVar()
            self.pvars[name] = var
            ttk.Label(brand, text=label).pack(side="left")
            ttk.Entry(brand, textvariable=var, width=9).pack(side="left", padx=(2, 0))
            ttk.Button(brand, text="🎨", width=3, command=lambda v=var: self._pick_color(v)).pack(side="left", padx=(0, 10))
        row += 1

        ttk.Label(frame, text="로고").grid(row=row, column=0, sticky="e", **PAD)
        self.pvars["logo"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self.pvars["logo"], width=70).grid(row=row, column=1, sticky="we", **PAD)
        ttk.Button(frame, text="파일 선택", command=self._pick_logo).grid(row=row, column=2, sticky="w", **PAD)
        row += 1

        bar = ttk.Frame(frame)
        bar.grid(row=row, column=1, sticky="w", padx=6, pady=8)
        ttk.Button(bar, text="제품 저장", command=self.save_product).pack(side="left")
        frame.columnconfigure(1, weight=1)

        self._refresh_product_list()
        self.new_product()
        names = self.product_choice["values"]
        if names:
            self.product_choice.set(names[0])
            self.load_product_file(products_dir() / f"{names[0]}.yaml")

    def _refresh_product_list(self) -> None:
        names = sorted(p.stem for p in products_dir().glob("*.yaml")) if products_dir().exists() else []
        self.product_choice["values"] = names

    def _pick_color(self, var: tk.StringVar) -> None:
        _, hex_ = colorchooser.askcolor(color=var.get() or None)
        if hex_:
            var.set(hex_.upper())

    def _pick_screenshots(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp")])
        if paths:
            self.pvars["screenshots"].set("; ".join(paths))

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("이미지", "*.png *.jpg *.jpeg *.svg")])
        if path:
            self.pvars["logo"].set(path)

    def _set_text(self, name: str, value: str) -> None:
        self.ptexts[name].delete("1.0", "end")
        self.ptexts[name].insert("1.0", value)

    def _get_text(self, name: str) -> str:
        return self.ptexts[name].get("1.0", "end").strip()

    def fill_product_form(self, p: Product) -> None:
        for name in ("name", "tagline", "url", "github", "target", "tone"):
            self.pvars[name].set(getattr(p, name) or "")
        self._set_text("description", p.description)
        self._set_text("store_links", "\n".join(p.store_links))
        self._set_text("features", "\n".join(p.features))
        self.pvars["banned_words"].set(", ".join(p.banned_words))
        self.pvars["screenshots"].set("; ".join(p.screenshots))
        for name in ("primary_color", "secondary_color", "text_color"):
            self.pvars[name].set(getattr(p.brand, name))
        self.pvars["logo"].set(p.brand.logo or "")

    def product_from_form(self) -> Product:
        name = self.pvars["name"].get().strip()
        tagline = self.pvars["tagline"].get().strip()
        if not name or not tagline:
            raise ValueError("제품 이름과 한 줄 소개는 꼭 입력해야 합니다.")
        defaults = Brand()
        return Product(
            name=name,
            tagline=tagline,
            description=self._get_text("description"),
            url=self.pvars["url"].get().strip() or None,
            github=self.pvars["github"].get().strip() or None,
            store_links=_lines(self._get_text("store_links")),
            target=self.pvars["target"].get().strip(),
            tone=self.pvars["tone"].get().strip() or Product.model_fields["tone"].default,
            features=_lines(self._get_text("features")),
            banned_words=[w.strip() for w in self.pvars["banned_words"].get().split(",") if w.strip()],
            screenshots=[s.strip() for s in self.pvars["screenshots"].get().split(";") if s.strip()],
            brand=Brand(
                primary_color=self.pvars["primary_color"].get().strip() or defaults.primary_color,
                secondary_color=self.pvars["secondary_color"].get().strip() or defaults.secondary_color,
                text_color=self.pvars["text_color"].get().strip() or defaults.text_color,
                logo=self.pvars["logo"].get().strip() or None,
            ),
        )

    def new_product(self) -> None:
        self.product_choice.set("")
        self.fill_product_form(Product(name="", tagline=""))

    def load_product_file(self, path: Path) -> None:
        from .product import load_product

        try:
            self.fill_product_form(load_product(path))
        except Exception as e:
            messagebox.showerror("불러오기 실패", str(e))

    def import_product_yaml(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml")])
        if path:
            self.load_product_file(Path(path))

    def save_product(self) -> Product | None:
        from .product import save_product

        try:
            product = self.product_from_form()
        except Exception as e:
            messagebox.showerror("입력 확인", str(e))
            return None
        slug = re.sub(r'[\\/:*?"<>|]+', "_", product.name).strip() or "product"
        save_product(product, products_dir() / f"{slug}.yaml")
        self._refresh_product_list()
        self.product_choice.set(slug)
        self.log(f"제품 정보 저장: {slug}")
        return product

    def import_github(self) -> None:
        from .copywriter import draft_product
        from .github import fetch_repo, readme_summary

        ref = self.pvars["github"].get().strip()
        if not ref:
            messagebox.showinfo("GitHub", "GitHub 저장소 주소를 입력하세요. 예: https://github.com/owner/repo")
            return
        settings = self._settings_from_form()

        def work():
            info = fetch_repo(ref, token=settings.github_token or None)
            draft = None
            if settings.anthropic_api_key:
                draft = draft_product(info.as_source_text()[:20_000], model=settings.anthropic_model,
                                      api_key=settings.anthropic_api_key)
            return info, draft

        def done(result):
            info, draft = result
            filled = []

            def fill(name, value):
                if value and not self.pvars[name].get().strip():
                    self.pvars[name].set(value)
                    filled.append(name)

            def fill_text(name, value):
                if value and not self._get_text(name):
                    self._set_text(name, value)
                    filled.append(name)

            if draft:
                fill("name", draft.name)
                fill("tagline", draft.tagline)
                fill_text("description", draft.description)
                fill("target", draft.target)
                fill_text("features", "\n".join(draft.features))
            fill("name", info.name)
            fill("tagline", info.description)
            fill_text("description", readme_summary(info.readme) or info.description)
            fill("url", info.homepage)
            note = "" if draft else "\n(Claude API 키를 설정하면 README를 요약해 기능·타깃까지 채웁니다.)"
            messagebox.showinfo("GitHub", f"{info.owner}/{info.name} 정보를 가져왔습니다.\n"
                                          f"빈칸 {len(filled)}개를 채웠습니다. 확인 후 '제품 저장'을 누르세요.{note}")

        self.run_task(work, done)

    # ---------- ③ 게시물 생성 ----------

    def _build_generate_tab(self) -> None:
        frame = self.tab_generate
        form = ttk.Frame(frame)
        form.pack(fill="x", padx=6, pady=6)
        ttk.Label(form, text="제품").grid(row=0, column=0, sticky="e", **PAD)
        self.gen_product = ttk.Combobox(form, state="readonly", width=40)
        self.gen_product.grid(row=0, column=1, sticky="w", **PAD)
        ttk.Label(form, text="게시물 수").grid(row=1, column=0, sticky="e", **PAD)
        self.gen_count = tk.IntVar(value=1)
        ttk.Spinbox(form, from_=1, to=10, textvariable=self.gen_count, width=5).grid(row=1, column=1, sticky="w", **PAD)
        self.gen_images = tk.BooleanVar(value=True)
        self.gen_fetch = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Gemini로 배경 이미지 만들기 (끄면 브랜드 색 배경)",
                        variable=self.gen_images).grid(row=2, column=1, sticky="w", **PAD)
        ttk.Checkbutton(form, text="웹사이트·GitHub 내용 읽어서 참고하기",
                        variable=self.gen_fetch).grid(row=3, column=1, sticky="w", **PAD)
        self.button(form, "게시물 생성 시작", self.start_generate).grid(row=4, column=1, sticky="w", padx=6, pady=8)

        ttk.Label(frame, text="진행 기록").pack(anchor="w", padx=12)
        self.log_text = tk.Text(frame, height=20, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _refresh_product_choices(self) -> None:
        self._refresh_product_list()
        names = list(self.product_choice["values"])
        self.gen_product["values"] = names
        current = self.product_choice.get()
        if current in names:
            self.gen_product.set(current)
        elif names and not self.gen_product.get():
            self.gen_product.set(names[0])

    def start_generate(self) -> None:
        from .product import load_product

        name = self.gen_product.get()
        if not name:
            messagebox.showinfo("제품 선택", "② 제품 정보 탭에서 제품을 저장한 뒤 선택하세요.")
            return
        product = load_product(products_dir() / f"{name}.yaml")
        settings = self.settings
        count, images, fetch = self.gen_count.get(), self.gen_images.get(), self.gen_fetch.get()

        def done(dirs):
            self.log(f"✅ 게시물 {len(dirs)}개 생성 완료. ④ 검토·게시 탭에서 확인하세요.")
            messagebox.showinfo("완료", f"게시물 {len(dirs)}개를 만들었습니다.\n④ 검토·게시 탭에서 확인하세요.")

        self.log(f"--- {name}: 게시물 {count}개 생성 시작 ---")
        self.run_task(lambda: service.generate(product, settings, count=count, use_images=images,
                                               fetch_sources=fetch, log=self.log), done)

    # ---------- ④ 검토·게시 ----------

    def _build_review_tab(self) -> None:
        frame = self.tab_review
        left = ttk.Frame(frame)
        left.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Label(left, text="게시물 목록").pack(anchor="w")
        self.post_list = tk.Listbox(left, width=30, height=30, exportselection=False)
        self.post_list.pack(fill="y", expand=True)
        self.post_list.bind("<<ListboxSelect>>", lambda e: self.show_selected_post())
        ttk.Button(left, text="새로고침", command=self.refresh_posts).pack(fill="x", pady=4)

        right = ttk.Frame(frame)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.post_title = ttk.Label(right, text="게시물을 선택하세요.", font=("", 11, "bold"))
        self.post_title.pack(anchor="w")

        body = ttk.Frame(right)
        body.pack(fill="both", expand=True)
        preview = ttk.Frame(body)
        preview.pack(side="left", padx=(0, 10))
        self.preview_label = ttk.Label(preview)
        self.preview_label.pack()
        nav = ttk.Frame(preview)
        nav.pack(pady=4)
        ttk.Button(nav, text="◀", width=3, command=lambda: self._step_slide(-1)).pack(side="left")
        self.slide_pos = ttk.Label(nav, text="")
        self.slide_pos.pack(side="left", padx=8)
        ttk.Button(nav, text="▶", width=3, command=lambda: self._step_slide(1)).pack(side="left")

        side = ttk.Frame(body)
        side.pack(side="left", fill="both", expand=True)
        ttk.Label(side, text="캡션 (수정 가능)").pack(anchor="w")
        self.caption_text = tk.Text(side, height=16, wrap="word")
        self.caption_text.pack(fill="both", expand=True)
        self.warn_label = ttk.Label(side, text="", foreground="#C0392B", wraplength=320, justify="left")
        self.warn_label.pack(anchor="w", pady=4)
        bar = ttk.Frame(side)
        bar.pack(anchor="w", pady=4)
        self.button(bar, "승인", self.approve_post).pack(side="left", padx=2)
        self.button(bar, "Instagram에 게시", self.publish_post).pack(side="left", padx=2)
        ttk.Button(bar, text="폴더 열기", command=self.open_post_dir).pack(side="left", padx=2)

        self._posts: list[tuple[Path, dict]] = []
        self._slide_index = 0
        self._photo = None

    STATUS_LABEL = {"draft": "검토 전", "approved": "승인됨", "published": "게시됨"}

    def refresh_posts(self) -> None:
        self._posts = service.list_posts(self.settings)
        self.post_list.delete(0, "end")
        for d, rec in self._posts:
            status = self.STATUS_LABEL.get(rec["status"], rec["status"])
            self.post_list.insert("end", f"[{status}] {rec['created_at'][5:16].replace('T', ' ')} {rec['post']['theme']}")
        if self._posts:
            self.post_list.selection_set(0)
            self.show_selected_post()

    def _selected(self) -> tuple[Path, dict] | None:
        sel = self.post_list.curselection()
        return self._posts[sel[0]] if sel else None

    def show_selected_post(self) -> None:
        item = self._selected()
        if not item:
            return
        d, rec = item
        post = PostDraft.model_validate(rec["post"])
        status = self.STATUS_LABEL.get(rec["status"], rec["status"])
        self.post_title.configure(text=f"{rec['product']} · {post.theme} ({status})")
        caption = rec.get("final_caption")
        if caption is None:
            caption_file = d / "caption.txt"
            caption = caption_file.read_text(encoding="utf-8") if caption_file.exists() else full_caption(post)
        self.caption_text.delete("1.0", "end")
        self.caption_text.insert("1.0", caption)
        warnings = rec.get("warnings", [])
        link = f"\n게시물: {rec['permalink']}" if rec.get("permalink") else ""
        self.warn_label.configure(text="\n".join(f"⚠ {w}" for w in warnings) + link)
        self._slide_index = 0
        self._show_slide()

    def _step_slide(self, delta: int) -> None:
        item = self._selected()
        if item:
            n = len(item[1]["slides"])
            self._slide_index = (self._slide_index + delta) % n
            self._show_slide()

    def _show_slide(self) -> None:
        from PIL import Image, ImageTk

        item = self._selected()
        if not item:
            return
        d, rec = item
        path = d / rec["slides"][self._slide_index]
        img = Image.open(path)
        img.thumbnail((360, 450))
        self._photo = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self._photo)
        self.slide_pos.configure(text=f"{self._slide_index + 1} / {len(rec['slides'])}")

    def approve_post(self) -> None:
        item = self._selected()
        if not item:
            return
        try:
            service.approve(item[0], self.caption_text.get("1.0", "end"))
        except Exception as e:
            messagebox.showerror("승인 실패", str(e))
            return
        self._reselect_after_refresh(item[0])

    def publish_post(self) -> None:
        item = self._selected()
        if not item:
            return
        d, rec = item
        if rec["status"] == "draft":
            if not messagebox.askyesno("승인 필요", "아직 승인하지 않은 게시물입니다. 현재 캡션으로 승인하고 게시할까요?"):
                return
            service.approve(d, self.caption_text.get("1.0", "end"))
        if not messagebox.askyesno("게시 확인", "Instagram에 지금 게시할까요? 게시 후에는 이 프로그램에서 되돌릴 수 없습니다."):
            return

        def done(link):
            self._reselect_after_refresh(d)
            messagebox.showinfo("게시 완료", f"게시했습니다.\n{link}")

        self.run_task(lambda: service.publish(d, self.settings, log=self.log), done)

    def _reselect_after_refresh(self, post_dir: Path) -> None:
        self.refresh_posts()
        for i, (d, _) in enumerate(self._posts):
            if d == post_dir:
                self.post_list.selection_clear(0, "end")
                self.post_list.selection_set(i)
                self.show_selected_post()
                break

    def open_post_dir(self) -> None:
        item = self._selected()
        if item:
            open_path(item[0])


def selftest(out_dir: Path) -> int:
    """빌드된 exe 점검용: 주요 모듈을 불러오고 슬라이드 1장을 렌더링해 결과를 파일로 남긴다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import anthropic  # noqa: F401
        import boto3  # noqa: F401
        from google import genai  # noqa: F401

        from .images.renderer import SlideRenderer, render_html
        from .models import Slide

        html = render_html(Slide(layout="cta", headline="InstaPromo 점검", body="한글 렌더링 확인"),
                           Brand(), background=None, index=1, total=1)
        with SlideRenderer(Settings.load(use_env=False).chromium_executable or None) as renderer:
            renderer.render(html, out_dir / "slide.jpg")
        (out_dir / "result.txt").write_text("ok", encoding="utf-8")
        return 0
    except Exception:
        (out_dir / "result.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(Path(sys.argv[2])))
    App().mainloop()


if __name__ == "__main__":
    main()
