from app.services.ai.video_pipeline_service import video_pipeline_service

from app.services.ai.streaming.streaming_result_publisher import StreamingResultPublisher
from app.services.ai.streaming.streaming_video_pipeline_service import StreamingVideoPipelineService


publisher = StreamingResultPublisher()

streaming_pipeline_service = StreamingVideoPipelineService(
    pipeline_service=video_pipeline_service,
    publisher=publisher,
    detection_sink=None,   # truyền DetectionRepositoryAdapter(...) khi đã có repository
    job_state_sink=None,   # truyền ProcessingJobRepositoryAdapter(...) khi đã có repository
)


def websocket_or_test_callback(payload, annotated_frame=None):
    print(payload["type"], payload.get("frame_index"), payload.get("progress_percent"))


job = streaming_pipeline_service.create_job(
    video_path="test_video6.mp4",
    session_id="session-demo-001",
)
publisher.subscribe(job.session_id, websocket_or_test_callback)

streaming_pipeline_service.start_job(
    job.job_id,
    background=False,
    output_face_dir="./pipeline_faces",
    target_fps=10.0,
    debug_video_path=None,
    stream_frame_dir=None,
    stream_emit_every_n_frames=1,
    stream_realtime_sleep=False,
    stream_send_annotated_frame=True,
)
