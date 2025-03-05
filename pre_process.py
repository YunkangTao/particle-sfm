import json
import cv2
import os
from tqdm import tqdm
def extract_and_save_frames(input_file, output_dir_5, output_dir_6):
    # 打开视频文件
    cap = cv2.VideoCapture(input_file)
    if not cap.isOpened():
        print(f"无法打开视频文件: {input_file}")
        return

    # 获取视频帧的宽度和高度
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"视频尺寸: {frame_width} x {frame_height}")

    # 每个小视频的尺寸
    crop_width = frame_width // 3
    crop_height = frame_height // 2

    # 定义裁剪区域：
    # 第5个视频区域：位于第二行、第二列
    # x 从 crop_width 开始, y 从 crop_height 开始
    x_offset_5 = crop_width
    y_offset_5 = crop_height

    # 第6个视频区域：位于第二行、第三列
    # x 从 2*crop_width 开始, y 从 crop_height 开始
    x_offset_6 = 2 * crop_width
    y_offset_6 = crop_height

    # 创建输出目录，如果不存在则创建
    os.makedirs(output_dir_5, exist_ok=True)
    os.makedirs(output_dir_6, exist_ok=True)

    frame_index = 0  # 用于命名输出帧
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 对每一帧进行裁剪对应区域
        # 注意：数组的切分格式为 frame[y1:y2, x1:x2]
        crop_frame_5 = frame[y_offset_5:y_offset_5 + crop_height, x_offset_5:x_offset_5 + crop_width]
        crop_frame_6 = frame[y_offset_6:y_offset_6 + crop_height, x_offset_6:x_offset_6 + crop_width]

        # 保存裁剪后的帧到对应目录
        output_path_5 = os.path.join(output_dir_5, f"frame_{frame_index:04d}.jpg")
        output_path_6 = os.path.join(output_dir_6, f"frame_{frame_index:04d}.jpg")
        cv2.imwrite(output_path_5, crop_frame_5)
        cv2.imwrite(output_path_6, crop_frame_6)

        frame_index += 1
        if frame_index % 100 == 0:
            print(f"已处理 {frame_index} 帧")

    cap.release()
    print("视频帧提取并保存完成！")

def find_all_vides(videos_path, metadata_path, video_numbers):
    all_data = json.load(open(metadata_path, 'r'))
    all_data = all_data[:video_numbers]
    all_data = [data['video_file_path'] for data in all_data] # "test_clips/s791KKzdyFs/20e7a3651ec30386.mp4"
    all_data = [os.path.join("results_checkpoint-8038", data) for data in all_data] # "results_checkpoint-8038/test_clips/s791KKzdyFs/20e7a3651ec30386.mp4"
    
    mp4_files = []

    for root, dirs, files in os.walk(videos_path):
        for file in files:
            if file.lower().endswith('.mp4'):
                mp4_file = os.path.join(root, file)
                print(mp4_file)
                if mp4_file in all_data:
                    mp4_files.append(os.path.join(root, file))

    print("videos numbers: ", len(mp4_files))
    return mp4_files


def main(videos_path, metadata_path, video_numbers):
    videos = find_all_vides(videos_path, metadata_path, video_numbers)
    for video in tqdm(videos, desc="Processing"):
        # input_file = "results_checkpoint-8038/test_clips/_cZ1oDQbgI4/0da6a36b24eaf5db.mp4"  # 输入视频文件
        # output_dir_5 = "results_checkpoint-8038/images_infered_easycamera/_cZ1oDQbgI4/0da6a36b24eaf5db/images"  # 存放第5个视频区域帧的目录
        output_dir_5 = video.replace("test_clips", "images_infered_easycamera").replace(".mp4", "/images")
        # output_dir_6 = "results_checkpoint-8038/images_ground_truth/_cZ1oDQbgI4/0da6a36b24eaf5db/images"  # 存放第6个视频区域帧的目录
        output_dir_6 = video.replace("test_clips", "images_ground_truth").replace(".mp4", "/images")
        extract_and_save_frames(video, output_dir_5, output_dir_6)

if __name__ == "__main__":
    metadata_path = "results_checkpoint-8038/metadata.json"
    videos_path = "results_checkpoint-8038/test_clips"
    video_numbers = 1000
    main(videos_path, metadata_path, video_numbers)