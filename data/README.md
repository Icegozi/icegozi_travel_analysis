# Quy ước dữ liệu

`VNTRIP/rawdata.csv` và `VIETNAM_TRAVEL/rawdata.csv` là dữ liệu gốc đã thu thập.
Không chỉnh sửa thủ công, đổi tên hoặc ghi đè các tệp này khi phân tích. Pipeline chỉ
đọc dữ liệu gốc và ghi kết quả có thể tái tạo vào `data/analysis/`.

Để phân tích hành vi đánh giá, tạo `data/reviews.csv` từ nguồn được phép sử dụng.
Tệp cần có: `review_id`, `destination`, `rating` (1–5), `review_text`. Có thể thêm
`review_date`, `platform`, `source_url`, `collected_at`. Dùng
`reviews.example.csv` làm mẫu; không thay thế dữ liệu thật bằng tệp mẫu.

Trước khi chạy `analysis_pipeline.py`, sao lưu hoặc commit dữ liệu đầu vào. Các tệp
kết quả trong `analysis/` và `docs/data/` được tạo lại mỗi lần chạy.
