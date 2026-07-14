# TIỂU LUẬN PHÂN TÍCH DỮ LIỆU DU LỊCH VIỆT NAM

## Nhóm thực hiện

- Hà Xuân Phúc
- Lại Thị Mai
- Hoàng Quốc Cường
- Đỗ Thị Thanh Huyền

## Mục tiêu

Phân tích mức độ quan tâm trực tuyến đối với các điểm đến du lịch Việt Nam theo
tháng, mùa và chủ đề du lịch. Kết quả được dùng để nhận diện điểm đến nổi bật theo
mùa, loại hình nội dung được quan tâm và gợi ý định hướng truyền thông.

> Lượt xem bài viết là chỉ số quan tâm trực tuyến; không thay thế số lượt khách du
> lịch thực tế.

## Nguồn dữ liệu

| Nguồn | Dữ liệu thu thập | Vai trò |
|---|---|---|
| VNTRIP | Bài viết, ngày đăng, lượt xem, mô tả, nội dung | Đo mức quan tâm theo lượt xem/ngày |
| Vietnam.travel | Bài viết và trang điểm đến công khai | Mở rộng danh mục điểm đến và chủ đề |

Mỗi crawler chỉ lấy HTML công khai khi `robots.txt` cho phép, không đăng nhập,
không vượt CAPTCHA và không thu thập dữ liệu cá nhân.

## Cấu trúc source code

```text
VNTRIP/
├── Export_Raw_Data.ipynb       # Crawl và xuất dữ liệu thô VNTRIP
├── Predict.ipynb               # Làm sạch, EDA và mô hình lượt xem
└── crawl_vntrip.py             # Crawler VNTRIP

VIETNAM_TRAVEL/
├── Export_Raw_Data.ipynb       # Crawl và xuất dữ liệu thô Vietnam.travel
└── crawl_vietnam_travel.py     # Crawler Vietnam.travel

KHAO_SAT/
└── PhanTich_KhaoSat.ipynb      # Phân tích rating, đánh giá và ý định quay lại

data/
├── VNTRIP/
│   ├── rawdata.csv             # Bài viết VNTRIP đã parse
│   ├── links_vntrip.csv        # URL bài viết
│   ├── article_snapshots.csv   # Lịch sử lượt xem theo ngày
│   ├── monthly_article_stats.csv
│   └── dataset.csv             # Dữ liệu đã làm sạch cho mô hình
├── VIETNAM_TRAVEL/
│   ├── rawdata.csv
│   └── links_vietnam_travel.csv
├── SURVEY/
│   └── tourist_survey.csv      # Mẫu hoặc dữ liệu xuất từ biểu mẫu khảo sát
└── analysis/
    ├── normalized_articles.csv
    └── destination_season_stats.csv

PhanTich_DiemDen.ipynb          # Phân tích đa nguồn theo điểm đến và mùa
TongHop_KetQua.ipynb             # Kết hợp xu hướng trực tuyến với kết quả khảo sát
```

## Quy trình thực hiện

1. Chạy `VNTRIP/Export_Raw_Data.ipynb` để thu thập bài viết VNTRIP.
2. Chạy `VIETNAM_TRAVEL/Export_Raw_Data.ipynb` để thu thập nội dung Vietnam.travel.
3. Chạy `PhanTich_DiemDen.ipynb` để chuẩn hóa dữ liệu, gán điểm đến/chủ đề và tạo
   thống kê mùa vụ.
4. Chạy `VNTRIP/Predict.ipynb` để làm sạch dữ liệu VNTRIP và thử nghiệm mô hình
   Linear Regression dự đoán lượt xem bài viết.
5. Nhập phản hồi khảo sát vào `data/SURVEY/tourist_survey.csv`, sau đó chạy
   `KHAO_SAT/PhanTich_KhaoSat.ipynb`.
6. Chạy `TongHop_KetQua.ipynb` để so sánh mức quan tâm trực tuyến với rating và ý
   định quay lại của du khách.

## Chỉ số phân tích

```text
views_per_day = view_count / max(1, số ngày từ ngày đăng đến ngày thu thập)
```

Quy ước mùa:

| Mùa | Tháng |
|---|---|
| Xuân | 1–3 |
| Hè | 4–6 |
| Thu | 7–9 |
| Đông | 10–12 |

`PhanTich_DiemDen.ipynb` xuất `destination_season_stats.csv`, gồm số bài, tổng lượt
xem và trung vị lượt xem/ngày cho từng điểm đến theo mùa.

## Kiểm soát chất lượng dữ liệu

