import os
import cv2
import shutil
from typing import List, Dict, Optional
from dataclasses import dataclass

# Import các service AI lõi
from app.services.ai.frame_extractor_service import FrameExtractorService
from app.services.ai.tracking_service import tracker_service  # AI-09 (Tracking)
from app.services.ai.face_detection_service import FaceDetectionService, PersonDetectionInput  # AI-03
from app.services.ai.face_embedding_service import FaceEmbeddingService, face_embedder, FaceEmbeddingResult  # AI-04


@dataclass
class ProcessedCustomer:
    """
    Data Transfer Object (DTO) chứa toàn bộ thông tin về 1 khách hàng 
    sau khi đã đi qua toàn bộ Pipeline.
    """
    track_id: int
    observation_count: int
    best_face_image_path: Optional[str]
    embedding: Optional[List[float]]
    face_confidence: Optional[float]


class VideoProcessingPipelineService:
    """
    AI-06 Video Processing Pipeline (Full Flow)
    
    Luồng xử lý:
    1. AI-01: Trích xuất Frame từ Video.
    2. AI-09: Tracking người (Gán ID cố định xuyên suốt frame).
    3. AI-03: Cắt mặt từ tất cả các lần xuất hiện của người đó.
    4. Best Face Selection: Chọn ra 1 tấm mặt đẹp nhất/to nhất cho mỗi ID.
    5. AI-04: Trích xuất Vector (Embedding) từ tấm ảnh đẹp nhất đó.
    """

    def __init__(self, yunet_model_path: str = None, arcface_model_path: str = None):
        self.frame_extractor = FrameExtractorService()
        self.tracker = tracker_service
        self.face_embedder = FaceEmbeddingService(
            model_path=arcface_model_path,
            model_name="arcface",
            input_size=(112, 112) # Ép chuẩn kích thước của ArcFace
        )

        # Khởi tạo AI-03 với cấu hình đã test thành công
        # Bạn thay đường dẫn tuyệt đối vào đây nếu cần thiết
        self.face_detector = FaceDetectionService(
            yunet_model_path=yunet_model_path,
            yunet_score_threshold=0.6
        )

    def process_video(
        self, 
        video_path: str, 
        output_face_dir: str = "./pipeline_faces",
        target_fps: float = 1.0
    ) -> List[ProcessedCustomer]:
        
        # 0. Setup thư mục lưu ảnh khuôn mặt (Xóa cũ tạo mới)
        if os.path.exists(output_face_dir):
            shutil.rmtree(output_face_dir)
        os.makedirs(output_face_dir, exist_ok=True)

        print("\n" + "="*50)
        print("KHỞI ĐỘNG AI PIPELINE (AI-01 -> AI-04)")
        print("="*50)

        # 1. BƯỚC 1: TRÍCH XUẤT FRAME (AI-01)
        print("[AI-01] Đang trích xuất frames từ video...")
        with self.frame_extractor.create_temp_frame_dir() as frame_dir:
            frame_result = self.frame_extractor.extract_frames(
                video_path, frame_dir, target_fps=target_fps
            )

            person_inputs = []
            track_observation_counts = {}

            # 2. BƯỚC 2: TRACKING NGƯỜI DÙNG BYTE-TRACK (AI-09)
            print(f"[AI-02/09] Đang quét Tracking trên {frame_result.extracted_count} frames...")
            for frame_data in frame_result.frames:
                image = cv2.imread(frame_data.image_path)
                if image is None:
                    continue

                tracked_persons = self.tracker.track_persons_in_frame(
                    frame=image,
                    frame_index=frame_data.frame_index,
                    img_path=frame_data.image_path
                )

                for p in tracked_persons:
                    track_id = p["track_id"]
                    # Đếm số frame người này xuất hiện
                    track_observation_counts[track_id] = track_observation_counts.get(track_id, 0) + 1

                    # Nạp dữ liệu vào hàng đợi cho AI-03
                    person_inputs.append(
                        PersonDetectionInput(
                            frame_index=p["frame_index"],
                            image_path=p["img_path"],
                            person_index=track_id, # Dùng track_id làm nhân dạng xuyên suốt
                            bbox=p["bbox"],
                            confidence=p.get("confidence")
                        )
                    )

            # 3. BƯỚC 3: CẮT KHUÔN MẶT BẰNG YUNET (AI-03)
            print(f"[AI-03] Đang phân tích khuôn mặt từ {len(person_inputs)} vùng cơ thể...")
            face_result = self.face_detector.detect_faces_from_person_detections(
                person_detections=person_inputs,
                output_dir=output_face_dir,
                max_faces_per_person=1,
                min_quality_score=0.0 # Để mở hoàn toàn bộ lọc
            )

            # 4. BƯỚC 4: BEST FACE SELECTION (Lọc lấy ảnh đẹp nhất cho mỗi người)
            print(f"[Pipeline] Đang tuyển chọn khuôn mặt tốt nhất (Best Face Selection)...")
            faces_by_track_id = {}
            for face in face_result.faces:
                t_id = face.person_index
                if t_id not in faces_by_track_id:
                    faces_by_track_id[t_id] = []
                faces_by_track_id[t_id].append(face)

            best_faces = []
            for t_id, faces in faces_by_track_id.items():
                # Tiêu chí: Diện tích ảnh (độ to/rõ) nhân với điểm tự tin
                def score_face(f):
                    area = f.width * f.height
                    conf = f.confidence if f.confidence else 0.5
                    return area * conf

                # Sắp xếp và lấy "Hoa hậu" đứng đầu
                best_face = sorted(faces, key=score_face, reverse=True)[0]
                best_faces.append(best_face)

            # 5. BƯỚC 5: TRÍCH XUẤT VECTOR (AI-04)
            print(f"[AI-04] Đang trích xuất Vector cho {len(best_faces)} khuôn mặt duy nhất...")
            embedding_results = self.face_embedder.extract_embeddings_from_detected_faces(best_faces)

            # Map vector vào track_id tương ứng
            embedding_dict = {res.person_index: res.embedding for res in embedding_results}

            # 6. ĐÓNG GÓI KẾT QUẢ TRẢ VỀ
            final_customers = []
            MIN_FRAMES_OBSERVED = 5  # Lọc rác chớp nháy
            MIN_FACE_CONFIDENCE = 0.7 # BỘ LỌC CHỐNG ẢO GIÁC ÁO/SÀN NHÀ
            
            for track_id, count in track_observation_counts.items():
                if count < MIN_FRAMES_OBSERVED:
                    continue
                    
                b_face = next((f for f in best_faces if f.person_index == track_id), None)

                if b_face is None:
                    continue

                # LOẠI BỎ KHÁCH HÀNG KHÔNG CÓ MẶT RÕ RÀNG
                # Nếu "mặt tốt nhất" mà điểm vẫn dưới 0.7, chứng tỏ khách này 
                # luôn quay lưng hoặc AI bắt nhầm nếp nhăn áo. Ta không lấy Vector của họ!
                if b_face.confidence < MIN_FACE_CONFIDENCE:
                    continue

                final_customers.append(ProcessedCustomer(
                    track_id=track_id,
                    observation_count=count,
                    best_face_image_path=b_face.face_image_path,
                    embedding=embedding_dict.get(track_id),
                    face_confidence=b_face.confidence
                ))

            print("XỬ LÝ HOÀN TẤT!")
            return final_customers

# 1. Lấy đường dẫn tuyệt đối của THƯ MỤC đang chứa file hiện tại (video_pipeline_service.py)
# Dù chạy trên máy ai, nó cũng sẽ tự tìm ra đúng thư mục đó.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Từ thư mục hiện tại, đi vào thư mục con "models" và chỉ định tên file ONNX
YUNET_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "face_detection_yunet_2023mar.onnx")
ARCFACE_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "arcface.onnx")

# (Tùy chọn) Thêm một chút log để kiểm tra file có thật sự nằm ở đó không khi khởi động
if not os.path.exists(YUNET_MODEL_PATH):
    print(f"CẢNH BÁO: Không tìm thấy file YuNet tại {YUNET_MODEL_PATH}")
if not os.path.exists(ARCFACE_MODEL_PATH):
    print(f"CẢNH BÁO: Không tìm thấy file ArcFace tại {ARCFACE_MODEL_PATH}")

# 3. Khởi tạo Service với đường dẫn đã được tính toán tự động
video_pipeline_service = VideoProcessingPipelineService(
    yunet_model_path=YUNET_MODEL_PATH,
    arcface_model_path=ARCFACE_MODEL_PATH
)