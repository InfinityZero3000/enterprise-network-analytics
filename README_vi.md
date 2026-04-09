# Phân tích Mạng lưới Doanh nghiệp (Enterprise Network Analytics)

## Tổng quan Hệ thống

Phân tích Mạng lưới Doanh nghiệp là một nền tảng phân tích và trực quan hóa nâng cao, chuyên vẽ bản đồ và phân tích các mạng lưới quan hệ phức tạp giữa các thực thể kinh tế, bao gồm các tập đoàn, cá nhân, địa chỉ, và tài sản.

Mục tiêu cốt lõi của hệ thống là gỡ rối các cấu trúc doanh nghiệp phức tạp, mạng lưới sở hữu chéo và các công ty bình phong (shell entities). Thông qua việc ứng dụng Khoa học Dữ liệu Đồ thị (Graph Data Science) và Trí tuệ Nhân tạo Tạo sinh (GenAI), nền tảng cho phép phát hiện các rủi ro tiềm ẩn, hành vi gian lận và các vi phạm tuân thủ trong các tập dữ liệu doanh nghiệp quy mô lớn.

---

## Các tính năng cốt lõi

### 1. Khám phá và Trực quan hóa Đồ thị
* **Render tương tác:** Lên bản đồ hiệu suất cao cho hàng ngàn node và edge, phản ánh theo thời gian thực những thay đổi về mặt topo mạng lưới và dữ liệu.
* **Tương tác Vật lý (Layout Physics):** Thao tác động với lực đẩy vật lý và các ràng buộc liên kết để thu phóng các cụm dữ liệu siêu kết nối, đảm bảo tầm nhìn phân tích tối ưu.
* **Tập trung & Lọc:** Cắt tỉa (pruning) node dựa trên bậc kết nối và chức năng tìm kiếm tức thời để điều tra các điểm nóng cục bộ trong mạng lưới.

### 2. Phát hiện Rủi ro & Gian lận
* **Rule Engine:** Các thuật toán quét mạng lưới liên tục được thiết kế để theo dấu các chỉ báo vi phạm cổ điển, bao gồm:
  * Đăng ký hàng loạt và tập trung hộp thư ảo (Virtual Mailbox).
  * Kiến trúc vòng lặp sở hữu chéo.
  * Giám đốc bù nhìn (Super-connected Proxies) đóng vai trò bình phong hoạt động.
* **Ưu tiên Rủi ro:** Phân loại hệ thống các mức độ rủi ro (Thấp, Trung bình, Cao, Nghiêm trọng) để tinh gọn và ưu tiên luồng công việc điều tra tuân thủ.

### 3. Phân tích Cấu trúc Sở hữu
* Tính toán thuật toán và truy xuất Người Thực thi Hưởng lợi Cuối cùng (Ultimate Beneficial Owners - UBO), mổ xẻ các hệ thống phân cấp sở hữu nhiều lớp, xuyên biên giới.

### 4. Trợ lý AI Doanh nghiệp
* Tích hợp giao diện Xử lý Ngôn ngữ Tự nhiên (NLP), cho phép người dùng truy vấn và chất vấn trực tiếp với mạng lưới dữ liệu.
* Hỗ trợ các nền tảng LLM hàng đầu (Gemini, Llama/Groq, OpenAI) được cấu hình để biên dịch các tương tác đồ thị toán học thành các tóm tắt thông tin tình báo doanh nghiệp sát với thực tế nhất.

---

## Lý thuyết và Thuật toán áp dụng

Hệ thống được thiết kế dựa trên các nguyên lý học thuật nền tảng của Khoa học Mạng lưới (Network Science) và Phân tích Dữ liệu hiện đại:

### 1. Khoa học Dữ liệu Đồ thị (Graph Data Science - GDS)
Nền tảng sử dụng các engine tính toán đồ thị chuyên dụng để thực thi các hoạt động phân tích vượt xa khả năng của Hệ thống Quản trị Cơ sở Dữ liệu Quan hệ (RDBMS) truyền thống:
* **Thuật toán Trung tâm (PageRank & Degree Centrality):** Đánh giá mức độ tập trung ảnh hưởng hoặc dòng vốn. Điểm trung tâm cao chỉ ra các "Hub" điều phối các luồng tài chính hoặc thông tin trong mạng lưới vĩ mô.
* **Các thành phần liên thông yếu (Weakly Connected Components - WCC):** Định danh các mạng con tách biệt bên trong đồ thị vĩ mô - rất quan trọng để khám phá các tập đoàn kinh tế ngầm có vẻ độc lập trên mặt chức năng nhưng liên kết cấu trúc thông qua các node ủy quyền (proxy).
* **Tìm đường (Path Finding):** Triển khai khám phá đường đi ngắn nhất để vạch trần các cấu trúc liên kết tinh vi, được che giấu giữa các thực thể mục tiêu.

### 2. GraphRAG (Retrieval-Augmented Generation trên Đồ thị)
Khác biệt với kiến trúc RAG Vector truyền thống, hệ thống này triển khai **GraphRAG**:
* AI engine sử dụng ngữ cảnh ngữ nghĩa để tạo các truy vấn đồ thị cấu trúc (ví dụ: cú pháp Cypher), trích xuất động các đồ thị con (sub-graphs) topo chính xác.
* Bằng cách phân tích các node chính xác và chuỗi quan hệ từ cơ sở dữ liệu đồ thị, hệ thống giảm thiểu triệt để hiện tượng ảo giác AI (hallucination), mang lại thông tin tình báo xác định.

