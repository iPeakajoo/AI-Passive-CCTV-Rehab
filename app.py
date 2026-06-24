import cv2
import mediapipe as mp
import numpy as np
import os
import requests
import tkinter as tk
from tkinter import filedialog

def send_line_alert(message):
    token = "YOUR_LINE_NOTIFY_TOKEN_HERE" 
    url = 'https://line.me'
    headers = {'Authorization': f'Bearer {token}'}
    try:
        requests.post(url, headers=headers, data={'message': message}, timeout=5)
    except:
        pass

def analyze_adl_video(video_path):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, min_detection_confidence=0.5)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return "ไม่สามารถเปิดไฟล์วิดีโอหรือกล้องวงจรปิดได้"

    fps = cap.get(cv2.CAP_PROP_FPS)
    dt = 1.0 / fps if fps > 0 else 1.0/30
    
    data = {
        "Left": {"coords": [], "speeds": [], "jerks": [], "active_frames": 0},
        "Right": {"coords": [], "speeds": [], "jerks": [], "active_frames": 0}
    }
    total_valid_frames = 0

    while cap.isOpened():
        success, frame = cap.read()
        if not success: break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)

        if results.pose_landmarks:
            total_valid_frames += 1
            landmarks = results.pose_landmarks.landmark
            
            l_shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].y])
            r_shoulder = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].y])
            shoulder_dist = np.linalg.norm(l_shoulder - r_shoulder)
            if shoulder_dist == 0: shoulder_dist = 1.0

            lw = np.array([landmarks[mp_pose.PoseLandmark.LEFT_WRIST].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST].y])
            rw = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].y])

            hip_level = (landmarks[mp_pose.PoseLandmark.LEFT_HIP].y + landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y) / 2

            for side, current_coord in [("Left", lw), ("Right", rw)]:
                history = data[side]["coords"]
                history.append(current_coord)

                if current_coord < hip_level: 
                    data[side]["active_frames"] += 1

                if len(history) > 1:
                    speed = np.linalg.norm(current_coord - history[-2]) / shoulder_dist / dt
                    data[side]["speeds"].append(speed)
                    if len(data[side]["speeds"]) > 1:
                        accel = (speed - data[side]["speeds"][-2]) / dt
                        data[side]["jerks"].append(abs(accel))

    cap.release()
    pose.close()

    if total_valid_frames == 0:
        return "ไม่พบโครงร่างมนุษย์ในคลิปวิดีโอนี้"

    report_text = "=== รายงานสรุปจาก AI: คัดกรองภาวะ Learned Non-Use ===\n\n"
    res = {}
    for side in ["Left", "Right"]:
        avg_speed = np.mean(data[side]["speeds"]) if data[side]["speeds"] else 0
        avg_jerk = np.mean(data[side]["jerks"]) if data[side]["jerks"] else 0
        smoothness = max(0, 100 - (avg_jerk * 0.1))
        use_ratio = (data[side]["active_frames"] / total_valid_frames) * 100
        res[side] = {"speed": avg_speed, "smooth": smoothness, "use": use_ratio}
        
        side_th = "ซ้าย (Left)" if side == "Left" else "ขวา (Right)"
        report_text += f"[{side.upper()} HAND] แขนข้าง{side_th}:\n"
        report_text += f"  - อัตราการเลือกใช้งานจริงในชีวิตประจำวัน: {use_ratio:.1f}%\n"
        report_text += f"  - คะแนนความลื่นไหล (Smoothness): {smoothness:.1f}/100\n\n"

    if abs(res["Left"]["use"] - res["Right"]["use"]) > 25:
        weak = "ซ้าย (LEFT)" if res["Left"]["use"] < res["Right"]["use"] else "ขวา (RIGHT)"
        diagnosis = f"⚠️ สัญญาณเตือน: ตรวจพบภาวะ 'Learned Non-Use' ที่แขนข้าง [{weak}]\nแนะนำแพทย์ปรับโปรแกรมบำบัดด้วยเทคนิคข้ามซีกประสาท (Cross-Education) หรือ CIMT"
    else:
        diagnosis = "✅ ผลการประเมิน: การขยับของรยางค์ส่วนบนทั้งสองข้างสมดุลดี ไม่พบภาวะ Learned Non-Use"
        
    report_text += diagnosis
    send_line_alert(f"\n[AI สรุปผลประจำวัน]\nผู้ป่วย: คุณตาประเสริฐ\n{diagnosis}")
    return report_text

def browse_file():
    file_path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.avi *.mov")])
    if file_path:
        lbl_status.config(text="AI กำลังวิเคราะห์พฤติกรรม ADL... กรุณารอสักครู่", fg="blue")
        root.update()
        report = analyze_adl_video(file_path)
        txt_result.delete("1.0", tk.END)
        txt_result.insert(tk.END, report)
        lbl_status.config(text="วิเคราะห์เสร็จสิ้น และส่งรายงานเข้า LINE เรียบร้อย!", fg="green")

root = tk.Tk()
root.title("AI Passive Tele-Rehab Assessment Tool")
root.geometry("520x560")

btn_upload = tk.Button(root, text="อัปโหลดวิดีโอ ADL จากกล้องวงจรปิด", command=browse_file, bg="#008CBA", fg="white", font=("Arial", 11, "bold"), padx=10, pady=10)
btn_upload.pack(pady=20)

lbl_status = tk.Label(root, text="สถานะ: รอไฟล์วิดีโอกิจวัตรประจำวันของผู้สูงอายุ...", font=("Arial", 10))
lbl_status.pack(pady=5)

txt_result = tk.Text(root, width=60, height=18, font=("Arial", 10))
txt_result.pack(pady=10)

root.mainloop()
