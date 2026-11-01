# Kiểm tra demo Readora — 2026-10-29

Đã thực hiện ba bước khởi động, cấu hình và kiểm tra frontend trên máy Windows.
Demo hiện dùng SQLite riêng `data/demo_catalog.db` với 10.000 sách; model service
phục vụ bundle `artifacts/remote-demo/serving`. Không chạy Spark hoặc tải raw data
trong lượt kiểm tra này, không tạo tài khoản và không ghi dữ liệu Supabase.

| Trường hợp kiểm tra qua trình duyệt | Kết quả |
| --- | --- |
| User mới chọn Fantasy & Paranormal | Gọi model thật, trả 12 sách từ catalog |
| Chọn Brave New World làm sách yêu thích | Gọi model thật, loại work của sách đầu vào |
| Lịch sử: đọc/5 sao, 1 sao và ẩn sách | Gọi model thật, loại cả ba work khỏi kết quả |
| Tắt hẳn model service | Vẫn trả 12 sách bằng heuristic và hiển thị trạng thái fallback |
| Khởi động lại model | Health trả `remote-demo`; giao diện tiếp tục dùng model |

Ba kịch bản dùng tín hiệu user mô phỏng trên trang `/demo`, đi qua recommendation
engine frontend, HTTP model API và API ánh xạ ID catalog thật. Đây không phải kiểm
thử đăng nhập hoặc lưu hồ sơ người dùng thật trên Supabase.

Browser check xác nhận ID khớp catalog, không trùng work trong kết quả model,
không xuất hiện các work bị loại, không có JavaScript page error; giao diện không
tràn ngang ở viewport 390px. Một số URL ảnh bìa gốc không tải được nên UI dùng
placeholder sẵn có. Việc này không ảnh hưởng ID hoặc thứ hạng gợi ý.

Đã sửa các lỗi phát hiện khi chạy: SQLite cursor context manager, lockfile npm
không đồng bộ, và việc frontend nối lại các sách/edition mà model đã loại.
Luồng đăng nhập chính vẫn được giữ; demo chỉ bật bằng `READORA_DEMO_MODE=1`.

Các kiểm tra: Python `15 passed, 2 skipped` trên Windows (hai test Spark), TypeScript,
ESLint cho các module tích hợp, production build và Playwright browser checks.
Báo cáo JSON/screenshot được lưu tại `logs/demo/browser-check.json`,
`logs/demo/fallback-check.json` và các file PNG cùng thư mục (không commit Git).

Mở http://127.0.0.1:3000/demo để kiểm tra. Có thể nhấp đúp `web/start.bat` để khởi động
cả ba dịch vụ và tự mở trình duyệt. Nếu cần điều khiển riêng, mở ba terminal
PowerShell ở repository root và chạy mỗi lệnh trong một terminal riêng:

```powershell
.\scripts\start-demo.ps1 -Service catalog
.\scripts\start-demo.ps1 -Service model
.\scripts\start-demo.ps1 -Service frontend
```

Giữ các terminal mở, dùng Ctrl+C để dừng từng service. Để thử fallback, dừng riêng
model và bấm lại **Lấy gợi ý**; sau đó chạy lại terminal model để phục hồi.
Hướng dẫn cài đặt và xử lý ExecutionPolicy nằm trong README ở repository root.
Chưa thực hiện bước đánh giá offline trên demo thật (`metrics.json`). Bản chia sẻ
được chuẩn bị trên nhánh `demo-ete`, kèm bundle serving trong `demo_assets/` để
checkout mới chạy được mà không cần train. Xem `python scripts/setup_demo.py --install`.

## Cập nhật ảnh bìa và bản chia sẻ — 2026-10-30

Đã pull sửa URL ảnh từ `main`, bổ sung đồng bộ cover URL vào SQLite mà không đổi
ID sách và xác nhận ảnh tải được trong trình duyệt: thể loại 11/12 bìa thật, sách
yêu thích 9/12, lịch sử 10/12. Các ảnh còn lại là placeholder `nophoto` của nguồn.
Các kiểm tra cover-refresh và bootstrap bundle đã được bổ sung cho bản chia sẻ.

## Launcher demo chung — 2026-11-01

`web/start.bat` gọi `scripts/launch-demo.ps1`, dùng lại `scripts/start-demo.ps1` cho
catalog/model/frontend. Launcher ưu tiên `.venv`, kiểm tra dependency/cổng trước khi
khởi động, đợi health/data rồi mở `/demo`. Ba cửa sổ giữ log và cho phép dừng riêng
bằng Ctrl+C. `start.bat` ở root cũng dùng cùng luồng. Cài lần đầu bằng Python 3.11–3.13:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe scripts\setup_demo.py --install
.\web\start.bat
```

`demo-ete` là nhánh chia sẻ bản demo, kèm bundle model và hướng dẫn chạy trong README.

Đã kiểm tra launcher trên Windows/Python 3.11/Node 24:

- Cả `web/start.bat` và `start.bat` ở root khởi động đủ ba service; `/demo` trả HTTP 200.
- Catalog trả 10.000 sách; health model trả `remote-demo`.
- Ba payload thể loại/sách yêu thích/lịch sử trả gợi ý thật, không trùng work và loại
  đúng các sách đầu vào/bị ẩn/1 sao. Đây là smoke test API; không chạy lại browser check.
- Chạy thêm launcher khi service đang hoạt động bị chặn ngay, không mở cửa sổ mới.
- Python 3.14 bị chặn với hướng dẫn tạo `.venv` bằng 3.11–3.13.
- Đã dừng các service thử nghiệm; cổng 8000/8001/3000 trống để chạy lại.

Setup runtime dùng wheel thường để tránh lỗi đường dẫn có dấu của editable install
trên Python 3.11/Windows; launcher vẫn ưu tiên mã trong `src/` của checkout hiện tại.

Kiểm tra trước phát hành ngày 2026-11-01: `19 passed, 1 skipped` (module integration
Spark được bỏ qua vì môi trường runtime không cài PySpark). Ruff, kiểm tra định dạng
Python, TypeScript, ESLint cho các module tích hợp và checksum bundle đều đạt.
