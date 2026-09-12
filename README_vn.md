# ship

CLI triển khai tinh gọn, an toàn hoạt động theo mô hình Staging và Guardrails (tương tự Git) để đồng bộ tệp và thư mục lên máy chủ từ xa qua SSH và rsync.

---

## Tính năng nổi bật

- **Quy trình tương tự Git:** Các lệnh quen thuộc (`init`, `add`, `remove`, `status`, `push`).
- **Hệ thống Guardrails nhiều lớp:**
  - Phòng thủ chống tấn công Path Traversal và thoát khỏi thư mục gốc qua liên kết mềm (symlink).
  - Tự động chặn các tệp nhạy cảm (`.env`, `.git/`, `.ssh/`, `.ship/`, các private key).
  - Bảo vệ các thư mục hệ thống trên máy chủ đích (`/`, `/home`, `/root`, `/etc`, `/var`, `/usr`, `/bin`).
- **Quy tắc loại trừ:** Tệp `.shipignore` cấp dự án giúp bỏ qua thư viện phụ thuộc, bộ nhớ đệm, nhật ký log và sản phẩm build.
- **Kiểm tra trước & Dry-run:** Xem trước cấu trúc thư mục trên máy chủ từ xa và mô phỏng đồng bộ trước khi áp dụng thay đổi.
- **Không phụ thuộc thư viện ngoài:** Xây dựng hoàn toàn bằng thư viện chuẩn của Python, OpenSSH và rsync.

---

## Yêu cầu & Cài đặt

### Yêu cầu môi trường
- Python 3.10+
- OpenSSH client (`ssh`)
- rsync

### Cài đặt

#### Cách 1: Cài đặt từ PyPI (Khuyên dùng)
```bash
# Cài bằng pip
pip install ship-cli

# Hoặc cài bằng pipx (môi trường biệt lập cho các công cụ CLI)
pipx install ship-cli
```
Lệnh này sẽ tự động đăng ký file thực thi `ship` vào PATH của hệ thống.

#### Cách 2: Cài đặt trực tiếp từ Git
Cài đặt trực tiếp từ GitHub qua `pip` hoặc `pipx`:
```bash
# Cài bằng pip
pip install git+https://github.com/<username>/ship.git

# Hoặc cài bằng pipx
pipx install git+https://github.com/<username>/ship.git
```

#### Cách 3: Cài đặt từ mã nguồn tải về (Local Source)
Clone kho mã nguồn và cài đặt:
```bash
git clone https://github.com/<username>/ship.git
cd ship

# Cài đặt tiêu chuẩn
pip install .

# Hoặc chế độ phát triển (editable mode)
pip install -e .
```

#### Cách 4: Tạo Alias trong Shell
Thêm dòng sau vào tệp cấu hình shell của bạn (`~/.bashrc` hoặc `~/.zshrc`):
```bash
alias ship="python3 /đường_dẫn_tới/ship/main.py"
```
Tải lại cấu hình shell:
```bash
source ~/.bashrc  # hoặc source ~/.zshrc
```

#### Cách 5: Tạo liên kết mềm (Symlink) vào PATH
```bash
mkdir -p ~/.local/bin
ln -sf /đường_dẫn_tới/ship/main.py ~/.local/bin/ship
chmod +x /đường_dẫn_tới/ship/main.py
```

---

## Kiến trúc

Khi chạy `ship init` trong bất kỳ thư mục dự án nào, một không gian làm việc độc lập sẽ được khởi tạo:

```text
my-project/
├── .ship/
│   ├── config.env              # Cấu hình kết nối SSH (host, port, user, remote_dir)
│   ├── guardrails/
│   │   ├── allowed             # Biểu thức chính quy (regex) quy định thư mục remote hợp lệ
│   │   ├── deny                # Quy tắc chặn các tệp nhạy cảm không được phép triển khai
│   │   └── protected           # Các đường dẫn hệ thống trên remote được bảo vệ
│   └── state/
│       └── files               # Danh sách tệp/thư mục đang được stage sẵn sàng push
├── .shipignore                 # Quy tắc loại trừ tệp (tương tự .gitignore)
└── ...
```

---

## Hướng dẫn sử dụng nhanh

### 1. Khởi tạo không gian làm việc
Chạy `ship init` tại thư mục gốc của dự án:
```bash
ship init
```
Làm theo các bước tương tác để nhập thông tin máy chủ và thư mục đích. Để bỏ qua tương tác và tạo cấu hình mẫu mặc định, sử dụng `ship init --no-input`.

### 2. Kiểm tra môi trường & Kết nối
```bash
ship preflight
```
Kiểm tra các công cụ trên máy local (`ssh`, `rsync`, `python3`), tệp cấu hình và thử kết nối SSH.

### 3. Đưa tệp vào Staging
```bash
# Đưa toàn bộ dự án vào staging
ship add .

# Đưa các tệp hoặc thư mục cụ thể vào staging
ship add src/ public/ package.json
```

