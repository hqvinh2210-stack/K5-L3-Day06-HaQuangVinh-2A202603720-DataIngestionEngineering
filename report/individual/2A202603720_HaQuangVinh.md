# Báo cáo cá nhân — Day 6

> Học viên cần đổi tên file thành `<MSSV>_<HoTen>.md` và điền thông tin còn thiếu trong `STUDENT.md` trước khi nộp.

## Dữ liệu và pipeline

- **Chủ đề và nguồn:** Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân, bản PDF công khai từ Cổng Thông tin điện tử Chính phủ (`13nd.signed.pdf`). Manifest nằm tại `data/manifest.json`. Corpus gồm 39/39 trang vật lý; tính cả phần quy định và biểu mẫu phụ lục vì đều có nội dung hữu ích, không có trang trống. Mục đích sử dụng là học tập/đánh giá nội bộ; không coi việc công khai là giấy phép tái phân phối vô điều kiện.
- **Đọc và chuẩn hóa:** PDF là bản scan nên pipeline dùng JSON OCR 39 trang do học viên cung cấp. Chuẩn hóa Unicode NFC, xuống dòng, khoảng trắng; giữ đoạn và ID trang vật lý. JSON được kiểm tra đủ trang 1–39, không trùng, không rỗng. Có 3 marker không đọc rõ/nhiễu; cần xem lại trực quan các trang 1, 35, 37, 39. Không câu gold nào dựa vào đoạn không đọc rõ. OCR EasyOCR thử nghiệm 15 trang chỉ là output phụ, không được pipeline tiêu thụ.
- **Embedding/store:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, vector 384 chiều, CPU, L2-normalized; PostgreSQL 16.16 + pgvector 0.8.7; exact cosine distance. Lệnh chính: `cd starter`, bật `.venv`, `docker compose -p day6_student_starter up -d --wait`, rồi `$env:HF_HUB_OFFLINE='1'; python -m src.run` nếu model đã cache. Model local nên chi phí API là **0 USD**; thời gian CPU được báo riêng.
- **Metadata:** bắt buộc `document_id`, `source`, `page` vật lý; bổ sung `printed_page`, `section`, `year`, `document_type`, `language`, `ocr_source`, phương pháp/index/ranh giới chunk. `section` được nhận từ heading Chương/Phụ lục trong OCR rồi truyền sang các trang kế tiếp; dùng để lọc vì phạm vi chương được người dùng cung cấp trước retrieval. `page` vật lý là locator chính vì số trang in trong phụ lục khởi động lại.

## Cấu hình và benchmark

- **A:** cửa sổ cố định 500 ký tự, overlap 50, không filter.
- **B:** gom theo đoạn, cắt mềm đoạn quá dài, tối đa 900 ký tự, không overlap, không filter.
- **C:** dùng đúng chunk và vector của B; chỉ thêm filter `section` khi câu hỏi có filter. Vì vậy so sánh B–C chỉ thay đúng một yếu tố ở retrieval.
- Bộ `benchmark/questions.json` gồm 20 câu đã viết và gắn evidence: 15 dev (`q01`–`q15`) và 5 test (`q16`–`q20`). Có 7 câu filter: 3 dev và 4 test. Evidence được đối chiếu bằng chuỗi chuẩn hóa tồn tại đúng trang OCR trước khi chạy; mỗi câu có đáp án, source, page và quote.
- Tiêu chí chọn đã chốt: Evidence Hit@3 dev cao nhất, sau đó Hit@1 dev, sau đó ít chunk hơn. B và C hòa hoàn toàn trên dev (12/15 Hit@3, 9/15 Hit@1, 103 chunk); tie còn lại được giải theo thứ tự cấu hình cố định nên **B được chọn trước khi đọc test**. Kết quả test C chỉ là quan sát hậu nghiệm, không dùng đổi nhãn cấu hình đã chọn.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian nạp | Chi phí API |
|---|---|---|---|---:|---:|---:|
| A | dev | 2/15 (13,3%) | 6/15 (40%) | 163 | 10,965 s | 0 USD |
| A | test | 1/5 (20%) | 2/5 (40%) | 163 | 10,965 s* | 0 USD |
| B | dev | 9/15 (60%) | 12/15 (80%) | 103 | 6,732 s | 0 USD |
| B | test | 2/5 (40%) | 3/5 (60%) | 103 | 6,732 s* | 0 USD |
| C | dev | 9/15 (60%) | 12/15 (80%) | 103 | 0,159 s* | 0 USD |
| C | test | 3/5 (60%) | 5/5 (100%) | 103 | 0,159 s* | 0 USD |

