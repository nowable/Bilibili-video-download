import requests
import re
from bilibili_api import video, sync

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    # Windows 文件名不能包含：\ / : * ? " < > |
    illegal_chars = r'[\\/:*?"<>|]'
    return re.sub(illegal_chars, '_', filename)

def download_bilibili(url):
    try:
        print("正在解析视频链接...")
        
        # 从 URL 提取 BV 号
        bv_match = re.search(r'BV\w+', url)
        if not bv_match:
            print("❌ 无效的 B 站视频链接")
            return
        
        bvid = bv_match.group()
        print(f"✅ 识别到视频 BV 号：{bvid}")
        
        # 创建视频对象
        v = video.Video(bvid=bvid)
        
        # 获取视频信息
        info = sync(v.get_info())
        title = info['title']
        cid = info['cid']  # 获取视频分 P ID
        print(f"✅ 找到视频：{title}")
        
        # 获取视频下载链接（默认最高画质）
        print("正在获取视频下载地址...")
        download_url_data = sync(v.get_download_url(cid=cid))
        
        # 调试：打印返回数据结构
        # print(f"调试信息：{download_url_data}")
        
        # 获取视频流地址 - 适配 DASH 格式
        if 'durl' in download_url_data:
            video_url = download_url_data['durl'][0]['url']
        elif 'dash' in download_url_data and 'video' in download_url_data['dash']:
            # DASH 格式：音视频分离，下载视频流
            dash_video = download_url_data['dash']['video']
            if len(dash_video) > 0:
                video_url = dash_video[0]['baseUrl']
            else:
                print("❌ DASH 视频列表为空")
                return
        elif 'video' in download_url_data:
            video_url = download_url_data['video'][0]['url']
        else:
            print("❌ 无法解析视频下载地址")
            print(f"返回数据：{download_url_data.keys()}")
            return
        
        # 清理文件名
        safe_title = sanitize_filename(title)
        
        print("开始下载...")
        video_res = requests.get(video_url, stream=True, timeout=30)
        
        # 获取文件大小
        total_size = int(video_res.headers.get('content-length', 0))
        downloaded = 0
        
        with open(f"{safe_title}.mp4", "wb") as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # 显示下载进度
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r下载进度：{percent:.1f}%", end='', flush=True)
        
        print(f"\n✅ 下载完成！文件：{safe_title}.mp4")
        
    except Exception as e:
        print(f"❌ 出错了：{e}")

if __name__ == "__main__":
    # ↓↓↓ 把这里换成你要下载的 B 站视频链接 ↓↓↓
    video_url = "https://www.bilibili.com/video/BV13QXGBDEFu?vd_source=20f974fa6a21f282d8ed0531349480f3"
    download_bilibili(video_url)
