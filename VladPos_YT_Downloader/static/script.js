document.addEventListener('DOMContentLoaded', () => {
    const urlSearchInput = document.getElementById('url-search-input');
    const searchBtn = document.getElementById('search-btn');
    const errorMsg = document.getElementById('error-msg');
    const searchResults = document.getElementById('search-results');

    // Progress UI
    const progressContainer = document.getElementById('progress-container');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const statusText = document.getElementById('status-text');
    const progressDetails = document.getElementById('progress-details');
    const finalLink = document.getElementById('final-link');
    const downloadLink = document.getElementById('download-link');

    // Modals
    const playModal = document.getElementById('play-modal');
    const downloadModal = document.getElementById('download-modal');
    const youtubeIframe = document.getElementById('youtube-iframe');
    const closePlay = document.getElementById('close-play');
    const closeDownload = document.getElementById('close-download');

    // Download Modal Elements
    const modalVideoTitle = document.getElementById('modal-video-title');
    const modalTypeSelect = document.getElementById('modal-type-select');
    const modalQualitySelect = document.getElementById('modal-quality-select');
    const modalQualityGroup = document.getElementById('modal-quality-group');
    const modalStartDownloadBtn = document.getElementById('modal-start-download-btn');

    let currentVideo = null;

    // --- Utility ---
    function showModal(modal) {
        modal.classList.remove('hidden');
        setTimeout(() => modal.classList.add('visible'), 10);
    }

    function hideModal(modal) {
        modal.classList.remove('visible');
        setTimeout(() => modal.classList.add('hidden'), 300);
    }

    function isPlaylist(url) {
        return url.includes('list=') || url.includes('start_radio=');
    }

    // --- Search Logic ---
    searchBtn.addEventListener('click', async () => {
        const query = urlSearchInput.value.trim();
        if (!query) return;

        if (isPlaylist(query)) {
            errorMsg.innerText = "Грешка: Плейлисти не се поддържат. Моля, сложи линк към индивидуално видео.";
            return;
        }

        if (query.startsWith('http')) {
            analyzeDirect(query);
            return;
        }

        searchBtn.disabled = true;
        searchBtn.innerText = 'Търсене...';
        errorMsg.innerText = '';
        searchResults.classList.add('hidden');
        searchResults.innerHTML = '';

        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            data.forEach(video => {
                const card = createVideoCard(video);
                searchResults.appendChild(card);
            });
            searchResults.classList.remove('hidden');
        } catch (err) {
            errorMsg.innerText = "Грешка: " + err.message;
        } finally {
            searchBtn.disabled = false;
            searchBtn.innerText = 'Търси / Извлечи';
        }
    });

    function createVideoCard(video) {
        const div = document.createElement('div');
        div.className = 'video-card';
        div.innerHTML = `
            <img src="${video.thumbnail}" class="card-thumb" alt="thumb">
            <div class="card-content">
                <h3>${video.title}</h3>
                <p>Канал: ${video.channel} • ${video.duration || ''}</p>
                <div class="card-actions">
                    <button class="btn-play">Гледай</button>
                    <button class="btn-download">Свали</button>
                </div>
            </div>
        `;

        div.querySelector('.btn-play').addEventListener('click', () => {
            youtubeIframe.src = `https://www.youtube.com/embed/${video.id}?autoplay=1`;
            showModal(playModal);
        });

        div.querySelector('.btn-download').addEventListener('click', () => {
            openDownloadModal(video);
        });

        return div;
    }

    // --- Modal Logic ---
    closePlay.addEventListener('click', () => {
        hideModal(playModal);
        youtubeIframe.src = '';
    });

    closeDownload.addEventListener('click', () => {
        hideModal(downloadModal);
    });

    window.onclick = (event) => {
        if (event.target == playModal) closePlay.click();
        if (event.target == downloadModal) closeDownload.click();
    };

    async function openDownloadModal(video) {
        currentVideo = video;
        modalVideoTitle.innerText = video.title;
        modalStartDownloadBtn.disabled = true;
        modalStartDownloadBtn.innerText = 'Зареждане...';
        showModal(downloadModal);

        try {
            const response = await fetch('/api/formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: video.id || video.url })
            });
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            modalQualitySelect.innerHTML = '';
            data.formats.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id;
                opt.innerText = `${f.quality} (${f.ext})`;
                modalQualitySelect.appendChild(opt);
            });
            modalStartDownloadBtn.disabled = false;
            modalStartDownloadBtn.innerText = 'Започни изтеглянето';

            // If was direct analyze, update title and currentVideo properly
            modalVideoTitle.innerText = data.title;
            currentVideo.title = data.title;
            currentVideo.url = currentVideo.url || `https://www.youtube.com/watch?v=${video.id}`;
        } catch (err) {
            modalVideoTitle.innerText = 'Грешка: ' + err.message;
            modalStartDownloadBtn.innerText = 'Опитай пак';
            modalStartDownloadBtn.disabled = false;
        }
    }

    modalTypeSelect.addEventListener('change', () => {
        if (modalTypeSelect.value === 'audio') {
            modalQualityGroup.classList.add('hidden');
        } else {
            modalQualityGroup.classList.remove('hidden');
        }
    });

    modalStartDownloadBtn.addEventListener('click', async () => {
        const type = modalTypeSelect.value;
        const format_id = modalQualitySelect.value;

        hideModal(downloadModal);
        progressContainer.classList.remove('hidden');
        progressContainer.scrollIntoView({ behavior: 'smooth' });
        finalLink.classList.add('hidden');
        progressBarFill.style.width = '0%';
        statusText.innerText = 'Подготовка...';
        progressDetails.innerText = '';

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentVideo.url, type, format_id })
            });
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            pollStatus(data.job_id);
        } catch (err) {
            statusText.innerText = 'Грешка: ' + err.message;
        }
    });

    // --- Direct Analyze Logic ---
    async function analyzeDirect(url) {
        errorMsg.innerText = '';
        // Minimal object to trigger the fetching in modal
        const vidObj = {
            id: null,
            title: "Зареждане на видео...",
            url: url
        };
        openDownloadModal(vidObj);
    }

    // --- Polling Logic ---
    async function pollStatus(job_id) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${job_id}`);
                const data = await response.json();

                progressBarFill.style.width = `${data.progress}%`;
                statusText.innerText = data.text;

                if (data.status === 'downloading') {
                    progressDetails.innerText = `Изтеглени: ${data.downloaded_mb} от ${data.total_mb}`;
                }

                if (data.status === 'completed') {
                    clearInterval(interval);
                    statusText.innerText = 'Готово!';
                    progressDetails.innerText = '';
                    finalLink.classList.remove('hidden');
                    downloadLink.href = `/api/file/${job_id}`;
                } else if (data.status === 'error') {
                    clearInterval(interval);
                    statusText.innerText = data.text;
                    progressDetails.innerText = '';
                }
            } catch (err) {
                clearInterval(interval);
                statusText.innerText = 'Грешка при връзката.';
            }
        }, 2000);
    }
});
