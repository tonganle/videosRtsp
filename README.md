1.本地mp4转rtsp流地址
2.拉取流地址存储为mp4文件
安装rtsp服务端
docker run -d --restart unless-stopped \
  -e MTX_RTSPTRANSPORTS=tcp \
  -e MTX_WEBRTCADDITIONALHOSTS=192.168.0.148 \
  -p 8554:8554 \
  -p 1935:1935 \
  -p 8888:8888 \
  -p 8889:8889 \
  -p 8890:8890/udp \
  -p 8189:8189/udp \
  bluenviron/mediamtx