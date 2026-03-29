from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import threading
import os
import re
from bilibili_api import video, sync
import requests

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 存储下载状态
download_status = {
    'downloading': False,
    'progress': 0,
    'message': '',
    'filename': None
}

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    illegal_chars = r'[\\/:*?"<>|]'
    return re.sub(illegal_chars, '_', filename)

def download_task(url):
    """后台下载任务"""
    global download_status
    
    try:
        download_status['downloading'] = True
        download_status['progress'] = 0
        download_status['message'] = '正在解析视频链接...'
        
        # 从 URL 提取 BV 号
        bv_match = re.search(r'BV\w+', url)
        if not bv_match:
            download_status['message'] = '❌ 无效的 B 站视频链接'
            download_status['downloading'] = False
            return
        
        bvid = bv_match.group()
        download_status['message'] = f'✅ 识别到视频 BV 号：{bvid}'
        
        # 创建视频对象
        v = video.Video(bvid=bvid)
        
        # 获取视频信息
        info = sync(v.get_info())
        title = info['title']
        cid = info['cid']
        download_status['message'] = f'✅ 找到视频：{title}'
        
        # 获取视频下载链接
        download_status['message'] = '正在获取视频下载地址...'
        download_url_data = sync(v.get_download_url(cid=cid))
        
        # 获取视频流地址 - 适配 DASH 格式
        if 'durl' in download_url_data:
            video_url = download_url_data['durl'][0]['url']
        elif 'dash' in download_url_data and 'video' in download_url_data['dash']:
            dash_video = download_url_data['dash']['video']
            if len(dash_video) > 0:
                video_url = dash_video[0]['baseUrl']
            else:
                download_status['message'] = '❌ DASH 视频列表为空'
                download_status['downloading'] = False
                return
        elif 'video' in download_url_data:
            video_url = download_url_data['video'][0]['url']
        else:
            download_status['message'] = '❌ 无法解析视频下载地址'
            download_status['downloading'] = False
            return
        
        # 清理文件名
        safe_title = sanitize_filename(title)
        filename = f"{safe_title}.mp4"
        download_status['filename'] = filename
        
        download_status['message'] = '开始下载...'
        video_res = requests.get(video_url, stream=True, timeout=30)
        
        # 获取文件大小
        total_size = int(video_res.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, "wb") as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # 更新进度
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        download_status['progress'] = round(percent, 1)
        
        download_status['progress'] = 100
        download_status['message'] = f'✅ 下载完成！文件：{filename}'
        download_status['downloading'] = False
        
    except Exception as e:
        download_status['message'] = f'❌ 出错了：{e}'
        download_status['downloading'] = False

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def start_download():
    """开始下载 API"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'message': '请提供视频链接'})
    
    if download_status['downloading']:
        return jsonify({'success': False, 'message': '已有下载任务正在进行中'})
    
    # 重置状态
    download_status['progress'] = 0
    download_status['message'] = ''
    download_status['filename'] = None
    
    # 启动后台下载线程
    thread = threading.Thread(target=download_task, args=(url,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': '下载已开始'})

@app.route('/api/status')
def get_status():
    """获取下载状态 API"""
    return jsonify(download_status)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
