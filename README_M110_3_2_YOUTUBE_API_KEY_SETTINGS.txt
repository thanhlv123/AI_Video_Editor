M110.3.2 - YouTube API Key Settings Integration
================================================

Mục tiêu
- Thêm YouTube Data API thành built-in provider trong APIKeyManager hiện có.
- Env var: YOUTUBE_API_KEY.
- API key được lưu bằng keyring/Windows Credential Manager giống KIE/Pexels/Pixabay.
- Không lưu secret vào api_providers.json, ProjectManifest, automation_run hoặc youtube_reference_manifest.
- Không thay đổi YouTube Reference search/ranking logic của M110.3.1.

Thiết kế
- Chỉ cần thêm profile mặc định youtube_data vào config/api_key_manager.py.
- _upgrade_config() hiện có sẽ tự thêm provider này vào api_providers.json cũ khi APIKeyManager khởi tạo.
- APIKeysDialog hiện có là generic và tự hiển thị mọi profile do APIKeyManager trả về.
- runtime_environment() hiện có sẽ tự xuất YOUTUBE_API_KEY khi provider bật và credential tồn tại.
- gui_creator_studio_m110_3_1.py hiện đã lấy runtime_environment() trước khi chạy YouTube Reference, vì vậy không cần sửa GUI production để truyền key.

Sau cài đặt
1. Mở Creator Studio.
2. Cài đặt -> Mở quản lý API.
3. Chọn "YouTube Data API".
4. Đảm bảo "Đã bật" được chọn.
5. Dán API key hợp lệ.
6. Nhấn "LƯU NHÀ CUNG CẤP".

Kiểm tra an toàn
- Xóa YOUTUBE_API_KEY khỏi process environment nếu muốn chứng minh Credential Manager hoạt động.
- APIKeyManager.runtime_environment() vẫn phải trả YOUTUBE_API_KEY.
- Không in API key ra console hoặc gửi key vào chat.
