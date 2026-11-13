# Day 06 — Data Ingestion Engineering

Pipeline retrieval cho bản scan 39 trang của **Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân**. Bài dùng OCR có truy vết trang, embedding local đa ngữ, PostgreSQL + pgvector và benchmark ba chiến lược A/B/C.

## Kết quả đã chạy

| Strategy | Chunking / filter | Dev Hit@1 | Dev Hit@3 | Test Hit@1 | Test Hit@3 |
|---|---|---:|---:|---:|---:|
| A | fixed 500 ký tự, overlap 50 | 2/15 | 6/15 | 1/5 | 2/5 |
| B | theo đoạn, tối đa 900, không filter | 9/15 | 12/15 | 2/5 | 3/5 |
| C | giống B, thêm filter `section` khi có | 9/15 | 12/15 | 3/5 | 5/5 |

Quy tắc chốt trước chọn **B trên dev**; B và C hòa trên dev nên B thắng tie theo thứ tự cấu hình cố định. C đạt 5/5 Hit@3 trên test là kết quả mô tả sau khi mở holdout, không được dùng để tinh chỉnh lại lựa chọn.

## Thành phần

- Corpus gốc: `13nd.signed.pdf`; OCR chuẩn: `starter/data/nghi_dinh_13_2023_ND-CP_ocr.json`.
- Manifest: `data/manifest.json` — 39 trang nội dung, 66.956 ký tự sau chuẩn hóa.
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 chiều, CPU, cosine, chi phí API 0 USD.
- Store: PostgreSQL 16 + pgvector 0.8.7, cổng local `127.0.0.1:55433`.
- Benchmark: `benchmark/questions.json` — 15 dev + 5 test, 7 câu có filter.
- Code: `starter/src/`; output: `results/`; audit: `results/manual_audit.json`; báo cáo: `report/individual/MSSV_HoTen.md`.

## Chạy trên VS Code / Windows PowerShell

Yêu cầu: Python 3.11+, Docker Desktop và mạng ở lần cài/tải model đầu tiên. Mở thư mục này trong VS Code, chọn **Terminal → New Terminal**, rồi chạy:

```powershell
cd starter
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
docker compose -p day6_student_starter up -d --wait
python scripts\check_setup.py
python scripts\check_embeddings.py
python -m src.run
```

Lần đầu `check_embeddings.py` tải model từ Hugging Face. Nếu model đã có trong cache nhưng máy đang offline, dùng:

```powershell
$env:HF_HUB_OFFLINE="1"
python -m src.run
```

`src.run` thực hiện đọc/kiểm tra OCR, tạo chunk A và B, embed thật, replace ba strategy trong database, chạy dev trước, cố định lựa chọn, chạy test và ghi artifacts vào thư mục `results/` ở root. Nạp lại không nhân đôi: sau lần chạy đã kiểm tra số row A/B/C lần lượt là 163/103/103.

Dừng database nhưng giữ volume:

```powershell
docker compose -p day6_student_starter stop
```

## Kiểm tra output

- `results/run_config.json`: model, store, tham số và quy tắc chọn.
- `results/ingestion_stats.json`: số chunk, kích thước, thời gian và count sau replace.
- `results/metrics.json`: Hit@1 và Evidence Hit@3 dev/test.
- `results/traces_A.json`, `traces_B.json`, `traces_C.json`: query, gold, top-3, score và metadata.
- `results/manual_audit.json`: coherence, metadata, filter compliance và grounding với nhãn/lý do.
- `results/error_log.txt`: OCR và lỗi kỹ thuật đã gặp, không che giấu fallback.

## Lưu ý trước khi nộp

Điền họ tên, MSSV, lớp, repo và commit trong `STUDENT.md`; đổi tên báo cáo thành `<MSSV>_<HoTen>.md`; tự đọc lại nhãn audit vì Codex là người hỗ trợ triển khai và chấm mẫu, không phải evaluator độc lập. Không commit `.env`, `.venv` hay cache model. Tài liệu là snapshot phục vụ retrieval, không phải tư vấn hoặc kiểm tra hiệu lực pháp luật hiện hành.
