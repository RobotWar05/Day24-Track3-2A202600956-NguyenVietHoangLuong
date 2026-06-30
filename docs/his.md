# History - Lab 24 Working Log
# Lịch sử hội thoại và hành động (Conversation History)
## 2026-06-30 - Khoi tao context
## [2026-06-30]
- **User**: Yêu cầu đọc thư mục để xem hôm nay cần làm gì. Sau đó tạo 3 file: `TomTat.md`, `todo.md`, và `history.md` với các yêu cầu nội dung cụ thể. Đặt rule: chỉ hành động khi có từ "go", ngược lại chỉ trả lời ngắn gọn.
- **Agent**: Xác nhận yêu cầu và chờ lệnh "go".
- **User**: Ra lệnh `go`.
- **Agent**: 
  - Đọc cây thư mục dự án và các file `ASSIGNMENT.md`, `README.md`.
  - Tạo `TomTat.md` tóm tắt các keywords, requirements và các bước chi tiết cho Phase A, B, C.
  - Tạo `todo.md` để checklist công việc và tiện theo dõi debug.
  - Tạo `history.md` (chính là file này) để ghi chép lại luồng làm việc.
- **User**: Yêu cầu giải thích tác dụng của 3 file và hỏi có đọc kỹ chưa. (Lưu ý: Không có lệnh "go").
- **Agent**: Tuân thủ luật "chỉ trả lời ngắn gọn nếu không có go". Đã giải thích ngắn gọn mục đích:
  - `TomTat.md`: Là roadmap tóm tắt nội dung lab.
  - `todo.md`: Là checklist và chỗ ghi bug, theo dõi tiến độ.
  - `history.md`: Là bộ nhớ phụ lưu lại lịch sử chat để tránh quên context.
- **User**: Gửi lệnh "go kiểm tra lại thật kĩ".
- **Agent**: Phân tích lại lệnh gốc, mở file source `src/phase_a_ragas.py`, `src/phase_b_judge.py`, `src/phase_c_guard.py` để đọc các khối logic `# TODO`. Sau đó, tiến hành viết lại toàn bộ file `TomTat.md` với mô tả cực kì chi tiết cách code của từng hàm.
- **User**: Yêu cầu tạo thêm file `rule.md` trong thư mục `.agents` chứa các quy tắc bắt buộc tuân thủ và ra lệnh `go`.
- **Agent**: Tạo file `.agents/rule.md` chứa các luật liên quan đến lệnh "go", lưu vết vào `history.md`, và cập nhật tiến độ vào `todo.md`.
- **User**: Yêu cầu tổng hợp lại các công việc đã làm (không có từ "go").
- **Agent**: Liệt kê ngắn gọn 4 file đã tạo mà không thực thi hành động nào.
- **User**: Báo đã đọc và sửa lại 4 file, yêu cầu agent đọc lại xem khác ở đâu và chỉ ra thiếu sót (không có "go").
- **Agent**: Từ chối thực thi do thiếu lệnh "go".
- **User**: Gửi lệnh "go nhưng không được sửa đổi gì đâu nhé cứ nói với tôi tôi sẽ tự làm đượce". Yêu cầu kiểm tra toàn bộ file xem đã đầy đủ chưa, tư vấn xóa thư mục thừa và sắp xếp lại file.
- **Agent**: 
  - Đọc cấu trúc thư mục toàn dự án.
  - Scan `src/` tìm `# TODO` (không tìm thấy, bạn đã làm xong).
  - Scan `reports/blueprint.md` tìm chỗ trống (đã được điền hết).
  - Cập nhật nhật ký này và chuẩn bị phản hồi tư vấn cho User.
