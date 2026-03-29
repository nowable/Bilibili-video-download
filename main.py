import sys
import os
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import threading
import re
from bilibili_api import video, sync
import requests

app = Flask(__name__)
CORS(app)

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
        
        bv_match = re.search(r'BV\w+', url)
        if not bv_match:
            download_status['message'] = '❌ 无效的 B 站视频链接'
            download_status['downloading'] = False
            return
        
        bvid = bv_match.group()
        download_status['message'] = f'✅ 识别到视频 BV 号：{bvid}'
        
        v = video.Video(bvid=bvid)
        info = sync(v.get_info())
        title = info['title']
        cid = info['cid']
        download_status['message'] = f'✅ 找到视频：{title}'
        
        download_status['message'] = '正在获取视频下载地址...'
        download_url_data = sync(v.get_download_url(cid=cid))
        
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
        
        safe_title = sanitize_filename(title)
        filename = f"{safe_title}.mp4"
        download_status['filename'] = filename
        
        download_status['message'] = '开始下载...'
        video_res = requests.get(video_url, stream=True, timeout=30)
        
        total_size = int(video_res.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, "wb") as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        download_status['progress'] = round(percent, 1)
        
        download_status['progress'] = 100
        download_status['message'] = f'✅ 下载完成！文件：{filename}'
        download_status['downloading'] = False
        
    except Exception as e:
        download_status['message'] = f'❌ 出错了：{e}'
        download_status['downloading'] = False

# HTML 模板（内嵌到 EXE 中）
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B 站视频下载器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        h1 { text-align: center; color: #333; margin-bottom: 10px; font-size: 32px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 14px; }
        .input-group { margin-bottom: 20px; }
        input[type="text"] {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4); }
        .btn:disabled { background: #ccc; cursor: not-allowed; transform: none; }
        .status-area { margin-top: 30px; padding: 20px; background: #f5f5f5; border-radius: 10px; display: none; }
        .status-area.show { display: block; }
        .status-message { font-size: 16px; color: #333; margin-bottom: 15px; word-break: break-word; }
        .progress-container { width: 100%; height: 30px; background: #e0e0e0; border-radius: 15px; overflow: hidden; margin-top: 10px; }
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
        }
        .success { color: #4CAF50; font-weight: bold; }
        .error { color: #f44336; font-weight: bold; }
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .tips {
            margin-top: 20px;
            padding: 15px;
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 5px;
            font-size: 14px;
            color: #856404;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 B 站视频下载器</h1>
        <p class="subtitle">输入视频链接，一键下载高清视频</p>
        <div class="input-group">
            <input type="text" id="videoUrl" placeholder="请输入 B 站视频链接（如：https://www.bilibili.com/video/BV...）">
        </div>
        <button class="btn" id="downloadBtn" onclick="startDownload()">🚀 开始下载</button>
        <div class="status-area" id="statusArea">
            <div class="status-message" id="statusMessage"></div>
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar" id="progressBar">0%</div>
            </div>
        </div>
        <div class="tips">
            💡 <strong>使用提示：</strong><br>
            • 支持普通视频链接和分享链接<br>
            • 自动提取最高画质<br>
            • 下载完成后文件保存在当前目录<br>
            • 请勿用于商业用途，尊重版权
        </div>
    </div>
    <script>
        let statusInterval = null;
        async function startDownload() {
            const urlInput = document.getElementById('videoUrl');
            const downloadBtn = document.getElementById('downloadBtn');
            const statusArea = document.getElementById('statusArea');
            const statusMessage = document.getElementById('statusMessage');
            const progressBar = document.getElementById('progressBar');
            const progressContainer = document.getElementById('progressContainer');
            const url = urlInput.value.trim();
            if (!url) { alert('请输入视频链接！'); return; }
            downloadBtn.disabled = true;
            downloadBtn.innerHTML = '<span class="loading-spinner"></span>下载中...';
            statusArea.classList.add('show');
            progressContainer.style.display = 'block';
            statusMessage.innerHTML = '<span class="loading-spinner"></span>正在启动下载任务...';
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            try {
                const response = await fetch('/api/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: url })
                });
                const result = await response.json();
                if (result.success) {
                    startStatusPolling();
                } else {
                    showError(result.message);
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '🚀 开始下载';
                }
            } catch (error) {
                showError('网络错误：' + error.message);
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '🚀 开始下载';
            }
        }
        function startStatusPolling() {
            statusInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/status');
                    const status = await response.json();
                    updateStatus(status);
                    if (!status.downloading && status.progress === 100) {
                        clearInterval(statusInterval);
                        document.getElementById('downloadBtn').disabled = false;
                        document.getElementById('downloadBtn').innerHTML = '🚀 开始下载';
                    } else if (!status.downloading && status.progress < 100) {
                        clearInterval(statusInterval);
                        document.getElementById('downloadBtn').disabled = false;
                        document.getElementById('downloadBtn').innerHTML = '🚀 开始下载';
                    }
                } catch (error) {
                    console.error('状态更新失败:', error);
                }
            }, 1000);
        }
        function updateStatus(status) {
            const statusMessage = document.getElementById('statusMessage');
            const progressBar = document.getElementById('progressBar');
            if (status.message.includes('✅')) {
                statusMessage.innerHTML = `<span class="success">${status.message}</span>`;
            } else if (status.message.includes('❌')) {
                statusMessage.innerHTML = `<span class="error">${status.message}</span>`;
            } else {
                statusMessage.innerHTML = `<span class="loading-spinner"></span>${status.message}`;
            }
            if (status.progress > 0) {
                progressBar.style.width = status.progress + '%';
                progressBar.textContent = status.progress.toFixed(1) + '%';
            }
        }
        function showError(message) {
            const statusArea = document.getElementById('statusArea');
            const statusMessage = document.getElementById('statusMessage');
            const progressContainer = document.getElementById('progressContainer');
            statusArea.classList.add('show');
            progressContainer.style.display = 'none';
            statusMessage.innerHTML = `<span class="error">${message}</span>`;
        }
        document.getElementById('videoUrl').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') { startDownload(); }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'message': '请提供视频链接'})
    
    if download_status['downloading']:
        return jsonify({'success': False, 'message': '已有下载任务正在进行中'})
    
    download_status['progress'] = 0
    download_status['message'] = ''
    download_status['filename'] = None
    
    thread = threading.Thread(target=download_task, args=(url,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': '下载已开始'})

@app.route('/api/status')
def get_status():
    return jsonify(download_status)

if __name__ == '__main__':
    print("=" * 50)
    print("🎬 B 站视频下载器启动成功！")
    print("=" * 50)
    print("📍 请在浏览器中打开：http://localhost:5000")
    print("💡 按 Ctrl+C 可停止服务")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=5000)
