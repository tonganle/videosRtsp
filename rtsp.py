import subprocess
import os
import tempfile
import atexit
import configparser
import time
import signal

class RTSPStreamer:
    def __init__(self):
        self.process = None
        self.should_exit = False
        self.retry_count = 0
        self.max_retries = 5  # 最大重试次数（0表示无限重试）
        self.base_delay = 2   # 基础重试延迟（秒）
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """处理退出信号"""
        self.should_exit = True
        if self.process:
            self.process.terminate()

    def read_config(self, config_path='cap.ini'):
        """读取配置文件"""
        config = configparser.ConfigParser()
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")

        config.read(config_path, encoding='utf-8')
        
        if not config.has_section('RTSP'):
            raise ValueError("配置文件中缺少 [RTSP] 段落")

        return {
            'rtsp_url': config.get('RTSP', 'serveUrl', fallback=None),
            'video_dir': config.get('RTSP', 'filePath', fallback=None)
        }

    def start_stream(self, concat_file, rtsp_url):
        """启动FFmpeg推流进程"""
        command = [
            'ffmpeg',
            '-re',
            '-stream_loop', '-1',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-f', 'rtsp',
            '-rtsp_transport', 'tcp',
            rtsp_url
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        return self.process

    def get_video_files(self, video_dir):
        """获取视频文件列表"""
        if not os.path.isdir(video_dir):
            raise ValueError(f"无效的视频目录: {video_dir}")

        file_list = sorted([
            os.path.join(video_dir, f)
            for f in os.listdir(video_dir)
            if f.lower().endswith('.mp4')
        ])

        if not file_list:
            raise ValueError(f"{video_dir} 目录中未找到MP4文件")

        return file_list

    def run(self):
        """主运行循环"""
        try:
            config = self.read_config()
            rtsp_url = config['rtsp_url']
            video_dir = config['video_dir']
            
            while not self.should_exit:
                try:
                    # 每次重试重新获取文件列表
                    file_list = self.get_video_files(video_dir)
                    concat_file = create_concat_file(file_list)
                    
                    print(f"▶ 尝试启动RTSP推流（第{self.retry_count+1}次尝试）...")
                    process = self.start_stream(concat_file, rtsp_url)
                    
                    # 监控进程状态
                    while True:
                        if self.should_exit:
                            process.terminate()
                            return
                            
                        # 读取错误输出
                        line = process.stderr.readline()
                        if line:
                            print(f"[FFmpeg] {line.strip()}")
                            
                        # 检查进程状态
                        return_code = process.poll()
                        if return_code is not None:
                            if return_code == 0:
                                print("✓ 正常退出")
                                return
                            else:
                                print(f"⚠ 推流中断，返回码: {return_code}")
                                break
                                
                        time.sleep(0.1)

                except Exception as e:
                    print(f"❌ 发生错误: {str(e)}")

                finally:
                    # 清理临时文件
                    if 'concat_file' in locals():
                        os.unlink(concat_file)
                    
                # 计算重试延迟（指数退避）
                delay = self.base_delay * (2 ** self.retry_count)
                print(f"⏳ {delay}秒后重试...")
                time.sleep(delay)
                
                # 更新重试计数器
                if self.max_retries > 0 and self.retry_count >= self.max_retries:
                    print("❌ 达到最大重试次数，终止程序")
                    return
                self.retry_count += 1

        except Exception as e:
            print(f"💥 致命错误: {str(e)}")
            exit(1)

def create_concat_file(file_list):
    """创建临时concat文件"""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as f:
        for file in file_list:
            f.write(f"file '{file}'\n")
        concat_filename = f.name
        atexit.register(os.unlink, concat_filename)
        return concat_filename

if __name__ == "__main__":
    streamer = RTSPStreamer()
    streamer.run()