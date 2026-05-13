from clipwright.core.mediafile import CameraType, FileRole
from clipwright.core.scanner import _detect_from_filename


def test_detects_gopro_chaptered_video_name():
    camera, role, chapter, clip_id = _detect_from_filename("GX020123.MP4")

    assert camera == CameraType.GOPRO
    assert role == FileRole.VIDEO
    assert chapter == 2
    assert clip_id == "0123"


def test_detects_dji_proxy_name():
    camera, role, chapter, clip_id = _detect_from_filename("DJI_20250816174012_0001_D.LRF")

    assert camera == CameraType.DJI_ACTION4
    assert role == FileRole.LRV
    assert chapter == 1
    assert clip_id == "0001"


def test_unknown_video_uses_stem_as_clip_id():
    camera, role, chapter, clip_id = _detect_from_filename("family-edit.mov")

    assert camera == CameraType.UNKNOWN
    assert role == FileRole.VIDEO
    assert chapter == 1
    assert clip_id == "family-edit"