### 3. Mô hình Chấm điểm Rủi ro
Được chuẩn hóa theo các phương pháp đánh giá rủi ro Chống Rửa Tiền (AML) và Biết Khách Hàng (KYC) hiện đại:
* **Seed Risk (Rủi ro nguồn khởi):** Xác định các thực thể gốc đối chiếu với danh sách đen quốc tế, cơ sở dữ liệu Cá nhân có Liên quan Chính trị (PEP), và sổ đăng ký trừng phạt.
* **Lan truyền rủi ro (Risk Propagation):** Điểm rủi ro lan truyền và phân rã một cách có hệ thống khi theo dấu các node con trong kiến trúc liên kết. Ví dụ: một công ty con có liên kết với một công ty mẹ bị trừng phạt sẽ kế thừa toán học các rủi ro lây nhiễm đó.

---

## Công nghệ sử dụng (Technology Stack)

Nền tảng được xây dựng dựa trên kiến trúc kỹ thuật dữ liệu và machine learning hiện đại, có khả năng mở rộng cao:

### 1. Kỹ thuật Dữ liệu & Lưu trữ
* **Cơ sở dữ liệu Đồ thị:** Neo4j (Logic Enterprise Graph Data Science)
* **Xử lý Dữ liệu Lớn:** Apache Spark (PySpark) & Delta Lake
* **Streaming & Messaging:** Apache Kafka (Hệ sinh thái Confluent)
* **Lưu trữ Đối tượng:** MinIO (Kho dữ liệu Data lake tương thích S3)
* **Điều phối (Orchestration):** Apache Airflow

### 2. Backend & Trí tuệ Nhân tạo
* **API Framework:** FastAPI (Python 3.11+, Kiến trúc bất đồng bộ)
* **Theo dõi mô hình:** MLflow
* **AI Tạo sinh (GenAI):** Tích hợp sâu (Native integration) với OpenAI, Google Gemini, và Groq LLMs qua giải pháp GraphRAG tùy chỉnh.

### 3. Frontend & Trực quan hóa
* **Core Framework:** React 18, TypeScript, Vite
* **Render Đồ thị:** D3.js thông qua `react-force-graph-2d` (Engine đồ thị WebGL/Canvas xử lý tăng tốc bằng GPU)
* **Styling:** CSS hiện đại (Tailwind và các thuộc tính tùy chỉnh)

---

## Hướng dẫn Khởi chạy (Getting Started)

Toàn bộ hệ sinh thái ứng dụng đã được container hóa để triển khai trên các môi trường phân lập.

### Yêu cầu cấu hình (Prerequisites)
* Docker Engine & Docker Compose (v2+)
* Node.js + npm (để chạy Web UI development server)
* Yêu cầu hệ điều hành tối thiểu: Linux/macOS hoặc Windows (WSL2), khuyến nghị RAM 8GB+.

### Các bước cài đặt nhanh (Quick Start)

**1. Clone kho mã nguồn về máy lưu trữ cục bộ:**
```bash
git clone https://github.com/InfinityZero3000/enterprise-network-analytics.git
cd enterprise-network-analytics
```

**2. Khởi chạy toàn bộ hệ thống bằng 1 lệnh:**
```bash
bash scripts/start.sh
```

Script khởi động hiện đã hỗ trợ cho người mới:
* Kiểm tra dependency bắt buộc (`docker`, `npm`)
* Kiểm tra Docker daemon đang chạy
* Tự tạo `.env` từ `.env.example` nếu chưa có
* Tự cài package UI trong `ui/` nếu chưa có `node_modules`
* Tự chạy Docker services và Web UI dev server

**3. Kiểm tra trạng thái dịch vụ (tuỳ chọn):**
```bash
docker compose ps
tail -f ui/ui.log
```

**4. Cấu hình API key AI (tuỳ chọn):**
Nếu cần dùng Trợ lý AI, mở `.env` và điền key (Gemini/Groq/OpenAI).

### Hướng dẫn lấy API key AI (chi tiết)

Bạn chỉ cần dùng tối thiểu 1 nhà cung cấp dưới đây.

**1. Tạo API key**
* Gemini: https://aistudio.google.com/app/apikey
* Groq: https://console.groq.com/keys
* OpenAI: https://platform.openai.com/api-keys
* OpenRouter (tuỳ chọn): https://openrouter.ai/keys

**2. Điền key vào file `.env`**
```bash
# Điền ít nhất một key
GEMINI_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=

# Tuỳ chọn model
GEMINI_MODEL=gemini-2.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_MODEL=gpt-4o
OPENROUTER_MODEL=openai/gpt-4o-mini
```

**3. Nạp lại backend sau khi cập nhật key**
```bash
docker compose restart api
```

**4. Test nhanh endpoint AI**
```bash
curl -X POST http://localhost:8000/api/v1/ai/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Liệt kê 3 công ty có liên kết cao nhất"}'
```

Nếu response trả về `answer` khác rỗng thì tích hợp AI đang hoạt động.

### Truy cập các dịch vụ
Sau khi toàn bộ dịch vụ được triển khai, bạn có thể tương tác với các URL dưới đây:
* **Web UI (Khám phá đồ thị):** `http://localhost:5173`
* **API Backend (FastAPI Swagger Docs):** `http://localhost:8000/docs`
* **Neo4j Browser:** `http://localhost:7474`
* **Kafka UI:** `http://localhost:8080`

### Dừng toàn bộ dịch vụ
```bash
bash scripts/stop.sh
```