`analysis_pipeline.py` làm sạch phần văn bản còn sót lại từ giao diện, loại các bài
trùng URL hoặc trùng nội dung trong cùng nguồn trước khi tạo bảng phân tích. Các tệp
kiểm tra được tạo trong `data/analysis/`:

- `duplicate_articles.csv` — các dòng bị loại và lý do.
- `label_review.csv` — nhãn điểm đến/chủ đề, từ khóa làm bằng chứng và trạng thái cần rà soát.
- `label_overrides.csv` — tệp để nhập nhãn đã kiểm tra thủ công; giữ cột `article_id` và điền
  `validated_destination` hoặc `validated_travel_theme`, sau đó chạy lại pipeline.
- `label_validation_summary.csv` — tổng số bài, số trùng bị loại và số nhãn cần rà soát.

## Khảo sát hành vi đánh giá

Để phân tích đúng phần “hành vi đánh giá” và “yếu tố ảnh hưởng”, nhóm thu thập phản
hồi qua biểu mẫu với các cột đã có trong `data/SURVEY/tourist_survey.csv`.

| Nhóm biến | Cột chính |
|---|---|
| Thông tin chuyến đi | `travel_date`, `destination`, `travel_theme`, `trip_purpose`, `budget_range` |
| Đánh giá 1–5 | `overall_rating`, `landscape_rating`, `service_rating`, `price_rating`, `food_rating`, `transport_rating`, `safety_rating`, `cleanliness_rating` |
| Hành vi sau chuyến đi | `revisit_intention`, `recommend_intention` |
| Nhận xét mở | `review_text` |

Notebook khảo sát tạo các đầu ra: `tourist_survey_clean.csv`,
`destination_rating_stats.csv` và `revisit_factor_coefficients.csv`. Mô hình Logistic
Regression chỉ chạy khi có tối thiểu 30 phản hồi hợp lệ và có đủ hai nhóm trả lời
“Có/Không” cho ý định quay lại.

## Môi trường chạy

Python 3.12 và các thư viện:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Trên Windows, kích hoạt môi trường bằng `.venv\\Scripts\\activate` rồi dùng
`pip install -r requirements.txt`. Chỉnh `.env` theo phạm vi crawl mong muốn; tệp
này chỉ dành cho máy cục bộ và không được đưa vào Git.

Nên chạy crawler với giới hạn mặc định và khoảng nghỉ giữa các request. Thu thập vài
trăm bài, đồng thời chạy lại ở nhiều thời điểm, sẽ giúp kết quả phân tích ổn định hơn.

## Chạy tự động

Chỉnh các tham số trong `.env`, sau đó chạy:

```bash
sh run_all.sh
```

Script lần lượt crawl VNTRIP, crawl Vietnam.travel và chạy `analysis_pipeline.py` để
tạo các bảng kết quả trong `data/analysis/`. Muốn chỉ chạy lại phân tích trên dữ liệu
đã có, đặt hai biến sau thành `0` trong `.env`:

```text
RUN_VNTRIP_CRAWLER=0
RUN_VIETNAM_TRAVEL_CRAWLER=0
```

| Biến cấu hình | Ý nghĩa |
|---|---|
| `VNTRIP_MAX_PAGES`, `VIETNAM_TRAVEL_MAX_PAGES` | Số trang danh mục tối đa cần duyệt |
| `VNTRIP_MAX_ARTICLES`, `VIETNAM_TRAVEL_MAX_ARTICLES` | Số nội dung tối đa cần lấy |
| `VNTRIP_DELAY_SECONDS`, `VIETNAM_TRAVEL_DELAY_SECONDS` | Khoảng nghỉ giữa các request |
| `HTTP_TIMEOUT_SECONDS` | Thời gian chờ một request HTTP |
| `RUN_SURVEY_ANALYSIS` | Bật/tắt phân tích phản hồi khảo sát |
| `RUN_COMBINED_ANALYSIS` | Bật/tắt bảng tổng hợp xu hướng và rating |

## Thiết lập Git

`.gitignore` loại trừ môi trường Python, cấu hình cục bộ, cache Jupyter và các báo
cáo phân tích có thể tái tạo. Dữ liệu nguồn cùng `data/analysis/label_overrides.csv`
vẫn có thể được quản lý phiên bản để lưu vết dữ liệu và hiệu chỉnh nhãn thủ công.

## Bản quyền

Copyright (c) 2026 Icegozi. All rights reserved. Xem [COPYRIGHT.md](COPYRIGHT.md).
