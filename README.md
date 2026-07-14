# PHÂN TÍCH DỮ LIỆU DU LỊCH VIỆT NAM TỪ HTML CÔNG KHAI

## Mục tiêu

Thu thập và phân tích nội dung HTML công khai từ VNTRIP và Vietnam.travel để nhận
diện điểm đến, chủ đề, mùa vụ và mức độ quan tâm trực tuyến. Lượt xem bài viết là
chỉ số quan tâm nội dung, không thay thế thống kê lượng khách du lịch thực tế.

Crawler chỉ lấy trang công khai khi `robots.txt` cho phép, không đăng nhập, không
vượt CAPTCHA và không thu thập dữ liệu cá nhân.

## Mục đích thực tiễn

Sản phẩm là công cụ theo dõi **nhu cầu nội dung du lịch trực tuyến**, giúp đội ngũ
marketing và kinh doanh chọn điểm đến, chủ đề và thời điểm ưu tiên. Sản phẩm không
dự báo trực tiếp số khách du lịch hoặc doanh thu.

| Người dùng | Câu hỏi cần trả lời | Kết quả sử dụng |
|---|---|---|
| Công ty lữ hành/OTA | Nên quảng bá tour hay điểm đến nào theo mùa? | Xếp hạng điểm cơ hội, lượt xem/ngày và xu hướng mùa vụ. |
| Khách sạn, resort | Khi nào nên chạy gói khuyến mãi hoặc hợp tác nội dung? | Theo dõi điểm đến có mức quan tâm và tốc độ tăng lượt xem cao. |
| Đội content/SEO | Nên viết chủ đề nào tiếp theo? | Nhận diện địa danh/chủ đề đang được quan tâm và nội dung cần mở rộng. |
| Cơ quan xúc tiến du lịch | Điểm đến nào cần ưu tiên truyền thông? | So sánh mức độ hiện diện và quan tâm trực tuyến giữa các điểm đến. |

Ví dụ: một điểm đến có lượt xem/ngày và số bài viết cao là tín hiệu để ưu tiên landing
page, bài SEO, quảng cáo hoặc gói sản phẩm theo mùa. Ngược lại, điểm đến có ít dữ
liệu cần được bổ sung nội dung và theo dõi thêm trước khi đầu tư ngân sách.

## Cấu trúc

```text
VNTRIP/crawl_vntrip.py                  # Crawl bài viết và snapshot lượt xem
VIETNAM_TRAVEL/crawl_vietnam_travel.py  # Crawl bài viết/điểm đến
analysis_pipeline.py                    # Làm sạch, gán nhãn, khử trùng, phân tích
dashboard.py                            # Sinh dashboard HTML tĩnh
run_all.sh                              # Crawl và phân tích toàn bộ
run_snapshot.sh                         # Cập nhật snapshot VNTRIP

data/
├── VNTRIP/rawdata.csv
├── VIETNAM_TRAVEL/rawdata.csv
└── analysis/                           # Các CSV kết quả tạo lại được

docs/index.html                         # Dashboard cho GitHub Pages
```

## Thiết lập

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Để chỉ phân tích dữ liệu HTML đã có, đặt trong `.env`:

```text
RUN_VNTRIP_CRAWLER=0
RUN_VIETNAM_TRAVEL_CRAWLER=0
```

Chạy toàn bộ luồng:

```bash
sh run_all.sh
```

## Kết quả phân tích

- `normalized_articles.csv`: nội dung HTML đã làm sạch, gán điểm đến/chủ đề.
- `duplicate_articles.csv`: bản ghi trùng URL hoặc nội dung bị loại.
- `label_review.csv`: nhãn tự động, từ khóa bằng chứng và trạng thái kiểm tra.
- `destination_season_stats.csv`: lượt xem/ngày theo điểm đến và mùa.
- `article_snapshot_trends.csv`: tốc độ tăng lượt xem giữa các lần crawl.
- `destination_opportunity_scores.csv`: điểm cơ hội từ 70% lượt xem/ngày và 30% số bài.

