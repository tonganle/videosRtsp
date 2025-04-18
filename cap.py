# coding=utf-8
import os
import cv2
import time
import datetime
import numpy as np
import threading
import configparser
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_capture.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()


class MyThread(threading.Thread):
    def __init__(self, func, args, name=""):
        threading.Thread.__init__(self)
        self.name = name
        self.func = func
        self.args = args

    def run(self):
        cam_id = self.args[0]
        logger.info(f"Cam {cam_id}: Thread starting.")
        try:
            self.func(*self.args)
        except Exception as e:
            logger.error(f"Cam {cam_id}: Thread encountered an error: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Cam {cam_id}: Thread exiting.")


def cap_videos(camid, cam, stat, videopath, r, m):
    while True:  # 外层重试循环
        try:
            # 持续尝试建立RTSP连接
            while True:
                logger.info(f"Cam {camid}: Attempting to connect to RTSP stream...")
                capstream = cv2.VideoCapture(cam)
                if capstream.isOpened():
                    logger.info(f"Cam {camid}: Successfully connected to RTSP stream")
                    break
                logger.error(f"Cam {camid}: Connection failed, retrying in 5 seconds...")
                time.sleep(5)

            # 持续尝试获取有效视频流
            while True:
                # 获取视频分辨率
                retries = 5
                w, h = 1920, 1080
                valid_stream = False
                while retries > 0:
                    ret, frame = capstream.read()
                    if ret:
                        h, w = frame.shape[:2]
                        logger.info(f"Cam {camid}: Stream resolution confirmed: {w}x{h}")
                        valid_stream = True
                        break
                    logger.warning(f"Cam {camid}: Waiting for valid video stream ({retries} retries left)")
                    retries -= 1
                    time.sleep(1)

                if not valid_stream:
                    logger.error(f"Cam {camid}: Failed to get valid stream, reinitializing connection...")
                    capstream.release()
                    break  # 跳出到外层重试循环

                # 创建视频存储目录
                try:
                    if not os.path.exists(videopath):
                        logger.info(f"Cam {camid}: Creating video directory: {videopath}")
                        os.mkdir(videopath)
                except Exception as e:
                    logger.error(f"Cam {camid}: Directory creation failed: {str(e)}")
                    time.sleep(5)
                    continue

                # 初始化视频写入器
                segment_duration = m * 60 * r
                frame_skip = 0
                clip_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                video_filename = os.path.join(videopath, f"{stat}-{camid}-{clip_time}.mp4")
                videoWriter = cv2.VideoWriter(video_filename, cv2.VideoWriter_fourcc(*'mp4v'), r, (w, h))

                if not videoWriter.isOpened():
                    logger.error(f"Cam {camid}: Failed to initialize video writer")
                    capstream.release()
                    time.sleep(5)
                    continue  # 继续外层循环

                logger.info(f"Cam {camid}: Starting video capture loop")
                try:
                    # 主捕获循环
                    while capstream.isOpened():
                        ret, frame = capstream.read()
                        if not ret:
                            logger.warning(f"Cam {camid}: Frame read error, reinitializing connection...")
                            break  # 跳出到内层重试循环

                        # 分段逻辑
                        frame_skip += 1
                        if frame_skip >= segment_duration:
                            videoWriter.release()
                            logger.info(f"Cam {camid}: Saved video segment: {video_filename}")

                            clip_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            video_filename = os.path.join(videopath, f"{stat}-{camid}-{clip_time}.mp4")
                            videoWriter = cv2.VideoWriter(video_filename, cv2.VideoWriter_fourcc(*'mp4v'), r, (w, h))

                            if not videoWriter.isOpened():
                                logger.error(f"Cam {camid}: Failed to create new video writer")
                                break  # 跳出到内层重试循环
                            frame_skip = 0

                        videoWriter.write(frame)

                finally:
                    videoWriter.release()
                    logger.info(f"Cam {camid}: Released video writer resources")

                # 当主捕获循环退出时，重新初始化连接
                capstream.release()
                logger.info(f"Cam {camid}: Released capture resources")
                break  # 回到外层重试循环

        except Exception as e:
            logger.error(f"Cam {camid}: Critical error: {str(e)}", exc_info=True)
            try:
                capstream.release()
            except:
                pass
            try:
                videoWriter.release()
            except:
                pass
            time.sleep(5)


if __name__ == '__main__':
    try:
        # 读取配置文件
        cp = configparser.ConfigParser()
        if not cp.read('./cap.ini'):
            raise FileNotFoundError("Configuration file cap.ini not found")

        if not cp.has_section('SETTING'):
            raise ValueError("Missing [SETTING] section in config")

        # 验证必要参数
        required = ['camnum', 'vcrpath', 'station', 'ratio', 'var']
        for param in required:
            if not cp.has_option('SETTING', param):
                raise ValueError(f"Missing parameter: {param}")

        # 获取配置参数
        cam_num = int(cp.get('SETTING', 'camnum'))
        vcr_path = cp.get('SETTING', 'vcrpath')
        station = cp.get('SETTING', 'station')
        ratio = int(cp.get('SETTING', 'ratio'))
        var = int(cp.get('SETTING', 'var'))

        logger.info("\n" + "=" * 50 + "\n"
                                      f"Loaded configuration:\n"
                                      f"Cameras: {cam_num}\n"
                                      f"Save path: {vcr_path}\n"
                                      f"Station ID: {station}\n"
                                      f"Frame rate: {ratio}\n"
                                      f"Segment duration: {var} minutes\n" +
                    "=" * 50)

        # 启动摄像头线程
        for cam in range(cam_num):
            cam_id = str(cam + 1)
            if not cp.has_option('SETTING', f'camid{cam_id}'):
                raise ValueError(f"Missing camid{cam_id} in config")

            rtsp_url = cp.get('SETTING', f'camid{cam_id}')
            logger.info(f"Initializing camera {cam_id} with URL: {rtsp_url}")

            t_cap = MyThread(
                func=cap_videos,
                args=(cam_id, rtsp_url, station, vcr_path, ratio, var),
                name=f"Cam{cam_id}_Thread"
            )
            t_cap.start()
            time.sleep(0.5)  # 避免日志交叉

    except Exception as e:
        logger.critical(f"Initialization failed: {str(e)}", exc_info=True)
        exit(1)