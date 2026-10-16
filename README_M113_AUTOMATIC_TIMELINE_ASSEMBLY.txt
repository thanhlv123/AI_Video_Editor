M113 - AUTOMATIC TIMELINE ASSEMBLY
===================================

Mục tiêu
--------
Tự động tạo timeline render-neutral sau M112, sử dụng voice_scenes.json làm timing authority.
M113 KHÔNG render/transcode video và KHÔNG thay đổi audio narration.

Đầu vào
-------
- voice_scenes.json
- Voice Asset local trong project
- final_renderable_assets.json (M110.6)
- music_selection_manifest.json (M112; selected hoặc skipped)

Đầu ra
------
<project>/work/automation/run_.../timeline_manifest.json

Nguyên tắc
----------
- Voice timing là authority.
- Mỗi scene dùng đúng final renderable asset đã chốt ở M110.6.
- Video scene: trim từ đầu source theo đúng scene duration; không loop, không đổi speed.
- Image scene: giữ ảnh đúng scene duration.
- Khoảng trống giữa các voice scene được lấp bằng freeze-frame của asset liền kề để timeline có coverage liên tục.
- Narration không time-stretch.
- YouTube Reference không bao giờ trở thành render asset.
- Chỉ tham chiếu file local nằm trong project.
- Nhạc nền lấy đúng quyết định M112: trim hoặc loop chỉ ở music track, narration/scene video không bị kéo tốc độ.
- M113 không render; M114 sẽ đọc timeline_manifest.json để FFmpeg render/export.

File production
---------------
creator_studio/timeline_assembly.py
creator_studio/automation_runner.py
gui_creator_studio_m113.py

Tests
-----
tests/test_timeline_assembly_m113.py
tests/test_automation_runner_m113.py
tests/test_gui_m113_timeline_assembly.py

Regression package đã chạy:
- M110.6 + M112 + M113
- Ran 39 tests
- OK

Manual acceptance
-----------------
1. Chạy gui_creator_studio_m113.py.
2. Bấm TẠO VIDEO trên project có Voice Asset + media + music (hoặc music skipped).
3. Sau M112, M113 phải tự chạy không cần bấm thêm.
4. Bước 08 "Dựng video" phải chuyển thành Hoàn thành.
5. Bước 09 "Xuất video" phải ở Đang chờ.
6. timeline_manifest.json phải tồn tại.
7. summary.unresolved_count = 0.
8. duration_seconds bằng mốc end lớn nhất của voice_scenes.json.
9. Mỗi scene clip có start/end đúng voice timing và asset local hợp lệ.
10. Scene video không loop và không speed_change.