Để hiệu chỉnh nhãn thủ công, điền `validated_destination` hoặc
`validated_travel_theme` trong `data/analysis/label_overrides.csv`, sau đó chạy lại
pipeline.

## Cập nhật dữ liệu không trùng lặp

Hai crawler nhận diện bài đã parse bằng `source_url`. Mỗi lần chạy, `rawdata.csv`
được ghi lại từ tập dữ liệu đã hợp nhất, nên không sinh dòng URL trùng. VNTRIP cập
nhật metadata bài có sẵn; Vietnam.travel giữ bài cũ và chỉ tải trang chi tiết của URL
mới. `VNTRIP_MAX_NEW_ARTICLES` và `VIETNAM_TRAVEL_MAX_NEW_ARTICLES` là số bài
**mới** tối đa trong mỗi lần chạy. Tên cũ `*_MAX_ARTICLES` vẫn được đọc để không
làm hỏng cấu hình cũ, nhưng không nên dùng trong cấu hình mới.

Mỗi crawler cũng tạo `crawl_manifest.json`, ghi số trang đã đọc, URL phát hiện,
bài mới/bài cũ và lỗi. Pipeline tổng hợp các báo cáo đó vào
`data/analysis/run_metadata.json`; đây là cơ sở để quality gate phát hiện dữ liệu
quá cũ hoặc một nguồn crawl không thực sự hoàn tất.

## Dashboard HTML

Chạy:

```bash
.venv/bin/python dashboard.py
```

Trang kết quả được tạo tại `docs/index.html`. Bật GitHub Pages với nhánh `main` và
thư mục `/docs` để xem online tại:

`https://icegozi.github.io/icegozi_travel_analysis/`

Dashboard gồm danh sách việc cần làm ngay, biểu đồ điểm cơ hội, biểu đồ tăng trưởng
từ snapshot, heatmap mùa vụ và bộ lọc điểm đến. Toàn bộ giao diện dùng HTML, CSS và
JavaScript thuần; không cần server hoặc thư viện frontend.

Mục **Tải dữ liệu CSV** trên dashboard cho phép tải raw data, danh sách URL, snapshot
và các bảng kết quả phân tích. Các tệp được tạo trong `docs/data/` khi chạy
`dashboard.py`, vì vậy cần commit cả thư mục này khi xuất bản qua GitHub Pages.

## Snapshot định kỳ

Chạy `./run_snapshot.sh` để cập nhật lượt xem của bài VNTRIP. Mẫu lịch cron nằm ở
`cron/snapshot.cron.example`; với GitHub-only, dùng GitHub Actions theo lịch thay
cho cron máy chủ.

## Tự động chạy trên GitHub

Workflow `.github/workflows/update-dashboard.yml` kiểm tra lúc **02:00 giờ Việt
Nam/ICT (UTC+7)** mỗi ngày, nhưng chỉ crawl đúng **3 ngày một lần**. Workflow crawl
dữ liệu công khai, phân tích, sinh lại `docs/index.html` và tự commit dữ liệu/dashboard
mới để GitHub Pages cập nhật. Chạy thủ công từ tab Actions luôn thực hiện ngay, không
chờ chu kỳ.

Sau khi push workflow lần đầu, vào **Settings → Actions → General → Workflow
permissions** và chọn **Read and write permissions**. Có thể chạy thử ngay tại tab
**Actions**, chọn workflow “Cập nhật dữ liệu và dashboard du lịch”, sau đó bấm
**Run workflow**.

Khi chạy thủ công, chọn một trong ba chế độ: `full` (crawl cả hai nguồn),
`vntrip_only` (chỉ crawl VNTRIP) hoặc `dashboard_only` (phân tích và tạo lại
dashboard từ dữ liệu hiện có). Trước khi commit/publish, `quality_gate.py` kiểm tra
số bài tối thiểu, số bài theo nguồn, tỷ lệ nhãn cần rà soát, bảng điểm cơ hội, HTML
dashboard và manifest mới của từng nguồn. Nếu không đạt ngưỡng, workflow thất bại
và không publish dữ liệu mới.

Copyright (c) 2026 Icegozi.
