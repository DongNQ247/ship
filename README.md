# 🚢 ship — Git-like File Deployment CLI

CLI tinh gọn hoạt động theo cơ chế **Staging & Guardrails** (tương tự mô hình làm việc của Git) để đồng bộ và triển khai file/folder từ máy local lên remote server thông qua SSH và `rsync`.

---

## ✨ Điểm nổi bật (Features)

- 🔄 **Quy trình Git-like quen thuộc:** `init` ➔ `add` ➔ `status` ➔ `push`.
- 🛡️ **Hệ thống Guardrails bảo mật nhiều lớp:**
  - Chống tấn công Path Traversal (`../`, symlink trỏ ra ngoài project root, absolute path escape).
  - Tự động chặn các file bí mật, nhạy cảm (`.env`, `*.env`, `.ssh/`, `*.pem`, `id_rsa`, `.ship/`, `.git/`).
  - Bảo vệ thư mục hệ thống trên remote (`/`, `/home`, `/root`, `/etc*`, `/var*`, `/usr*`, `/bin*`,...).
- 🚫 **Hỗ trợ `.shipignore`:** Bỏ qua dependencies (`node_modules/`, `venv/`), cache, build artifacts, logs.
- 🔍 **Xem trước & Dry-run:** Cho phép `ship inspect` kiểm tra remote và `ship push --dry-run` mô phỏng trước khi push thực tế.
- ⚡ **Zero External Python Dependencies:** Sử dụng 100% Python standard library, kết hợp các công cụ chuẩn Linux (`ssh`, `rsync`).

---

## 📦 Cài đặt & Thiết lập (Setup)

### Yêu cầu môi trường
- **Python 3.10+**
- **OpenSSH client** (`ssh`) & **rsync**

### Cách 1: Tạo Alias trong Shell (Khuyên dùng)
Thêm dòng sau vào file cấu hình shell (`~/.bashrc` hoặc `~/.zshrc`):

```bash
alias ship="python3 /đường_dẫn_tới/ship/main.py"
```

Sau đó tải lại cấu hình:
```bash
source ~/.bashrc   # hoặc source ~/.zshrc
```

### Cách 2: Tạo Symlink vào PATH
```bash
mkdir -p ~/.local/bin
ln -sf /đường_dẫn_tới/ship/main.py ~/.local/bin/ship
chmod +x /đường_dẫn_tới/ship/main.py
```

---

## 💡 Mô hình hoạt động (Architecture)

Khi đứng ở bất kỳ thư mục dự án nào, chạy `ship init` sẽ tạo môi trường quản lý độc lập:

```text
my-project/
├── .ship/                      # Thư mục quản lý cấu hình & trạng thái (như .git/)
│   ├── config.env              # Thông tin kết nối SSH (host, user, port, remote_dir)
│   ├── guardrails/             # Các chính sách an toàn
│   │   ├── allowed             # Regex quy định đường dẫn REMOTE_DIR hợp lệ
│   │   ├── deny                # Pattern chặn tuyệt đối các file nhạy cảm
│   │   └── protected           # Pattern bảo vệ thư mục hệ thống trên server
│   └── state/
│       └── files               # Staging manifest (danh sách file/thư mục chuẩn bị push)
├── .shipignore                 # Quy tắc loại trừ (tương tự .gitignore)
└── ...
```

---

## 🚀 Hướng dẫn sử dụng từng bước (Quickstart)

### Bước 1: Khởi tạo dự án
Đứng tại thư mục dự án cần deploy:
```bash
ship init
```
*Hệ thống sẽ hỏi thông tin kết nối máy chủ (Host/IP, SSH Port, SSH User, Remote Directory) và tự động tạo `.ship/` cùng `.shipignore`.*

*(Nếu muốn khởi tạo tự động không qua prompt, dùng `ship init --no-input`)*.

---

### Bước 2: Kiểm tra kết nối trước khi deploy
```bash
ship preflight
```
*Lệnh này kiểm tra các công cụ trên máy local (`ssh`, `rsync`, `python3`), kiểm tra cấu hình và thử kết nối SSH tới server.*

---

