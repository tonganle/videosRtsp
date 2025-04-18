import subprocess
import os
import tempfile
import atexit


def start_rtsp_stream(concat_file, rtsp_url):
    command = [
        'ffmpeg',
        '-re',
        '-stream_loop', '-1',  # 无限循环整个文件列表
        '-f', 'concat',
        '-safe', '0',  # 允许非安全文件路径
        '-i', concat_file,
        '-c:v', 'copy',  # 复制视频流，无需重新编码
        '-c:a', 'copy',  # 复制音频流
        '-f', 'rtsp',
        '-rtsp_transport', 'tcp',  # 使用TCP传输
        rtsp_url
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    return process


def create_concat_file(file_list):
    # 创建临时列表文件，退出时自动删除
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as f:
        for file in file_list:
            f.write(f"file '{file}'\n")
        concat_filename = f.name
        atexit.register(os.unlink, concat_filename)  # 注册退出时删除
        return concat_filename


if __name__ == "__main__":
    video_dir = "C:\\Users\\Admin\\Desktop\\yolo-ai\\data\\videos"

    # 获取目录下所有MP4文件并排序
    file_list = sorted([
        os.path.join(video_dir, f)
        for f in os.listdir(video_dir)
        if f.endswith('.mp4')
    ])

    if not file_list:
        print("错误: videos目录下未找到MP4文件")
        exit(1)

    # 创建临时concat列表文件
    concat_file = create_concat_file(file_list)
    rtsp_url = "rtsp://localhost:8554/mystream"

    # 启动RTSP流
    process = start_rtsp_stream(concat_file, rtsp_url)
    print(f"RTSP流已启动，地址: {rtsp_url}")
    print("按 Ctrl+C 停止流媒体")

    try:
        # 实时输出错误信息
        while True:
            stderr_line = process.stderr.readline()
            if stderr_line:
                print(stderr_line.strip())
            if process.poll() is not None:
                break
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        print("\nRTSP流已停止")