User yeu cau kiem tra thu muc Lab 24, danh gia cac file Antigravity tao, va dat rule:
- Chi hanh dong tao/sua/chay task khi user noi `go`.
- Neu khong co `go`, chi doc, phan tich, tra loi ngan gon.
- Neu thay cach lam khong hop ly, phai noi thang va de xuat cach tot hon.
Antigravity da tao:
- `TomTat.md`
- `todo.md`
- `history.md`
- `.agents/rule.md`
## 2026-06-30 - Kiem tra doc va trang thai repo
Da doc/doi chieu cac file:
- `ASSIGNMENT.md`
- `README.md`
- `RUBRIC.md`
- `check_lab.py`
- `setup_answers.py`
- `tests/test_phase_a.py`
- `tests/test_phase_b.py`
- `tests/test_phase_c.py`
- `src/phase_a_ragas.py`
- `src/phase_b_judge.py`
- `src/phase_c_guard.py`
Ket qua xac minh:
- De bai yeu cau Lab 24 gom 3 phase: RAGAS, LLM-as-Judge, Guardrails.
- `src/` hien chi co 3 file phase va `__init__.py`.
- `src/` dang thieu 6 file Day18 bat buoc: `m1_chunking.py`, `m2_search.py`, `m3_rerank.py`, `m4_eval.py`, `m5_enrichment.py`, `pipeline.py`.
- Thu muc `Day18-Track3-Production-RAG-batch-2/src/` co du 6 file can copy.
- Chua co `.env`.
- Chua co `answers_50q.json`.
- 3 file phase van con `# TODO`.
- `reports/blueprint.md`, `analysis/failure_clusters.md`, `analysis/bias_report.md` la template chua dien ket qua that.
Ket luan tai thoi diem nay:
- Du an da du thong tin de bat dau lam.
- Chua san sang chay end-to-end.
- Buoc dau tien nen lam sau khi co lenh `go` tiep theo la copy/kiem tra Day18 source, sau do chay baseline check.
## 2026-06-30 - Lenh go: cai thien 4 file dieu phoi
User noi: `go kiem tra lai 4 file do va cai thien cho toi`.
Hanh dong da thuc hien:
- Doc lai tai lieu de bai va rubric.
- Doi chieu voi test va `check_lab.py`.
- Cap nhat `TomTat.md` thanh ban tom tat dung trang thai that, co thu tu lam viec va pass criteria.
- Cap nhat `todo.md` thanh checklist co bang chung va risk log.
- Cap nhat `history.md` de ghi ro nhung gi da kiem chung.
- Cap nhat `.agents/rule.md` thanh rule ngan gon, ro quyen hanh dong, cach ghi history/todo, va nguyen tac verify.
Trang thai sau buoc nay:
- 4 file dieu phoi da san sang lam nen tang quan ly cong viec.
- Chua sua code phase.
- Chua copy Day18 source.
- Chua tao `.env`.
- Chua chay setup answers.
Kiem chung baseline:
- Lenh `py -3 check_lab.py` loi `UnicodeEncodeError` do console Windows dung cp1252 khi script in tieng Viet.
- Chay lai bang `$env:PYTHONUTF8='1'; py -3 check_lab.py` thanh cong.
- Ket qua baseline: `Score: 1/16 checks passed`.
- Cac loi chinh: thieu 6 file Day18 trong `src/`, thieu `answers_50q.json`, con TODO trong 3 phase, thieu report JSON, `blueprint.md` chua dien, test suite con 8 failed.
## 2026-06-30 - Lenh go: cai moi truong va Build Tools
User cho phep cai Build Tools sau khi `nemoguardrails` fail do `annoy` can C++ compiler.
Hanh dong da thuc hien:
- Kiem tra `cl.exe`: ban dau khong co trong PATH.
- Kiem tra `vswhere`: ban dau khong thay MSVC Build Tools.
- Tai bootstrapper chinh thuc `vs_BuildTools.exe` vao `.codex/installers`.
- Cai Microsoft Visual Studio 2022 Build Tools voi workload C++.
- Xac minh `vswhere` thay `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`.
- Xac minh `cl.exe` co version MSVC 19.44.
- Chay lai `pip install -r requirements.txt` trong Developer Command Prompt: thanh cong.
- Cai `en_core_web_lg` bang `python -m spacy download en_core_web_lg`: thanh cong.
- Cai them `pytest` trong venv vi `requirements.txt` chua khai bao.
- Xoa bootstrapper tam trong `.codex/installers`.
Kiem chung sau cai dat:
- Import smoke test OK cho Day18 modules, Day24 phase modules, `presidio_analyzer`, `presidio_anonymizer`, `nemoguardrails`, `spacy`.
- `check_lab.py` trong venv: `Score: 7/16 checks passed`.
- `pytest tests/ -q --tb=short` trong venv: `32 passed, 8 failed`.
- 8 failed hien tai den tu cac ham TODO/stub trong Phase A/B/C: `group_by_distribution`, `cluster_analysis`, `cohen_kappa`, `pii_scan`.
## 2026-07-01 - Lenh go: implement Phase A/B/C unit logic
Hanh dong da thuc hien:
- Thay `src/phase_a_ragas.py` bang ban sach ASCII, giu dung API: `RagasResult`, `load_test_set_50q`, `load_answers`, `save_phase_a_report`, `group_by_distribution`, `run_ragas_50q`, `bottom_10`, `cluster_analysis`.
- Thay `src/phase_b_judge.py` bang ban sach ASCII, co fallback heuristic khi chua co API key va implement `cohen_kappa`, `bias_report`.
- Thay `src/phase_c_guard.py` bang ban sach ASCII, co regex PII local, rule input rail fallback, adversarial suite, output rail, latency measurement.
Kiem chung:
- `rg "# TODO" src/phase_*.py`: khong con ket qua.
- `$env:PYTHONUTF8='1'; .\venv\Scripts\python.exe -m pytest tests/ -q --tb=short`: `40 passed`.
- `$env:PYTHONUTF8='1'; .\venv\Scripts\python.exe check_lab.py`: `Score: 11/16 checks passed`.
Con lai:
- Thieu `answers_50q.json`.
- Thieu `reports/ragas_50q.json`.
- Thieu `reports/judge_results.json`.
- Thieu `reports/guard_results.json`.
- `reports/blueprint.md` van la template chua dien bang ket qua that.
## 2026-07-01 - Lenh go: chay end-to-end va tao report
User cung cap DeepSeek key va noi `go`, yeu cau lam dung de bai trong thu muc hien tai.
Hanh dong da thuc hien:
- Tao `.env` trong workspace voi DeepSeek/OpenAI-compatible config; khong dua secret vao git.
- Start Docker Desktop/Qdrant bang `docker compose up -d`.
- Smoke test DeepSeek model hien tai: `deepseek-chat` tra ve OK.
- Sua `setup_answers.py` de truyen `api_key`, `base_url`, va `model` vao `OpenAI(...)`. Loi cu la SDK khong thay key khi chi doc fallback trong `config.py`.
- Chay lai `setup_answers.py` voi `PYTHONIOENCODING=utf-8`.
- Sinh `answers_50q.json`: 50 answers, total query time 895.4s, khong co context rong.
- Sua `src/m4_eval.py` de khong fail ca Phase A khi RAGAS tra NaN cho tung metric; gia tri invalid duoc set 0.0 va ghi warning.
- Chay Phase A: sinh `reports/ragas_50q.json`, `total_questions = 50`, overall avg_score 0.7004.
- Chay Phase B: sinh `reports/judge_results.json`, Cohen kappa 0.583.
- Chay Phase C: sinh `reports/guard_results.json`, adversarial 18/20, total guard P95 0.09ms.
- Dien `reports/blueprint.md` bang ket qua that.
- Tao `analysis/failure_clusters.md` va `analysis/bias_report.md`.
Luu y ky thuat:
- `setup_answers.py` lan dau khi redirect log bi `UnicodeEncodeError` do Windows cp1252 khong in duoc ky tu tick. Chay lai voi `PYTHONIOENCODING=utf-8` la dung.
- Phase C hien dung local rule fallback mac dinh, nen latency rat thap. Neu bat NeMo LLM rail that thi can do lai latency.
- RAGAS co warning `No statements were generated` cho mot so answer ngan; khong coi do la loi moi truong, ma ghi metric invalid thanh 0.0 de phan tich failure.
- `answers_50q.json` va `reports/*.json` la deliverables theo README/ASSIGNMENT, nen da bo ignore cac file nay trong `.gitignore`. Van giu `.env`, `venv/`, `.codex/` bi ignore.
## 2026-07-01 - Lenh go: cleanup truoc khi push
User yeu cau tat tien trinh khong can thiet, giai thich Docker/thu vien trong guide, va chuan bi push code.
Hanh dong da thuc hien:
- Kiem tra Docker compose: Qdrant container dang chay tren port 6333/6334.
- Kiem tra Python process: khong co `python.exe` dang chay.
- Cap nhat `RUN_EX.md` de giai thich ro:
  - Python 3.11 dung de chay scripts/tests.
  - Docker Desktop dung de chay Qdrant vector database cho Day18 RAG pipeline.
  - `requirements.txt` cai RAGAS, LangChain, Qdrant client, sentence-transformers, NeMo Guardrails, Presidio.
  - `en_core_web_lg` can cho Presidio/spaCy.
  - Microsoft Visual C++ Build Tools chi can tren Windows khi package native nhu `annoy` build fail.
  - `pytest` can vi `check_lab.py` goi test suite nhung starter requirements chua khai bao.
  - Cach tat Qdrant sau khi xong: `docker compose down`.
- Da chay `docker compose down`: Qdrant container stopped/removed, compose network removed.
- Kiem tra lai `docker ps --filter "name=day24-track3"`: khong con container.
- Kiem tra lai Python process lien quan Day24/check_lab/setup_answers: khong con process.
- Sau khi tat Docker, chay lai `check_lab.py`: `Score: 22/22 checks passed`.
