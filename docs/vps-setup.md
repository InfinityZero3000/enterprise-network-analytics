# Hướng Dẫn Cài Đặt Trên VPS

> **Stack:** PySpark · Apache Kafka · Neo4j · FastAPI · MLflow · Airflow · MinIO

---

## Yêu Cầu Phần Cứng

| Thành phần | Tối thiểu | Khuyến nghị |
|---|---|---|
| vCPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| Ổ cứng | 50 GB SSD | 100 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

> **Lý do cần RAM lớn:** Neo4j cần 6 GB (heap 4G + pagecache 2G), Spark Worker cần 4 GB, cộng thêm Kafka, API, MLflow...

---

## Bước 1 — Cài Đặt Docker Trên VPS

SSH vào VPS, sau đó chạy các lệnh sau:

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt Docker
curl -fsSL https://get.docker.com | sh

# Thêm user hiện tại vào group docker (không cần sudo mỗi lần)
sudo usermod -aG docker $USER
newgrp docker

# Cài Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Kiểm tra cài đặt thành công
docker --version
docker compose version
```

---

## Bước 2 — Clone Project

```bash
git clone https://github.com/InfinityZero3000/enterprise-network-analytics.git
cd enterprise-network-analytics
```

---

## Bước 3 — Tạo File `.env`

```bash
# Tạo file .env từ nội dung mẫu dưới đây
cat > .env << 'EOF'
# ── Neo4j ──────────────────────────────────────────
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=ena_password

# ── Kafka ──────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=kafka:29092

# ── MinIO (object storage) ─────────────────────────
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# ── MLflow ─────────────────────────────────────────
MLFLOW_TRACKING_URI=http://mlflow:5000

# ── LLM (tuỳ chọn, dùng nếu kích hoạt AI features) ─
OPENAI_API_KEY=sk-...
EOF
```

> **Lưu ý:** Đổi mật khẩu mặc định (`ena_password`, `minioadmin`) trước khi deploy thật.

---

## Bước 4 — Khởi Động Tất Cả Services

```bash
docker compose up -d
```

Kiểm tra trạng thái các container:

```bash
docker compose ps
```

Xem log realtime của FastAPI:

```bash
docker compose logs -f api
```

---

## Bước 5 — Truy Cập Các Services

| Service | URL | Thông tin đăng nhập |
|---|---|---|
| **FastAPI Docs** | `http://<VPS_IP>:8000/docs` | — |
| **Neo4j Browser** | `http://<VPS_IP>:7474` | neo4j / ena_password |
| **Kafka UI** | `http://<VPS_IP>:8080` | — |
| **Spark Master** | `http://<VPS_IP>:8082` | — |
| **MLflow** | `http://<VPS_IP>:5000` | — |
| **MinIO Console** | `http://<VPS_IP>:9001` | minioadmin / minioadmin |

Thay `<VPS_IP>` bằng IP thật của VPS (ví dụ: `103.27.xx.xx`).

---

## Bước 6 — Mở Port Firewall (UFW)

```bash
# Bật firewall
sudo ufw enable

# Cho phép SSH (quan trọng, không được bỏ qua)
sudo ufw allow 22/tcp

# Mở các port cần thiết
sudo ufw allow 8000/tcp   # FastAPI
sudo ufw allow 7474/tcp   # Neo4j Browser
sudo ufw allow 7687/tcp   # Neo4j Bolt
sudo ufw allow 8080/tcp   # Kafka UI
sudo ufw allow 8082/tcp   # Spark Master
sudo ufw allow 5000/tcp   # MLflow
sudo ufw allow 9001/tcp   # MinIO Console

# Kiểm tra
sudo ufw status
```

> **Bảo mật nâng cao:** Hạn chế mở port công khai, chỉ whitelist IP tin cậy hoặc dùng Nginx reverse proxy + SSL.

---

## Bước 6.1 — Cấu Hình CORS + API Gateway (Khuyến Nghị)

Backend đã hỗ trợ CORS qua biến môi trường trong `.env`:

```bash
# Chỉ cho phép UI từ Vercel và localhost dev
CORS_ALLOW_ORIGINS=https://your-ui.vercel.app,http://localhost:5173
CORS_ALLOW_CREDENTIALS=false
CORS_ALLOW_METHODS=*
CORS_ALLOW_HEADERS=*

# Nếu gateway mount API dưới prefix /api thì bật root path
# API_ROOT_PATH=/api
```

Áp dụng cấu hình mới:

```bash
docker compose up -d --build api
docker compose logs -f api --tail 100
```

Thiết lập Nginx gateway trên VPS:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp docs/nginx-api-gateway.conf /etc/nginx/sites-available/ena-api
sudo ln -sf /etc/nginx/sites-available/ena-api /etc/nginx/sites-enabled/ena-api
sudo nginx -t
sudo systemctl restart nginx
```

Sau đó cấp SSL:

```bash
sudo certbot --nginx -d api.example.com
```

> Lưu ý: cập nhật `server_name` trong file `docs/nginx-api-gateway.conf` trước khi copy sang `/etc/nginx`.

---

## Bước 7 — Chạy Pipeline Thủ Công (Tuỳ Chọn)

Nếu muốn chạy batch pipeline trực tiếp (không qua Airflow):

```bash
# Vào trong container API
docker compose exec api bash

# Chạy batch pipeline
python -c "from pipeline.batch_pipeline import BatchPipeline; print(BatchPipeline().run())"
```

---

## Phát Triển Code Trên VPS

### Option A — VS Code Remote SSH (Khuyến Nghị)

1. Cài extension **Remote - SSH** trên VS Code máy local
2. Nhấn `Ctrl+Shift+P` → **Remote-SSH: Connect to Host**
3. Nhập `user@<VPS_IP>`
4. Mở folder `/home/user/enterprise-network-analytics`
5. Code trực tiếp như trên máy local — mọi thay đổi tự động sync lên VPS

### Option B — Cài Python Environment Để Chạy Script

```bash
# Cài Python 3.11 và Java (cần cho PySpark)
sudo apt install -y python3.11 python3.11-venv openjdk-17-jdk

# Tạo virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Cài đặt dependencies
pip install -e ".[dev]"
```

---

## Các Lệnh Vận Hành Thường Dùng

```bash
# Xem mức sử dụng tài nguyên realtime
docker stats

# Restart một service cụ thể
docker compose restart neo4j
docker compose restart kafka

# Xem log của một service
docker compose logs -f neo4j --tail 100

# Dừng tất cả (giữ nguyên data)
docker compose stop

# Khởi động lại sau khi dừng
docker compose start

# Xoá toàn bộ container và data volumes (cẩn thận!)
docker compose down -v
```

---

## Xử Lý Sự Cố Thường Gặp

### Container khởi động không lên

```bash
# Xem log chi tiết của container lỗi
docker compose logs <tên_service>

# Ví dụ
docker compose logs neo4j
```

### Hết RAM — Services bị kill

```bash
# Kiểm tra memory
free -h

# Giảm heap Neo4j trong docker-compose.yml
# NEO4J_dbms_memory_heap_max__size: 2G  ← giảm từ 4G xuống 2G
# NEO4J_dbms_memory_pagecache_size: 1G  ← giảm từ 2G xuống 1G
```

### Spark Worker không kết nối được Master

```bash
# Kiểm tra network
docker network inspect enterprise-network-analytics_ena-net

# Restart cả cụm Spark
docker compose restart spark-master spark-worker
```

### Port bị chiếm

```bash
# Tìm process đang dùng port (ví dụ port 8080)
sudo lsof -i :8080
sudo kill -9 <PID>
```
