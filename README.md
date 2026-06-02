# AWS SAM & GitHub Actions CI/CD Production-Grade Project

Dự án này triển khai cấu trúc thư mục tiêu chuẩn doanh nghiệp (Production-grade) dựa trên **AWS SAM (Serverless Application Model)**, tích hợp **Amazon DynamoDB**, và cấu hình **CI/CD tự động bằng GitHub Actions** hỗ trợ triển khai đa môi trường (Dev/Prod) theo nhánh Git.

---

## 📂 Cấu Trúc Thư Mục Chuẩn Production

```text
project-sam/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions CI/CD Workflow (Dev/Prod)
├── apigateway/                 # Quản lý API Gateway REST API (OpenAPI) & Lambda Permissions
│   ├── hello_world/
│   │   └── template.yaml       # Cấu hình API cho Hello World
│   └── items/
│       └── template.yaml       # Cấu hình API cho Items (Create/Delete)
├── dynamodb/                   # Quản lý DynamoDB Table
│   └── items/
│       └── template.yaml       # Cấu hình bảng ItemsTable
├── lambda/                     # Toàn bộ mã nguồn, cấu hình & layer liên quan tới Lambda
│   ├── hello_world/            # Module Hello World
│   │   ├── template.yaml       # Template cấu hình hàm Hello World
│   │   ├── app.py              # File code xử lý logic Hello World
│   │   └── requirements.txt
│   ├── items/                  # Module Items CRUD
│   │   ├── template.yaml       # Template cấu hình các hàm Items
│   │   ├── create/
│   │   │   ├── app.py          # Code xử lý tạo item
│   │   │   └── requirements.txt
│   │   └── delete/
│   │       ├── app.py          # Code xử lý xóa item
│   │       └── requirements.txt
│   ├── shared/                 # Định nghĩa Lambda Layer dùng chung
│   │   └── template.yaml
│   └── layers/                 # Thư mục chứa code của Lambda Layer dùng chung
│       └── shared_layer/
│           └── python/
│               └── shared_utils.py  # DynamoDB connection helper & Response formatter
├── events/                     # Chứa các mock events cho chạy thử local
│   ├── hello_event.json
│   ├── create_event.json       # Mock event gọi API POST thêm dữ liệu
│   └── delete_event.json       # Mock event gọi API DELETE xoá dữ liệu
├── template.yaml               # Template gốc (Root Stack) điều phối các nested stacks
├── samconfig.toml              # Cấu hình tham số deploy cho từng môi trường (Dev/Prod)
└── README.md
```

---

## 🛠️ Phát Triển Và Kiểm Thử Cục Bộ

### 1. Cài đặt môi trường
Đảm bảo bạn đã cài đặt Python 3.13+ và AWS SAM CLI.

### 2. Build ứng dụng bằng SAM
```bash
sam build
```

### 3. Kiểm thử Lambda cục bộ bằng Event mẫu
Bạn có thể giả lập chạy Lambda cục bộ trực tiếp trên máy của mình bằng cách truyền file event giả lập:
* **Test tạo dữ liệu:**
  ```bash
  sam local invoke CreateItemFunction -e events/create_event.json
  ```
* **Test xóa dữ liệu:**
  ```bash
  sam local invoke DeleteItemFunction -e events/delete_event.json
  ```

### 4. Chạy Local API Gateway
```bash
sam local start-api
```
Bây giờ, bạn có thể kiểm thử API bằng công cụ như Postman, cURL hoặc trình duyệt:
* **Hello World API (GET):** `http://127.0.0.1:3000/hello?name=Developer`
* **Create Item API (POST):**
  ```bash
  curl -X POST http://127.0.0.1:3000/items \
       -H "Content-Type: application/json" \
       -d '{"id": "item-102", "name": "Python Clean Code", "description": "Writing clean Python code"}'
  ```
* **Delete Item API (DELETE):**
  ```bash
  curl -X DELETE http://127.0.0.1:3000/items/item-102
  ```

---

## 🚀 Quy Trình Triển Khai Đa Môi Trường (Dev/Prod)

Chúng ta cấu hình deploy dựa trên nhánh Git:
- **Nhánh `dev`**: Tự động triển khai lên stack **`project-sam-dev`** (Môi trường Development).
- **Nhánh `main`**: Tự động triển khai lên stack **`project-sam-prod`** (Môi trường Production).

### Cấu hình Secrets trên GitHub:
Truy cập kho lưu trữ GitHub của bạn: **Settings > Secrets and variables > Actions > New repository secret**.

Khai báo các biến môi trường sau:
- `AWS_ACCESS_KEY_ID`: Access Key của AWS IAM User có quyền deploy.
- `AWS_SECRET_ACCESS_KEY`: Secret Access Key tương ứng.
- `AWS_REGION`: AWS Region mặc định (Ví dụ: `ap-southeast-1`).

### Cách thức hoạt động của CI/CD:
1. Khi bạn push code lên nhánh `dev`, GitHub Actions sẽ tự động chạy lệnh:
   ```bash
   sam deploy --config-env dev --region <region>
   ```
2. Khi bạn tạo Pull Request và merge vào nhánh `main`, pipeline sẽ tự động chạy:
   ```bash
   sam deploy --config-env prod --region <region>
   ```
3. SAM CLI sẽ tự động đóng gói mã nguồn, tải zip lên S3 bucket được tạo tự động thông qua tính năng `resolve_s3 = true` trong `samconfig.toml`, và triển khai/cập nhật tài nguyên bằng AWS CloudFormation.

---

## 🔍 Xác Minh Kết Quả Deploy Thực Tế (Trên Cloud)
Sau khi pipeline hoàn tất, CloudFormation sẽ xuất ra URL của các endpoint. Bạn có thể sử dụng cURL để gửi request lên môi trường AWS thực tế:
* **Tạo dữ liệu trên Cloud:**
  ```bash
  curl -X POST <CREATE_ITEM_API_URL> \
       -H "Content-Type: application/json" \
       -d '{"id": "real-item-99", "name": "AWS Serverless Book", "description": "Cloud native design patterns"}'
  ```
* **Xóa dữ liệu trên Cloud:**
  ```bash
  curl -X DELETE <DELETE_ITEM_API_URL_WITHOUT_ID>/real-item-99
  ```