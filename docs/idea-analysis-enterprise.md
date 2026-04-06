1. Mức độ UI / UX Graph (Cải thiện trải nghiệm đồ thị)
Highlight chính xác Sub-graph gây ra cảnh báo: Hiện tại khi bấm Điều tra, hệ thống chỉ đang search tên entity (1 node). Bạn nên truyền thêm alertType để đồ thị tự động vẽ phần liên quan.
Ví dụ: Nếu cảnh báo là CIRCULAR_OWNERSHIP (sở hữu chéo), đồ thị nên tự fetch và hiển thị chính xác cụm 3-4 công ty tạo thành vòng tròn đó thay vì tải toàn bộ mạng lưới của công ty, đồng thời tô viền đỏ các mắt xích nguy hiểm.
Mở Side-drawer / Mini-graph: Thay vì nhảy hẳn sang tab graph làm mất danh sách cảnh báo đang xem, hãy mở một cửa sổ dạng slide-panel ở cạnh phải. Trong panel này hiện đồ thị nhỏ, thông tin chi tiết và lịch sử cảnh báo của công ty đó.
2. Mức độ AI & Tự động hóa (Tận dụng ai_api và LLM)
AI Investigation Report (Tính báo tự động): Ngay khi bấm Điều tra, kích hoạt một sub-agent hoặc GraphRAG chạy ngầm để lấy data từ Neo4j và gen ra một báo cáo tóm tắt 3-5 dòng.
Ví dụ: "Công ty X vừa đổi chủ sở hữu 3 lần trong năm nay. Chủ hiện tại liên quan đến công ty Y đang nằm trong danh sách đen của OpenSanctions."
Gợi ý câu hỏi (Chat vắn tắt): Đưa entity này thẳng vào khung Quick Chat ở góc màn hình, tạo sẵn các câu prompt (Prompt chips) như: "Tìm chủ sở hữu hưởng lợi cuối cùng (UBO)", "Tài sản bị đóng băng không?", "Những chi nhánh chung địa chỉ?" để người dùng hỏi AI ngay lập tức.
3. Mức độ Quản lý nghiệp vụ rủi ro (Case Management)
Cập nhật quy trình điều tra (Workflow): Đổi nút "Điều tra" thành tạo một Hồ sơ (Case). Analyst sẽ có các label để phân loại: New, Investigating (Đang điều tra), False Positive (Nhận diện nhầm), Confirmed Fraud (Xác nhận gian lận).
Lưu vết đồ thị (Snapshot): Cho phép người dùng chụp lại snapshot của đồ thị hiện tại kèm ghi chú ("Tôi phát hiện công ty ma ở nhánh này") và lưu lại vào thư mục hồ sơ báo cáo.
4. Mức độ Thuật toán Đồ thị (Neo4j GDS Analytics)
Phân tích Blast Radius (Tầm ảnh hưởng): Chạy thuật toán của Neo4j để xem nếu entity này bị cấm vận/vỡ nợ, thì có bao nhiêu công ty "sạch" xung quanh sẽ bị vấy bẩn theo (do góp vốn chung, nợ chéo, chung chuỗi cung ứng).
Find Shortest Path to Risk: Tự động gọi API vẽ "Đường đi ngắn nhất" từ Entity bị cảnh báo đến một node được xem là nguồn cơn nguy hiểm (ví dụ: một tổ chức dính án trừng phạt trong danh sách GLEIF / OpenSanctions).