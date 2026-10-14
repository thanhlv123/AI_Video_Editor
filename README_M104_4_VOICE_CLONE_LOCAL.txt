M104.4 - VOICESTUDIO LOCAL VOICE CLONE
=======================================

Mục tiêu
--------
M104.4 mở rộng TTS provider framework để voice cloning cũng đi qua TTSService.
GUI không gọi trực tiếp VoiceStudio provider.

Luồng:
AI Video Editor GUI
  -> TTSService.clone_voice(...)
  -> VoiceStudioLocalProvider.clone_voice(...)
  -> POST http://127.0.0.1:3900/profiles
  -> VoiceStudio lưu voice profile cục bộ
  -> AI Video Editor làm mới danh sách voice
  -> tự chọn profile vừa tạo

Không dùng quota API cloud.

File mới / cập nhật
-------------------
- gui_creator_studio_m104_4.py
- creator_studio/tts/models.py
- creator_studio/tts/provider.py
- creator_studio/tts/service.py
- creator_studio/tts/__init__.py
- creator_studio/tts/providers/voicestudio_provider.py
- tests/test_tts_voice_clone_service.py
- tests/test_voicestudio_local_provider.py

Bảo vệ quyền sử dụng giọng
--------------------------
Nút Tạo giọng clone chỉ được bật khi người dùng xác nhận mình sở hữu giọng
hoặc đã được người sở hữu cho phép clone và sử dụng.

Audio mẫu
---------
GUI chấp nhận:
WAV, MP3, M4A, FLAC, OGG, OGA, OPUS, AAC, WEBM.
Khuyến nghị VoiceStudio/OmniVoice: một người nói, âm thanh sạch, khoảng 3-10 giây.
Transcript là tùy chọn. Nếu để trống, VoiceStudio 0.5.6 có thể dùng ASR local đã
cài để tự nhận dạng khi lưu profile. Nếu không có ASR, nhập transcript khớp
chính xác với audio mẫu.

Test
----
python -m unittest tests.test_voicestudio_local_provider tests.test_tts_voice_clone_service -v

Kết quả ở gói phát hành M104.4: 6 tests PASS.

Sau khi clone
-------------
Giọng mới được lưu trong VoiceStudio, không ghi audio mẫu vào ProjectManifest.
Khi user chọn giọng clone và tạo narration, ProjectManifest sẽ lưu provider
voicestudio_local + profile id trong voice.voice_id giống mọi TTS voice khác.

Lưu ý engine
------------
Voice profile clone cần một TTS engine hỗ trợ cloning. OmniVoice là lựa chọn
phù hợp để test trước. Nếu active engine không hỗ trợ reference voice,
VoiceStudio có thể từ chối generation dù profile vẫn được tạo thành công.
