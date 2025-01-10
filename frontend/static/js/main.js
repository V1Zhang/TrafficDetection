class VideoHandler {
    constructor() {
        this.canvas = document.getElementById('videoCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.videoSource = document.getElementById('videoSource');
        this.cameraSource = document.getElementById('cameraSource');
        this.ipCameraUrl = document.getElementById('ipCameraUrl');
        this.videoFile = document.getElementById('videoFile');
        this.startButton = document.getElementById('startButton');
        this.isStreaming = false;
        this.uploadProgress = document.getElementById('uploadProgress');
        this.progressBar = this.uploadProgress.querySelector('.progress-bar');
        this.progressText = this.uploadProgress.querySelector('.progress-text');
        
        this.eventSource = null;
        
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.startButton.addEventListener('click', () => this.toggleStream());
        
        // 切换视频源类型
        this.videoSource.addEventListener('change', () => {
            document.getElementById('cameraOptions').style.display = 
                this.videoSource.value === 'camera' ? 'block' : 'none';
            document.getElementById('fileOptions').style.display = 
                this.videoSource.value === 'file' ? 'block' : 'none';
        });
        
        // 摄像头源切换
        this.cameraSource.addEventListener('change', () => {
            this.ipCameraUrl.style.display = 
                this.cameraSource.value === 'ip' ? 'block' : 'none';
        });
    }

    async toggleStream() {
        if (this.isStreaming) {
            await this.stopStream();
            this.startButton.textContent = '启动';
        } else {
            await this.startStream();
            this.startButton.textContent = '停止';
        }
        this.isStreaming = !this.isStreaming;
    }

    async startStream() {
        try {
            const formData = new FormData();
            
            if (this.videoSource.value === 'camera') {
                const source = this.cameraSource.value;
                const url = source === 'ip' ? this.ipCameraUrl.value : 'local';
                formData.append('type', 'camera');
                formData.append('source', source);
                formData.append('url', url);
                
                await this.sendStreamRequest(formData);
            } else {
                const file = this.videoFile.files[0];
                if (!file) {
                    throw new Error('请选择视频文件');
                }
                formData.append('type', 'file');
                formData.append('video', file);
                
                await this.uploadVideoWithProgress(formData);
            }

            // 开始获取视频流和检测结果
            this.startVideoStream();
        } catch (err) {
            console.error('启动失败:', err);
            alert(err.message);
        } finally {
            this.hideProgress();
        }
    }

    async stopStream() {
        try {
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
            await fetch('/stop_stream', { method: 'POST' });
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        } catch (err) {
            console.error('停止失败:', err);
        }
    }

    startVideoStream() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        this.eventSource = new EventSource('/video_feed');
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            // 更新视频画面
            this.updateCanvas(data.frame);
            
            // 更新检测结果
            this.updateDetectionResults(data.detections);
        };
        
        this.eventSource.onerror = () => {
            if (!this.isStreaming) {
                this.eventSource.close();
                this.eventSource = null;
            }
        };
    }

    updateCanvas(frameBase64) {
        const img = new Image();
        img.onload = () => {
            // 设置 canvas 尺寸以匹配图像
            if (this.canvas.width !== img.width || this.canvas.height !== img.height) {
                this.canvas.width = img.width;
                this.canvas.height = img.height;
            }
            // 绘制图像
            this.ctx.drawImage(img, 0, 0);
        };
        img.src = `data:image/jpeg;base64,${frameBase64}`;
    }

    updateDetectionResults(results) {
        const container = document.getElementById('detectionResults');
        container.innerHTML = '';

        results.forEach(result => {
            const div = document.createElement('div');
            div.className = 'detection-result';
            div.innerHTML = `
                <img src="data:image/jpeg;base64,${result.image}">
                <p>类型: ${result.type}</p>
                <p>距离: ${result.distance}米</p>
                <p>置信度: ${result.confidence}%</p>
            `;
            container.appendChild(div);
        });
    }

    async uploadVideoWithProgress(formData) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    this.updateProgress(percentComplete);
                }
            };
            
            xhr.onload = () => {
                if (xhr.status === 200) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error('上传失败'));
                }
            };
            
            xhr.onerror = () => {
                reject(new Error('上传失败'));
            };
            
            this.showProgress();
            xhr.open('POST', '/start_stream', true);
            xhr.send(formData);
        });
    }

    async sendStreamRequest(formData) {
        const response = await fetch('/start_stream', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('启动失败');
        }
        
        return response.json();
    }

    showProgress() {
        this.uploadProgress.style.display = 'block';
        this.updateProgress(0);
    }

    hideProgress() {
        this.uploadProgress.style.display = 'none';
    }

    updateProgress(percent) {
        const roundedPercent = Math.round(percent);
        this.progressBar.style.width = `${roundedPercent}%`;
        this.progressText.textContent = `${roundedPercent}%`;
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    new VideoHandler();
}); 