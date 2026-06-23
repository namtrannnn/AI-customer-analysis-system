import os
import time
import shutil
from app.services.ai.video_pipeline_service import video_pipeline_service

def run_full_pipeline_test():
    video_path = "test_video2.mp4"
    if not os.path.exists(video_path):
        print(f"❌ Không tìm thấy video: {video_path}")
        return

    start_time = time.time()
    
    # 🚀 Chạy Pipeline và Yêu cầu xuất Video Debug
    pipeline_result = video_pipeline_service.process_video(
        video_path=video_path,
        output_face_dir="./pipeline_faces",
        target_fps=15.0, # Tốc độ quét FPS (chỉnh tùy cấu hình máy)
        debug_video_path="debug_final_pipeline.mp4" # Tên file video xuất ra
    )

    processing_time = time.time() - start_time
    merged_profiles = pipeline_result["merged_profiles"]

    # ==========================================
    # BÁO CÁO THỐNG KÊ QUA TỪNG MÀNG LỌC
    # ==========================================
    print("\n" + "="*60)
    print("📊 BÁO CÁO THỐNG KÊ HIỆU QUẢ PIPELINE (AI-01 -> AI-05) 📊")
    print("="*60)
    print(f"⏱️ Tổng thời gian chạy  : {processing_time:.2f} giây")
    print("-" * 60)
    print(f"1️⃣ TỔNG Track IDs sinh ra (Bao gồm ảo) : {pipeline_result['raw_track_count']} người")
    print(f"2️⃣ TỔNG số ảnh khuôn mặt cắt được     : {pipeline_result['faces_detected']} ảnh")
    print(f"3️⃣ Số ID vượt qua bộ lọc (Sạch rác)    : {pipeline_result['valid_tracklets']} Tracklets")
    print(f"4️⃣ 🚀 KHÁCH HÀNG THỰC TẾ (SAU KHI GỘP): {len(merged_profiles)} Khách hàng")
    print("="*60)

    # ==========================================
    # COPY ẢNH ĐẠI DIỆN CỦA PROFILE GỘP RA ĐỂ XEM
    # ==========================================
    best_faces_dir = "./final_merged_profiles"
    if os.path.exists(best_faces_dir):
        shutil.rmtree(best_faces_dir)
    os.makedirs(best_faces_dir, exist_ok=True)

    print(f"\n📂 Đang trích xuất hồ sơ khách hàng ra thư mục: {best_faces_dir}")
    for profile in merged_profiles:
        profile_id = profile["profile_id"]
        original_path = profile["best_face_image_path"]
        
        if original_path and os.path.exists(original_path):
            new_name = f"{profile_id}.jpg"
            new_path = os.path.join(best_faces_dir, new_name)
            shutil.copy(original_path, new_path)

        # In chi tiết từng khách hàng
        print(f"👤 [Hồ sơ: {profile_id}]")
        print(f"   ↳ Gộp từ các Track IDs : {profile['merged_track_ids']}")
        print(f"   ↳ Tổng số frame góp mặt: {profile['total_observations']} frames")
        print(f"   ↳ Độ sắc nét khuôn mặt : {profile['best_face_confidence']:.2f}")
        print("-" * 60)

    print(f"🎬 VIDEO DEBUG CHỨA BBOX VÀ ID ĐÃ LƯU TẠI: debug_final_pipeline.mp4")

if __name__ == "__main__":
    run_full_pipeline_test()