document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('url-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const errorMsg = document.getElementById('error-msg');
    const videoInfo = document.getElementById('video-info');
    const videoThumbnail = document.getElementById('video-thumbnail');
    const videoTitle = document.getElementById('video-title');
    const typeSelect = document.getElementById('type-select');
    const qualitySelect = document.getElementById('quality-select');
    const qualityGroup = document.getElementById('quality-group');
    const downloadBtn = document.getElementById('download-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const statusText = document.getElementById('status-text');
    const finalLink = document.getElementById('final-link');
    const downloadLink = document.getElementById('download-link');

    let currentFormats = [];

    analyzeBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) return;

        analyzeBtn.disabled = true;
        analyzeBtn.innerText = 'Analysing...';
        errorMsg.innerText = '';
        videoInfo.classList.add('hidden');

        try {
            const response = await fetch('/api/formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            videoTitle.innerText = data.title;
            videoThumbnail.src = data.thumbnail;
            currentFormats = data.formats;

            // Populate qualities
            qualitySelect.innerHTML = '';
            currentFormats.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id;
                opt.innerText = `${f.quality} (${f.ext})`;
                qualitySelect.appendChild(opt);
            });

            videoInfo.classList.remove('hidden');
        } catch (err) {
            errorMsg.innerText = err.message;
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.innerText = 'Analyze';
        }
    });

    typeSelect.addEventListener('change', () => {
        if (typeSelect.value === 'audio') {
            qualityGroup.classList.add('hidden');
        } else {
            qualityGroup.classList.remove('hidden');
        }
    });

    downloadBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        const type = typeSelect.value;
        const format_id = qualitySelect.value;

        downloadBtn.disabled = true;
        progressContainer.classList.remove('hidden');
        finalLink.classList.add('hidden');
        progressBarFill.style.width = '0%';
        statusText.innerText = 'Starting...';

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, type, format_id })
            });

            const { job_id } = await response.json();
            pollStatus(job_id);
        } catch (err) {
            statusText.innerText = 'Initial request failed.';
            downloadBtn.disabled = false;
        }
    });

    async function pollStatus(job_id) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${job_id}`);
                const data = await response.json();

                progressBarFill.style.width = `${data.progress}%`;
                statusText.innerText = data.text;

                if (data.status === 'completed') {
                    clearInterval(interval);
                    statusText.innerText = 'Video is ready!';
                    finalLink.classList.remove('hidden');
                    downloadLink.href = `/api/file/${job_id}`;
                    downloadBtn.disabled = false;
                } else if (data.status === 'error') {
                    clearInterval(interval);
                    statusText.innerText = data.text;
                    downloadBtn.disabled = false;
                }
            } catch (err) {
                clearInterval(interval);
                statusText.innerText = 'Connection lost.';
                downloadBtn.disabled = false;
            }
        }, 2000);
    }
});
