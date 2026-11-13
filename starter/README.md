# Starter · PostgreSQL + pgvector

Pipeline đã hoàn thiện cho corpus Nghị định 13/2023/NĐ-CP. Docker Compose tạo PostgreSQL + pgvector local; `src/` đọc OCR, chia chunk, tạo embedding, lưu vector, chạy benchmark và ghi trace.

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf và python-dotenv
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # đọc / chuẩn hóa OCR và gắn metadata
│   ├── chunking.py        # fixed-size và paragraph-aware
│   ├── embeddings.py      # MiniLM đa ngữ local, 384 chiều
│   ├── store.py           # pgvector, replace idempotent và filter
│   ├── evaluation.py      # Hit@1/Hit@3 và trace
│   └── run.py             # pipeline A/B/C hoàn chỉnh
├── data/                  # OCR JSON chuẩn
└── scripts/               # kiểm tra setup/model và OCR tùy chọn
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14**, và mạng để tải image/dependencies lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Điền key tương ứng trong `.env` nếu dùng OpenRouter, OpenAI hoặc Gemini; **không commit `.env`**. Model local không cần API key. Ghi tên model và số chiều; dùng cùng model cho toàn bộ chiến lược và vector query tương thích vector document.

Starter này được cấu hình sẵn để dùng model local đa ngữ
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` trên CPU. Model
trả về vector 384 chiều và không cần API key. Trong terminal VS Code tại thư
mục `starter/`, chạy:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.check_embeddings
```

Lần đầu chạy sẽ tải model từ Hugging Face vào cache local. Kết quả kiểm tra
thành công kết thúc bằng `Embedding setup OK`. Những lần sau dùng lại model đã
cache. `src/embeddings.py` chuẩn hóa vector trước khi lưu để dùng cosine
similarity nhất quán trong pgvector.

## 3. Chạy pipeline

Từ thư mục `starter/`, chạy `python -m src.run`. Khi model đã cache và không có mạng, đặt `$env:HF_HUB_OFFLINE='1'` trước lệnh. Output được ghi vào `../results/`; xem README ở root để biết cấu hình A/B/C, kết quả và checklist nộp bài.
