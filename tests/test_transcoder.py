from clipwright.core.transcoder import AudioCodec, Container, TranscodeSettings, VideoCodec


def test_h264_transcode_args_include_crf_and_audio_bitrate():
    settings = TranscodeSettings(
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        container=Container.MP4,
        crf=20,
        audio_bitrate="256k",
    )

    args = settings.build_ffmpeg_args()

    assert ["-c:v", "libx264"] == args[0:2]
    assert "-crf" in args
    assert "20" in args
    assert ["-c:a", "aac"] == args[-4:-2]
    assert ["-b:a", "256k"] == args[-2:]


def test_copy_video_and_strip_audio_args():
    settings = TranscodeSettings(
        video_codec=VideoCodec.COPY,
        audio_codec=AudioCodec.NONE,
        container=Container.MOV,
    )

    assert settings.build_ffmpeg_args() == ["-c:v", "copy", "-an"]


def test_resolution_adds_scale_filter():
    settings = TranscodeSettings(resolution=(1920, 1080))

    args = settings.build_ffmpeg_args()

    assert "-vf" in args
    assert "scale=1920:1080" in args[args.index("-vf") + 1]