### Bước 3: Thêm file vào Staging
```bash
# Thêm toàn bộ dự án hiện tại
ship add .

# Hoặc chỉ định từng file / thư mục cụ thể
ship add src/ public/ package.json
```
*`ship` sẽ tự động kiểm tra đối soát với `.shipignore` và các chính sách bảo mật trong `guardrails/deny`.*

---

### Bước 4: Kiểm tra trạng thái Staging
```bash
ship status
```
*Hiển thị cây thư mục dự án cùng danh sách chi tiết các file đã được staged sẵn sàng push.*

---

### Bước 5: Bỏ file khỏi Staging (nếu cần)
```bash
# Bỏ một hoặc nhiều file cụ thể
ship remove src/temp.py

# Xoá toàn bộ danh sách staging
ship remove --all
```

---

### Bước 6: Kiểm tra thư mục trên Remote Server
```bash
# Xem cây thư mục trên server (mặc định độ sâu 2)
ship inspect

# Xem với độ sâu tùy chỉnh (ví dụ: depth = 3)
ship inspect 3
```

---

### Bước 7: Đồng bộ lên Remote Server (Push)
```bash
# Chạy thử (Dry-run) để xem trước file nào sẽ được tải lên mà không thay đổi server
ship push -n

# Đồng bộ thực tế (rsync qua SSH)
ship push

# Đồng bộ kèm log chi tiết và tiến độ (Verbose)
ship push -v
```

---

### Bước 8: Dọn dẹp Remote Server (Clean)
```bash
# Chạy thử dry-run
ship clean -n

# Xóa thư mục REMOTE_DIR trên server (có cảnh báo xác nhận)
ship clean

# Xóa trực tiếp không cần xác nhận
ship clean -y
```

---

## 📋 Bảng tổng hợp các lệnh (Command Reference)

> *Bạn có thể chạy lệnh `ship <command>` ở bất kỳ thư mục con nào bên trong dự án.*

| Lệnh | Mô tả | Tuỳ chọn phổ biến |
| :--- | :--- | :--- |
| `ship init` | Khởi tạo môi trường `.ship/` và `.shipignore` | `--no-input` |
| `ship preflight` | Kiểm tra công cụ môi trường & kết nối SSH | |
| `ship add <paths...>` | Thêm file/thư mục vào staging manifest | |
| `ship remove <paths...>` | Bỏ file/thư mục khỏi staging manifest | `--all` |
| `ship status` | Xem cây thư mục và danh sách file đã stage | `-L <depth>` |
| `ship inspect [depth]` | Xem trước cấu trúc cây thư mục trên remote | `depth` (mặc định 2) |
| `ship push` | Đồng bộ file đã staged lên remote qua SSH/rsync | `-n` (dry-run), `-v` (verbose) |
| `ship clean` | Xoá thư mục đích trên server (được bảo vệ) | `-n` (dry-run), `-y` (skip confirm) |

---

## 🛡️ Cơ chế an toàn (Guardrails & Policies)

1. **`.shipignore`**:
   - Loại trừ file tạm, logs, build outputs (`dist/`, `build/`), môi trường ảo (`.venv/`, `node_modules/`).
2. **`.ship/guardrails/allowed`**:
   - Regex quy định các đường dẫn thư mục `REMOTE_DIR` được phép triển khai (mặc định dạng `/home/<user>/<project>(/.*)?`).
3. **`.ship/guardrails/deny`**:
   - Chặn tuyệt đối không cho phép stage hay push các file nhạy cảm (`.env`, `*.env`, `.ssh/`, `.git/`, `*.pem`, `id_rsa`,...).
4. **`.ship/guardrails/protected`**:
   - Ngăn chặn triệt để nguy cơ phá hoại các thư mục hệ thống (`/`, `/home`, `/root`, `/etc*`, `/var*`, `/usr*`, `/bin*`,...).

---

## 🧪 Kiểm thử (Testing)

Dự án đi kèm bộ kiểm thử tự động toàn diện:

```bash
# 1. Chạy Unit Tests
python3 -m unittest discover tests

# 2. Chạy Security & Regression Test Suite (54 kịch bản phòng vệ an ninh)
bash tests/test_security.sh
```
