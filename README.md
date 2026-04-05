# Enterprise Network Analytics (Hệ Thống Phân Tích Mạng Lưới Doanh Nghiệp)

**Enterprise Network Analytics** là một nền tảng chuyên sâu (Intelligence Console) được thiết kế nhằm cung cấp cái nhìn toàn cảnh về dữ liệu doanh nghiệp, bóc tách các mối quan hệ sở hữu phức tạp và phát hiện điểm nóng rủi ro theo thời gian thực. Hệ thống giúp phơi bày các mạng lưới ngầm, công ty "vỏ bọc" (shell companies) và các hành vi gian lận tài chính tinh vi bằng cách tận dụng sức mạnh của Lý thuyết Đồ thị (Graph Theory) kết hợp với Trí tuệ Nhân tạo (Gen AI).

---

## 1. Tổng Quan Hệ Thống

Hệ thống hoạt động dựa trên một Data Pipeline khép kín, đi từ việc thu thập dữ liệu thô đến việc truy vấn AI thông minh:

- **Data Ingestion (Thu thập):** Dữ liệu được crawl hoặc đẩy vào qua hệ thống Kafka từ các nguồn như OpenCorporates, OpenOwnership, OpenSanctions, v.v.
- **Processing (Xử lý ETL):** Apache Spark đóng vai trò làm sạch, chuẩn hóa và chuyển đổi dữ liệu thành các dạng thực thể (Entity) và liên kết (Relationship).
- **Graph Layer (Mạng lưới):** Dữ liệu được nạp vào cơ sở dữ liệu Neo4j để mô hình hóa toàn bộ dưới dạng Đồ thị Toán học.
- **Analytics (Phân tích):** Graph Data Science (GDS) và hệ thống Rule Engine quét qua toàn bộ đồ thị để tìm ra các bất thường, chấm điểm rủi ro.
- **AI & UI (Tương tác):** Người dùng tương tác trực tiếp qua giao diện React trực quan, hoặc yêu cầu Trợ lý AI (Tích hợp LLM như Gemini, GPT, Llama) trực tiếp phân tích các cụm đồ thị.

---

## 2. Các Chức Năng Cốt Lõi

### Trực quan hóa Mạng lưới Đồ thị (Graph Explorer)
- Khám phá các mối quan hệ chồng chéo của doanh nghiệp, cá nhân dưới hình thức đồ thị lưới.
- Auto-layout bằng mô phỏng lực vật lý (Force-directed graph) có thể dang rộng để phân tách các điểm siêu kết nối (Super-nodes / Hubs).
- Tính toán trực tiếp số bậc (Degree) và chọn lọc để theo dõi những mắt xích quan trọng nhất.

### Phân tích Sở hữu & Truy vết UBO (Ultimate Beneficial Owner)
- **Truy vết sở hữu chéo:** Bóc tách các công ty con do cùng một cá nhân hoặc nhóm cá nhân kiểm soát.
- **Tìm kiếm UBO:** Đi ngược chuỗi sở hữu (ownership chain) qua nhiều tầng lớp để xác định chủ sở hữu hưởng lợi cuối cùng.

### Phát hiện Gian lận & Cảnh báo Rủi ro (Fraud Detection)
Hệ thống Rule Engine rà soát liên tục để phát hiện:
- **Chuỗi Sở hữu Vòng tròn (Circular Ownership):** Công ty A sở hữu B, B sở hữu C, và C sở hữu ngược lại A nhằm che giấu dòng tiền.
- **Công ty "Vỏ bọc" (Shell Companies):** Hàng chục hoặc hàng trăm công ty không có hoạt động kinh doanh thực tế nhưng dùng chung quy mô một địa chỉ văn phòng ảo (Ví dụ: Mass Registration tại các thiên đường thuế).
- **Thực thể Siêu kết nối:** Điểm trung chuyển bất thường sở hữu số lượng lớn doanh nghiệp.

### GraphRAG & Trợ lý ảo AI
- Giải thích ngữ cảnh dữ liệu bằng ngôn ngữ tự nhiên: AI sẽ đọc trực tiếp cụm đồ thị xuất hiện trên màn hình và phân tích rủi ro dựa trên cấu trúc đó.
- Giao tiếp mượt mà: Người dùng có thể yêu cầu AI "Đánh giá mức độ rủi ro của công ty X dựa trên các mắt xích xung quanh".

---

## 3. Cơ Sở Lý Thuyết & Thuật Toán

Nền tảng được xây dựng vững chắc trên các học thuyết về Mạng lưới phức hợp (Complex Networks):

- **Đồ thị có hướng (Directed Graphs):** Dùng để biểu diễn dòng chảy sở hữu (Ai sở hữu ai, bao nhiêu phần trăm cổ phần).
- **PageRank / Centrality:** Thuật toán đánh giá tầm quan trọng của thực thể. Một cá nhân không trực tiếp làm CEO nhưng sở hữu nhiều công ty lớn, hoặc nằm ở ngã tư của nhiều liên kết, sẽ có điểm Centrality rất cao.
- **Weakly Connected Components (WCC):** Tìm các "hòn đảo" công ty độc lập hoặc các liên minh ngầm không liên kết rõ ràng ra bên ngoài mạng lưới.
- **Thuật toán Path Finding:** Tìm đường đi ngắn nhất (Shortest Path) giữa hai thực thể bất kỳ để điều tra xem có liên hệ lợi ích nhóm hay không.

