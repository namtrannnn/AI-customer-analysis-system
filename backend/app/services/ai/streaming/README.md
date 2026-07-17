# Streaming Pipeline Services

Đặt thư mục này vào:

`app/services/ai/streaming/`

## Mapping yêu cầu

- AI-01: `streaming_video_pipeline_service.py`
- AI-02: `frame_queue_service.py`
- AI-03: `pipeline_stage_service.py`
- AI-04: `multi_frame_face_matching_service.py`
- AI-05: `embedding_cache_service.py`
- AI-06: `streaming_result_publisher.py`

`streaming_video_pipeline_service.py` là adapter bao quanh `video_pipeline_service`
hiện tại. Nó không thay đổi thuật toán matching lõi.

## Event frame cho UI

```json
{
  "type": "frame_result",
  "session_id": "...",
  "job_id": "...",
  "frame_index": 120,
  "processed_frames": 121,
  "total_frames": 4489,
  "timestamp_seconds": 12.0,
  "progress_percent": 2.69,
  "processing_fps": 7.8,
  "persons": [
    {
      "detection_id": "...",
      "track_id": 12,
      "anonymous_code": "P_0004",
      "bbox": [100, 220, 280, 580],
      "display_stage": "CONFIRMED",
      "status": "CONFIRMED: P_0004",
      "operation": "upsert"
    }
  ]
}
```

## Event cuối

```json
{
  "type": "pipeline_result",
  "session_id": "...",
  "job_id": "...",
  "status": "COMPLETED",
  "progress_percent": 100.0,
  "merged_profiles": [],
  "track_to_profile": {},
  "profile_track_ids": {},
  "person_paths": {}
}
```

## WebSocket/SSE

WebSocket chỉ cần subscribe vào `StreamingResultPublisher`.
SSE có thể dùng:

```python
yield publisher.to_sse(payload)
```

## Lưu DB

Truyền callback `detection_sink` và `job_state_sink` vào
`StreamingVideoPipelineService`. Hai adapter mẫu nằm trong
`repository_adapters.py`.
