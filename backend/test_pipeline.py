
import asyncio
import os
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.video_service_streaming_integrated import (
    process_temporary_video,
    subscribe_video_processing,
    unsubscribe_video_processing,
)

VIDEO_PATH = "test_video6.mp4"
SESSION_ID = "test-session-001"


def on_stream_event(payload, annotated_frame=None):
    event_type = payload.get("type")

    if event_type == "frame_result":
        print(
            f"[FRAME] frame={payload.get('frame_index')} | "
            f"progress={payload.get('progress_percent', 0):.2f}% | "
            f"fps={payload.get('processing_fps', 0):.2f} | "
            f"persons={len(payload.get('persons') or [])}"
        )
        for person in payload.get("persons") or []:
            print(
                f"    track={person.get('track_id')} | "
                f"pid={person.get('anonymous_code')} | "
                f"stage={person.get('display_stage')} | "
                f"bbox={person.get('bbox')}"
            )

    elif event_type == "pipeline_result":
        print("\n[PIPELINE COMPLETED]")
        print(f"status={payload.get('status')}")
        print(f"raw_track_count={payload.get('raw_track_count')}")
        print(f"faces_detected={payload.get('faces_detected')}")
        print(f"profile_track_ids={payload.get('profile_track_ids')}")

    elif event_type == "pipeline_error":
        print("\n[PIPELINE ERROR]")
        print(payload.get("error"))

    else:
        print(f"[EVENT] {event_type}: {payload}")


async def main():
    if not os.path.exists(VIDEO_PATH):
        raise FileNotFoundError(f"Không tìm thấy video: {VIDEO_PATH}")

    subscribe_video_processing(SESSION_ID, on_stream_event)

    try:
        with open(VIDEO_PATH, "rb") as file_handle:
            upload = UploadFile(
                filename=Path(VIDEO_PATH).name,
                file=file_handle,
                headers=Headers({"content-type": "video/mp4"}),
            )

            result = await process_temporary_video(
                file=upload,
                db=None,
                processing_session_id=SESSION_ID,
            )

            print("\n[API RESPONSE]")
            print(result.model_dump() if hasattr(result, "model_dump") else result)
    finally:
        unsubscribe_video_processing(SESSION_ID, on_stream_event)


if __name__ == "__main__":
    asyncio.run(main())