### 4. Kiểm tra trạng thái Staging
```bash
ship status
```
Hiển thị cây thư mục dự án và danh sách các tệp hiện đang được stage.

### 5. Xem trước cấu trúc trên máy chủ từ xa
```bash
# Xem cây thư mục trên remote (độ sâu mặc định: 2)
ship inspect

# Chỉ định độ sâu hiển thị
ship inspect 3
```

### 6. Đồng bộ lên máy chủ (Push)
```bash
# Chạy thử mô phỏng (Dry-run)
ship push -n

# Đồng bộ các tệp đã stage lên máy chủ từ xa
ship push

# Chế độ chi tiết hiển thị tiến độ truyền tệp
ship push -v
```

### 7. Bỏ tệp khỏi Staging hoặc Dọn dẹp
```bash
# Bỏ các đường dẫn cụ thể khỏi staging
ship remove src/temp.py

# Xoá toàn bộ danh sách staging
ship remove --all

# Dọn dẹp/Xoá thư mục đích trên remote (được bảo vệ)
ship clean -n   # Chạy thử mô phỏng
ship clean      # Xác nhận tương tác
ship clean -y   # Bỏ qua bước xác nhận
```

---

## Chế độ Dry-Run (Mô phỏng an toàn)

Cờ `-n` (hoặc `--dry-run`) cho phép bạn kiểm tra và chạy thử toàn bộ quy trình mà **hoàn toàn không ghi đè, tạo mới hay xoá bất kỳ tệp nào** trên máy chủ:

### 1. Mô phỏng quá trình Push (`ship push -n`)
- **Cơ chế hoạt động:** Hệ thống vẫn thực hiện đầy đủ quy trình kiểm tra an toàn (đối soát staging, kiểm tra `.shipignore`, rà soát `guardrails/deny`), sau đó truyền cờ `-n` vào lệnh `rsync` qua SSH.
- **Đảm bảo an toàn:** Không có thư mục nào được tạo mới trên server, không có byte dữ liệu nào bị ghi đè.
- **Xem trước danh sách tệp sẽ đồng bộ (`ship push -n -v`):** Kết hợp cờ `-n` với `-v` (verbose) để in ra danh sách chính xác từng tệp sẽ được tải lên máy chủ:
  ```bash
  ship push -n -v
  ```

### 2. Mô phỏng quá trình Clean (`ship clean -n`)
- **Cơ chế hoạt động:** Kiểm tra xem thư mục đích `REMOTE_DIR` có vượt qua các chốt chặn an toàn `allowed` và `protected` hay không, sau đó in ra thông báo xác nhận đường dẫn sẽ bị tác động mà không thực thi lệnh xoá (`rm -rf`).

---

## Bảng tra cứu lệnh

| Lệnh | Mô tả | Tùy chọn phổ biến |
| :--- | :--- | :--- |
| `ship init` | Khởi tạo không gian làm việc `.ship/` và `.shipignore` | `--no-input` |
| `ship preflight` | Kiểm tra công cụ môi trường và thử kết nối SSH | |
| `ship add <paths...>` | Đưa tệp/thư mục vào staging để chuẩn bị triển khai | |
| `ship remove <paths...>` | Bỏ đường dẫn khỏi danh sách staging | `--all` |
| `ship status` | Xem cấu trúc dự án và danh sách tệp đã stage | `-L <depth>` |
| `ship inspect [depth]` | Xem cây thư mục thực tế trên máy chủ từ xa | `depth` (mặc định: 2) |
| `ship push` | Đồng bộ các tệp đã stage lên máy chủ từ xa | `-n` (dry-run), `-v` (verbose) |
| `ship clean` | Xoá thư mục đích trên máy chủ từ xa | `-n` (dry-run), `-y` (yes) |

---

## Chính sách & Guardrails

- **`.shipignore`**: Bỏ qua các tệp tạm, sản phẩm build và thư viện phụ thuộc (`node_modules/`, `venv/`, `.cache/`).
- **`.ship/guardrails/allowed`**: Ràng buộc các thư mục đích `REMOTE_DIR` được phép triển khai (mặc định: `/home/<user>/<project>(/.*)?`).
- **`.ship/guardrails/deny`**: Chặn hoàn toàn việc stage hoặc push các bí mật/key (`.env`, `*.env`, `.ssh/`, `.git/`, `*.pem`, `id_rsa`).
- **`.ship/guardrails/protected`**: Ngăn chặn rủi ro chỉnh sửa hoặc xoá nhầm các thư mục hệ thống quan trọng (`/`, `/home`, `/root`, `/etc`, `/var`, `/usr`, `/bin`).

---

## Kiểm thử

Chạy bộ kiểm thử tự động:

```bash
# Kiểm thử đơn vị (Unit tests)
python3 -m unittest discover tests

# Kiểm thử bảo mật và hồi quy (Security test suite)
bash tests/test_security.sh
```
