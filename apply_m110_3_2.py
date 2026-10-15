from __future__ import annotations

from pathlib import Path
import shutil
import sys


YOUTUBE_PROFILE_BLOCK = '''            {
                "id": "youtube_data",
                "name": "YouTube Data API",
                "env_var": "YOUTUBE_API_KEY",
                "base_url": "https://www.googleapis.com/youtube/v3",
                "model": "",
                "enabled": True,
            },
'''

STORYBLOCKS_MARKER = '''            {
                "id": "storyblocks",
'''


def patch_api_key_manager(project_root: Path) -> str:
    target = project_root / "config" / "api_key_manager.py"
    if not target.is_file():
        raise FileNotFoundError(f"Không tìm thấy: {target}")

    text = target.read_text(encoding="utf-8")

    if '"id": "youtube_data"' in text:
        return "already_present"

    marker_index = text.find(STORYBLOCKS_MARKER)
    if marker_index < 0:
        raise RuntimeError(
            "Không tìm thấy mốc Storyblocks trong config/api_key_manager.py. "
            "Không sửa file để tránh làm hỏng phiên bản hiện tại."
        )

    backup = target.with_suffix(target.suffix + ".m110_3_2.bak")
    shutil.copy2(target, backup)

    patched = text[:marker_index] + YOUTUBE_PROFILE_BLOCK + text[marker_index:]
    target.write_text(patched, encoding="utf-8")
    return "patched"


def main() -> int:
    script_path = Path(__file__).resolve()
    project_root = script_path.parent

    # Support running either from project root or an extracted installer folder.
    if not (project_root / "config" / "api_key_manager.py").is_file():
        candidate = Path.cwd().resolve()
        if (candidate / "config" / "api_key_manager.py").is_file():
            project_root = candidate
        else:
            print("ERROR: Hãy chạy script này từ thư mục gốc AI_Video_Editor.")
            print(r'Ví dụ: cd "D:\YouTubeTools\AI_Video_Editor"')
            return 2

    try:
        result = patch_api_key_manager(project_root)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    if result == "already_present":
        print("M110.3.2: YouTube Data API profile đã tồn tại - không cần sửa lại.")
    else:
        print("M110.3.2: Đã thêm YouTube Data API profile vào APIKeyManager.")
        print("Backup: config/api_key_manager.py.m110_3_2.bak")

    print("Env var: YOUTUBE_API_KEY")
    print("Secret storage: Windows Credential Manager qua keyring hiện có")
    print("Không lưu API key vào JSON/project/automation manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