\* Thời gian nạp được đo một lần cho mỗi strategy rồi dùng chung cho hai dòng dev/test, không phải hai lần chạy riêng. C tái sử dụng embedding của B để giữ phép so sánh kiểm soát; 0,159 s là thời gian ghi strategy C, không phải thời gian embed lại.

| Strategy | Coherence TB /2 (n=10) | Metadata đủ và đúng | Filter tuân thủ | Grounding 0/1/2 và TB /2 |
|---|---:|---:|---:|---:|
| A | 0,30 | 15/15 | N/A (không áp dụng filter) | 1 / 1 / 3; **1,40** |
| B | 1,60 | 15/15 | N/A (không áp dụng filter) | 2 / 0 / 3; **1,20** |
| C | 1,60 | 15/15 | 4/4 câu test có filter | 0 / 0 / 5; **2,00** |

Trace đầy đủ: `results/traces_A.json`, `traces_B.json`, `traces_C.json`. Nhãn và lý do thủ công: `results/manual_audit.json`. Coherence dùng cùng vị trí ký tự 0 của 10 trang vật lý đầu, đã cố định trước khi so sánh. Metadata đọc 5 câu test × top-3 cho từng strategy. Grounding đọc toàn bộ top-3 của q16–q20. Người chấm là Codex hỗ trợ AI, đồng thời tham gia triển khai nên có nguy cơ thiên lệch; học viên phải đọc lại nhãn trước khi bảo vệ bài.

## Phân tích và kết luận

- **A–B:** chunk theo đoạn giảm 60 chunk (163 xuống 103), giảm ký tự lặp do overlap, tăng coherence 0,30 lên 1,60 và tăng Hit@3 dev 40% lên 80%. Fixed window thường cắt giữa từ/ý. Ví dụ `q20` ở A tìm đúng trang nhưng gold exact bị trượt vì chunk bắt đầu giữa từ “nhỏ”; audit vẫn chấm grounding 2 vì top-3 đủ điều khoản và ngoại lệ. Điều này cho thấy exact quote là metric nghiêm ngặt và cần đọc trace.
- **B–C:** không thay chunk/vector. Với `q19`, B trả trang 28/29/10 và bỏ lỡ ngày hiệu lực ở trang 27; filter `chuong_iv` của C đưa evidence trang 27 vào rank 2. Với `q20`, B bị nhiễu bởi các đoạn 72 giờ ở Chương II; C giới hạn Chương IV và tìm được điều khoản miễn trừ cùng ngoại lệ. Test tăng Hit@3 từ 3/5 lên 5/5, nhưng mẫu chỉ có bốn câu test áp dụng filter nên không được suy rộng.
- **Chiến lược chọn:** theo quy tắc chốt trước, B là lựa chọn benchmark chính vì hòa C trên dev và thắng tie theo thứ tự cố định. Trong ứng dụng thực tế, nếu `section` là input đáng tin cậy, C là biến thể vận hành hợp lý; nếu section thiếu hoặc sai, pipeline tự chạy như B hoặc có thể loại nhầm evidence.
- **Hạn chế:** OCR chưa được người kiểm tra độc lập duyệt toàn bộ; section phụ thuộc heading OCR; corpus chỉ có một văn bản và test chỉ 5 câu; 4/5 câu test có filter làm lợi ích C dễ thấy hơn; exact substring không nhận tương đương ngữ nghĩa hoặc evidence ghép nhiều chunk; thời gian đo một lượt trên CPU và chịu cache; chi phí điện/phần cứng không quy đổi. Đây là snapshot văn bản 2023 cho retrieval, không phải hệ thống xác định hiệu lực pháp luật hiện hành.
- **Nếu mở rộng:** thêm nhiều văn bản/năm để filter có bài toán phân biệt khó hơn; tạo test holdout mới do test hiện đã được xem; review OCR hai người; dùng article/heading parser để gắn `article`; đánh giá recall đa-evidence; thử hybrid BM25+dense và reranker, nhưng chỉ chọn tham số trên dev.

## Công cụ AI và kiểm tra

ChatGPT được dùng để tạo OCR từ file scan; Codex hỗ trợ viết code, chạy thử, phân tích trace và soạn nhãn audit. Các kiểm tra đã thực hiện gồm: xác thực đủ 39 trang OCR, kiểm tra 20 evidence, kiểm tra embedding 384 chiều, kết nối PostgreSQL/pgvector, chạy đủ A/B/C, kiểm tra số row sau replace (163/103/103) và lưu log lỗi. Không dùng API embedding trả phí và không dùng vector ngẫu nhiên.
