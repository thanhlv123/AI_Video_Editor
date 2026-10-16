M110.6 — Scene → Final Renderable Asset
========================================

Mục tiêu
--------
Chốt chính xác asset local/project cuối cùng cho từng scene trước khi bước nhạc/timeline/render bắt đầu.

Nguyên tắc
----------
- M107 scene assignment là selection pointer hiện hành.
- M106 Project Media Library là asset catalog.
- voice_scenes.json là timing authority cho scene.
- M110.4/M110.5 chỉ cung cấp quyết định chất lượng; không thay thế selection pointer.
- YouTube Reference luôn preview/reference-only và không bao giờ được promote thành render asset trong M110.6.
- Video phải có duration đủ bao phủ scene; nếu không, scene giữ unresolved.
- M110.6 không loop/speed một video quá ngắn để giả vờ đủ timing.

Artifact
--------
<project>/work/automation/run_.../final_renderable_assets.json

Mỗi scene ghi:
- timing
- assignment asset_id/media_type
- asset local project path + metadata
- final quality score/source
- render_eligible
- issues nếu unresolved

Workflow
--------
M110.4 keep_stock path -> M110.6
M110.5 research path -> M110.6
M110.6 all ready -> Bước 05/06 hoàn thành -> chờ M112 Music
M110.6 unresolved -> Bước 05/06 không được báo hoàn thành giả
