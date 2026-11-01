# Books Recommender System

Pipeline gợi ý sách trên bộ [UCSD Goodreads Book Graph](https://cseweb.ucsd.edu/~jmcauley/datasets/goodreads.html), tích hợp với Readora ở `web/`. Mặc định demo đọc Parquet đã có trong `samples_data/`, không cần tải lại raw dataset. Mô hình làm việc ở cấp `work_id`; `canonical_book_id` dùng hệ ID `book_id_csv` của ETL upstream.

## Kiến trúc

- `process/`: notebook tải dữ liệu và ETL MySQL cũ.
- `src/books_recommender/`: chuẩn hóa Parquet, train, đánh giá và inference offline.
- `configs/`: cấu hình sample/full; mọi đường dẫn tương đối được tính từ repository root.
- `artifacts/<run_id>/`: model, transformer, dự đoán và `metrics.json` (không commit Git).
- `notebooks/modeling/`: notebook khám phá/kết quả, chỉ gọi package dùng chung.
- `web/`: frontend/backend upstream; backend hiện nhập Parquet bằng `init_sample_data.py`.
- `src/books_recommender/serving/`: model service tương thích contract của upstream.
- `demo_assets/`: bundle serving nén, được version hóa riêng để nhóm clone về demo ngay.

Pipeline gồm popularity, item-item cosine, Spark implicit ALS, TF-IDF content-based và weighted hybrid. `similar_books`, `average_rating`, `ratings_count` không được dùng làm feature học.

## Cài đặt

Demo cần Python 3.11–3.13, Node.js 22.12+ hoặc 24 và Internet
để cài dependency/tải ảnh bìa. Không cần Java, Spark, Docker hay tài khoản Supabase.
Tại repository root, chạy một lần:

```bash
python scripts/setup_demo.py --install
```

Lệnh này cài dependency runtime và giải nén model có sẵn từ `demo_assets/` vào
`artifacts/remote-demo/`. Source/sample data đã có trong Git; SQLite sẽ tự tạo khi
khởi động catalog. Để **train hoặc chạy integration Spark**, cài thêm Java 17/21 và:

```bash
python -m pip install -e ".[train,dev,serve]"
```

## Demo từ tập mẫu của remote

### Clone nhánh demo và mở trên Windows

```bash
git clone --branch demo-ete --single-branch https://github.com/Cheetah-lhp/Books-Recommender-System.git
cd Books-Recommender-System
```

Tại repository root, cài một lần bằng Python 3.11 (có thể thay bằng 3.12/3.13):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe scripts\setup_demo.py --install
```

Sau đó **nhấp đúp `web/start.bat`** hoặc chạy từ repository root:

```powershell
.\web\start.bat
```

`start.bat` ở repository root cũng gọi cùng launcher. Launcher tự tìm Python trong
`.venv`, mở ba cửa sổ **Readora catalog/model/frontend**, đợi catalog có dữ liệu và model
đúng run `remote-demo`, rồi mở **http://127.0.0.1:3000/demo** khi frontend sẵn sàng.
Không cần activate venv hay tự đặt biến môi trường. Nếu thiếu dependency hoặc có cổng
8000/8001/3000 bị chiếm, launcher dừng và báo lỗi; không tự tắt tiến trình có sẵn.
Nếu một service lỗi/timeout, xem cửa sổ tương ứng và dừng các service đã mở trước khi
chạy lại. Dùng **Ctrl+C trong cả ba cửa sổ**, rồi đóng chúng để dừng demo.

Các đường dẫn được tính từ vị trí file script/repository; mỗi thành viên có thể
clone vào thư mục khác. Không chia sẻ `.venv` giữa các máy. Nếu đổi tên hoặc di
chuyển checkout đã setup, nên tạo lại `.venv` ở vị trí mới; dữ liệu và bundle model
không cần tải lại.

Launcher không cài lại Python dependency mỗi lần chạy; frontend chỉ tự chạy `npm ci`
khi chưa có `node_modules`. Có thể truyền `-NoBrowser` để không tự mở trình duyệt,
hoặc `-StartupTimeoutSeconds 600` nếu lần cài frontend đầu tiên mất nhiều thời gian.

Run `remote-demo` đã được đóng gói sẵn trong nhánh này (archive khoảng 6,3 MiB).
Không cần train lại hoặc xin thêm file model từ máy người khác.
Nếu muốn điều khiển riêng từng dịch vụ, vẫn có thể mở **ba terminal PowerShell** tại
repository root, mỗi terminal chạy một lệnh (script cũng tự tìm Python trong `.venv`):

```powershell
.\scripts\start-demo.ps1 -Service catalog
```

```powershell
.\scripts\start-demo.ps1 -Service model
```

```powershell
.\scripts\start-demo.ps1 -Service frontend
```

Sau khi cả ba service sẵn sàng, mở **http://127.0.0.1:3000/demo**. Chọn một trong
ba tình huống, chọn thể loại/sách rồi bấm **Lấy gợi ý**. Trang hiển thị trạng thái
**Đang dùng model · remote-demo**, sách đầu vào và 12 gợi ý. Tình huống lịch sử
còn mô phỏng một sách 1 sao và một sách bị ẩn để kiểm tra loại trừ.

Demo gọi cùng recommendation engine và HTTP model service của ứng dụng, dùng
catalog thật 10.000 sách. Tín hiệu user được tạo cho từng lượt thử, không cần đăng
nhập, không tạo tài khoản hay ghi dữ liệu Supabase. Endpoint demo chỉ bật khi
`READORA_DEMO_MODE=1` (script đã cấu hình). Luồng đăng nhập thông thường giữ nguyên.
Catalog dùng SQLite riêng ở `data/demo_catalog.db`; không cần MySQL hoặc Docker.
Script dùng `ratings_count` để chọn pool sách phổ biến cho demo, còn cấu hình web
thông thường vẫn giữ `rating` như upstream.

Nếu PowerShell chặn chạy script, dùng cho từng lệnh:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-demo.ps1 -Service frontend
```

Cài dependency bằng bước `setup_demo.py --install` ở trên; phần frontend tự chạy
`npm ci` nếu chưa có `node_modules`. Có thể dùng `-Install` trên launcher khi cần
cài lại dependency backend đầy đủ. Python 3.11/3.13 và Node 24 đã được kiểm thử.
Giữ ba terminal mở; **Ctrl+C** ở từng terminal để dừng. Muốn thử fallback, dừng riêng
terminal `model`, bấm lại **Lấy gợi ý**: trang vẫn có sách và báo **Đang dùng fallback**.
Chạy lại lệnh `-Service model` để phục hồi. Script từ chối mở service thứ hai nếu
port của nó đang được sử dụng.

Health checks: `http://127.0.0.1:8000/health` và `http://127.0.0.1:8001/health`.
Đường dẫn frontend chính vẫn là `http://127.0.0.1:3000/`.

Kiểm tra tự động qua trình duyệt (cần `pip install playwright`; nếu chưa có browser,
chạy `python -m playwright install chromium`):

```powershell
python scripts/check_demo.py --check-covers
# Dừng riêng model, sau đó kiểm tra fallback:
python scripts/check_demo.py --fallback
```

Kết quả/screenshot nằm trong `logs/demo/browser-check.json`, `fallback-check.json`
và các file PNG cùng thư mục. Test kiểm tra ID, không trùng work, loại các sách đã
đọc/1 sao/ẩn, không có JavaScript page error và không tràn ngang ở màn hình hẹp.
Các file runtime, SQLite và screenshots đều được Git ignore. Việc đánh giá offline
trên tập demo thật để tạo `metrics.json` vẫn là bước riêng, chưa chạy ở lượt này.
Bundle serving nhỏ dưới `demo_assets/` là asset demo được commit có chủ đích;
model train đầy đủ, các run mới, database và logs vẫn được ignore. Catalog sẽ
tự đồng bộ URL ảnh từ Parquet khi khởi động lại sau các cập nhật dữ liệu.

Linux/macOS có thể dùng cùng `setup_demo.py`, rồi chạy ba service ở các terminal
riêng (thay `<repo>` bằng đường dẫn tuyệt đối của checkout):

```bash
mkdir -p data
DB_ENGINE=sqlite BOOKS_SQLITE_PATH="<repo>/data/demo_catalog.db" python web/backend/init_sample_data.py
DB_ENGINE=sqlite BOOKS_SQLITE_PATH="<repo>/data/demo_catalog.db" python -m uvicorn main:app --app-dir web/backend --host 127.0.0.1 --port 8000
```

```bash
ML_CATALOG_URL=http://127.0.0.1:8000 python -m books_recommender.cli serve --run-id remote-demo --port 8001
```

```bash
cd web/front_end
npm ci --no-audit --no-fund
READORA_DEMO_MODE=1 READORA_CATALOG_SORT=ratings_count ML_RECOMMENDER_URL=http://127.0.0.1:8001/recommend API_BASE=http://127.0.0.1:8000 VITE_API_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --strictPort
```

### Chuẩn bị hoặc train lại demo

`configs/demo.yaml` đọc 10.000 sách từ `samples_data/`, lọc user có ít nhất 5 positive
ở cấp work rồi chọn ổn định tối đa 3.000 user. Lịch sử chỉ đầy đủ **trong tập sách mẫu**,
vì upstream lấy mẫu theo sách. Adapter đọc `books`, `works`, `authors`, `genres`,
`book_authors_map`, `interactions`; `reviews` chỉ cần cho temporal split. Các bảng phụ
lớn được lọc bằng Spark join. Metadata đã bị upstream bỏ như shelves được để rỗng.

Trên Windows dùng Docker (hai lệnh chạy lần lượt):

```bash
docker compose --profile modeling run --rm --build modeling
docker compose --profile modeling up -d --build recommender
```

Lệnh đầu chạy prepare → train → export-serving → evaluate, ghi `metrics.json`.
Lệnh thứ hai mở model service ở `http://127.0.0.1:8001`, không khởi động MySQL.
Nếu model đã chạy trong Docker, chỉ mở catalog và frontend ở hai terminal riêng
(không dùng `start.bat` vì launcher này luôn khởi động đủ ba service):

```powershell
.\scripts\start-demo.ps1 -Service catalog
# Terminal khác:
.\scripts\start-demo.ps1 -Service frontend
```

Đây là URL của **model registry `ML_RECOMMENDER_URL`**, phục vụ luồng `getForYou`.
Không gán nó vào legacy `RECOMMENDER_API_URL`: endpoint questionnaire cũ dùng payload
và response khác. Các biến tùy chọn nằm ở `modeling/readora.env.example`.

Trên Linux/WSL cũng có thể chạy native:

```bash
python -m books_recommender.cli run-all --config configs/demo.yaml
python -m books_recommender.cli serve --run-id latest --port 8001
```

Nếu chỉ cần train và export để nối web trước khi evaluate:

```bash
python -m books_recommender.cli prepare --config configs/demo.yaml
python -m books_recommender.cli train --models hybrid --config configs/demo.yaml --run-id remote-demo
```

Nếu run ID đã tồn tại, trainer sẽ tạo tên có hậu tố; truyền tên run thực tế vào
`start-demo.ps1 -Service model -RunId <run_id>`. Bundle có sẵn chỉ phục vụ inference;
không chứa full Spark model/config để tiếp tục train hoặc evaluate. Muốn đánh giá,
hãy prepare/train một run mới. Có thể train trên Windows bằng Docker:

```bash
docker compose --profile modeling run --rm --build modeling prepare --config configs/demo.yaml
docker compose --profile modeling run --rm modeling train --models hybrid --config configs/demo.yaml --run-id remote-demo-trained
```

Model service dùng sparse TF-IDF và ALS item factors đã nạp sẵn; không mở Spark
trong mỗi request. Serving được giới hạn 50.000 work để vừa bộ nhớ; `full.yaml`
vẫn dùng Spark phân tán và không tự export toàn bộ catalog vào RAM.

## Quy ước ID và contract Readora

| Trường | Ý nghĩa |
| --- | --- |
| `samples_data.books.book_id` | `book_id_csv` từ ETL upstream |
| `canonical_book_id` | `book_id_csv` của edition canonical có mặt trong catalog |
| `original_book_id` trong catalog ML | Goodreads ID gốc, lấy từ URL ở sample mode khi có |
| `web` backend `books.id` | Khóa chính database, chính là ID frontend gửi |
| `web` backend `books.goodreads_id` | Trong import sample hiện tại, chứa `book_id_csv` |
| `userId` của Readora | User ứng dụng/Supabase, không phải user Goodreads |

Service gọi `POST /api/books/batch` trên backend hiện có để ánh xạ `books.id` →
`goodreads_id` → work. Không suy đoán hai ID bằng nhau, không gọi dịch vụ Goodreads.
Khi database được thay bằng nguồn có namespace khác, cần một bảng mapping rõ ràng;
không đổi ý nghĩa `goodreads_id` bằng cách đoán theo giá trị.

`POST /recommend` nhận đúng payload từ `web/front_end/src/lib/ml/engine.server.ts`:

```json
{
  "userId": "application-user-uuid",
  "preferences": {"genres": ["Fantasy & Paranormal"], "favorite_books": ["123"]},
  "history": [{"book_id": "123", "status": "read"}],
  "ratings": [{"book_id": "123", "rating": 5}],
  "feedback": {"liked": [], "disliked": [], "hidden": []},
  "candidates": ["456", "789"]
}
```

Response là `{"books": [{"id": "456", "score": 0.8, "reason": "..."}], "run_id": "..."}`.
ID trả về giữ nguyên ID frontend; chỉ rerank candidates đã gửi, gộp các edition cùng
work và loại work đã đọc/bị ẩn/low rating trong kết quả model. Khi có response model
hợp lệ, web chỉ dùng danh sách đã lọc đó, tránh nối lại sách/edition mà model đã loại.
Response bổ sung `work_id` cho mỗi sách và `mapped_candidates` cho lượt gọi. Model
không khả dụng hoặc không ánh xạ được candidates thì web giữ heuristic fallback.
User mới được dựng profile từ favorite/history/rating/feedback live; ALS fold-in dùng
item factors đã train, không gán UUID hay số userId vào user Goodreads.
Không có signal dùng popularity; genre/seed chưa có ALS factor dùng content.
Catalog không khả dụng trả 503 để upstream fallback, ID không ánh xạ được bị bỏ qua.

`GET /health` trả run đang phục vụ. `ML_API_KEY` tùy chọn bật Bearer auth cho model API.
Service không tự reload khi `LATEST` thay đổi; restart service sau khi train run mới.
Run cũ chuẩn ID Goodreads phải chạy lại prepare/train trước khi export-serving.
Bundle version hóa có SHA-256 trong `demo_assets/manifest.json`; `setup_demo.py`
kiểm tra checksum, không ghi đè run đã tồn tại và không mang đường dẫn máy tác giả.

## Dùng raw/full dataset

Chạy `process/download.ipynb` để tải dữ liệu vào `data/`. JSON đã giải nén và `.json.gz` đều được hỗ trợ. Các file tối thiểu:

```text
goodreads_books.json[.gz]
goodreads_book_works.json[.gz]
goodreads_book_authors.json[.gz]
goodreads_book_genres_initial.json[.gz]
book_id_map.csv
goodreads_interactions.csv
```

Temporal review split cần thêm `goodreads_reviews_dedup.json[.gz]` và `user_id_map.csv`.

## Chạy pipeline

Vòng lặp phát triển mặc định lấy ổn định 10.000 user và toàn bộ lịch sử của họ:

```bash
books-recommender prepare --config configs/sample.yaml
books-recommender train --models all --config configs/sample.yaml
books-recommender evaluate --run-id latest
books-recommender recommend --run-id latest --user-id 123 --top-k 20
```

Cold-start từ sách hoặc thể loại:

```bash
books-recommender recommend --run-id latest --seed-book-ids 948,1024
books-recommender recommend --run-id latest --genres fantasy,history
```

Chạy trọn quy trình:

```bash
books-recommender run-all --config configs/sample.yaml
```

Full dataset dùng `configs/full.yaml`. Cấu hình mặc định vẫn là local Spark; trên cluster hãy override `spark.master`, memory và số shuffle partitions. Không có bước nào collect toàn bộ interactions/catalog về driver.

Docker profile không phụ thuộc MySQL:

```bash
docker compose --profile modeling run --rm modeling
```

Trên Windows, Hadoop đi kèm PySpark có thể không ghi được Parquet ở local nếu thiếu
binary `winutils` tương thích. Cách chạy được hỗ trợ và đã kiểm thử là Docker command
ở trên hoặc WSL/Linux; không cần tải `winutils.exe` từ nguồn không chính thức.

## Dữ liệu ML và artifacts

`prepare` tạo:

- `books/`: một dòng mỗi work, canonical edition và metadata nội dung.
- `interactions/`: strength và partition `train/validation/test`.
- `edition_to_work/`: mapping edition sang item cấp work.

Mỗi run lưu config snapshot, manifest, ALS model, TF-IDF pipeline/vectors, neighbor tables và báo cáo. Demo còn có `serving/` (catalog/vectors, edition aliases, ALS factors và manifest) độc lập với đường dẫn processed, dùng được khi chuyển container sang máy Windows. `metrics.json` có Precision, Recall, NDCG, MAP, MRR, hit rate ở K=5/10/20, coverage, novelty, genre diversity và các slice user/item.

## Kiểm thử

```bash
pytest -q
pytest -q -m integration
ruff check src tests
```

Integration test chạy cả hai schema raw và sample Parquet, gồm `prepare → train → evaluate → recommend → export/load → HTTP rerank`, không cần tải dataset thật. Unit/API test chạy được trên Windows, kiểm tra ID mapping khác nhau, UUID user, cold-start, loại edition trùng, auth và fallback.
Trên Windows, test Spark này tự skip; chạy bản Linux giống môi trường modeling bằng Docker:

```bash
docker build -t books-recommender:test -f modeling/Dockerfile .
docker run --rm --entrypoint sh -v "${PWD}:/workspace" -w /workspace books-recommender:test \
  -c "pip install -q pytest httpx && PYTHONPATH=/workspace/src pytest -q -m integration"
```
