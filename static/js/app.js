const state = Object.seal({
    markdown: '',
    fileName: '',
    originalFile: null,
    isPreview: false
});

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('docling-theme', theme); } catch (_) {}
}

function initTheme() {
    let theme = 'light';
    try {
        const stored = localStorage.getItem('docling-theme');
        if (stored === 'dark' || stored === 'light') theme = stored;
        else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) theme = 'dark';
    } catch (_) {}
    setTheme(theme);
}

function clearElement(node) {
    if (!node) return;
    if (typeof node.replaceChildren === 'function') node.replaceChildren();
    else node.innerHTML = '';
}

function renderDownloadCard(target, { icon = '📄', message, url, downloadName, linkLabel = 'Download Original' }) {
    if (!target) return;

    const container = document.createElement('div');
    container.className = 'original-download-card';

    const iconEl = document.createElement('div');
    iconEl.className = 'original-download-icon';
    iconEl.textContent = icon;

    const messageEl = document.createElement('p');
    messageEl.className = 'original-download-message';
    messageEl.textContent = message;

    const linkEl = document.createElement('a');
    linkEl.href = url;
    linkEl.className = 'original-download-link';
    linkEl.textContent = linkLabel;
    linkEl.target = '_blank';
    linkEl.rel = 'noopener';
    if (downloadName) linkEl.download = downloadName;

    container.append(iconEl, messageEl, linkEl);
    target.appendChild(container);
}

function renderPdfFallback(target, url, downloadName) {
    if (!target) return;
    clearElement(target);
    const embed = document.createElement('embed');
    embed.src = url;
    embed.type = 'application/pdf';
    embed.className = 'original-pdf';
    embed.onerror = () => {
        clearElement(target);
        renderDownloadCard(target, {
            message: 'Open the PDF in a new tab',
            url,
            downloadName,
            linkLabel: 'Open PDF'
        });
    };
    target.appendChild(embed);
}

function displayOriginalDocument() {
    const originalViewer = document.getElementById('originalViewer');
    if (!originalViewer) return;

    clearElement(originalViewer);

    const originalFile = state.originalFile;
    if (!originalFile) {
        const placeholder = document.createElement('div');
        placeholder.className = 'original-placeholder';
        placeholder.innerHTML = '<p>Original document will appear here after processing</p>';
        originalViewer.appendChild(placeholder);
        return;
    }

    const { url, content_type: contentType, original_name: originalName } = originalFile;
    const displayName = originalName || state.fileName || 'document';

    if (!contentType) {
        renderDownloadCard(originalViewer, {
            message: `File: ${displayName}`,
            url,
            downloadName: displayName
        });
        return;
    }

    if (contentType.startsWith('image/')) {
        const img = document.createElement('img');
        img.src = url;
        img.alt = displayName;
        img.className = 'original-image';
        img.onerror = () => {
            clearElement(originalViewer);
            renderDownloadCard(originalViewer, {
                message: `Unable to display ${displayName}`,
                url,
                downloadName: displayName
            });
        };
        originalViewer.appendChild(img);
        return;
    }

    if (contentType === 'application/pdf') {
        const pdfObject = document.createElement('object');
        pdfObject.data = url;
        pdfObject.type = 'application/pdf';
        pdfObject.className = 'original-pdf';
        pdfObject.onerror = () => renderPdfFallback(originalViewer, url, displayName);

        const fallbackNotice = document.createElement('div');
        fallbackNotice.className = 'original-pdf-fallback';
        const link = document.createElement('a');
        link.href = url;
        link.textContent = 'Open PDF in a new tab';
        link.target = '_blank';
        link.rel = 'noopener';
        fallbackNotice.append('If the PDF does not display, ', link, '.');
        pdfObject.appendChild(fallbackNotice);

        originalViewer.appendChild(pdfObject);
        return;
    }

    if (contentType.includes('word') || contentType.includes('document')) {
        renderDownloadCard(originalViewer, {
            message: 'DOCX file uploaded',
            url,
            downloadName: displayName
        });
        return;
    }

    renderDownloadCard(originalViewer, {
        message: `File: ${displayName}`,
        url,
        downloadName: displayName
    });
}

function displayOutput() {
    const outputContent = document.getElementById('outputContent');
    if (!outputContent) return;
    if (state.isPreview) {
        outputContent.innerHTML = marked.parse(state.markdown || '');
        outputContent.classList.remove('markdown-raw');
        outputContent.classList.add('markdown-preview');
    } else {
        outputContent.textContent = state.markdown || '';
        outputContent.classList.remove('markdown-preview');
        outputContent.classList.add('markdown-raw');
    }
}

window.addEventListener('DOMContentLoaded', () => {
    initTheme();

    const themeToggle = document.getElementById('themeToggle');
    themeToggle?.addEventListener('click', () => {
        const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        setTheme(next);
    });

    // Load system info
    fetch('/info')
        .then(res => res.json())
        .then(data => {
            const deviceEl = document.getElementById('deviceInfo');
            const threadsEl = document.getElementById('threadsInfo');
            if (deviceEl) deviceEl.textContent = (data.device || '').toUpperCase();
            if (threadsEl) threadsEl.textContent = data.num_threads ?? '';
        })
        .catch(() => {});

    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadFilename = document.getElementById('uploadFilename');
    const convertBtn = document.getElementById('convertBtn');
    const loading = document.getElementById('loading');
    const loadingFileName = document.getElementById('loadingFileName');
    const outputSection = document.getElementById('outputSection');
    const toggleSwitch = document.getElementById('toggleSwitch');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorMessage = document.getElementById('errorMessage');

    const setLoadingState = (isLoading) => {
        loading?.classList.toggle('show', isLoading);
        if (convertBtn) convertBtn.disabled = isLoading;
        if (isLoading && loadingFileName) {
            loadingFileName.textContent = state.fileName;
        }
        // Hide filename in upload area when loading starts
        if (isLoading && uploadFilename) {
            uploadFilename.classList.remove('show');
        }
    };

    const setOutputVisibility = (isVisible) => {
        outputSection?.classList.toggle('show', isVisible);
    };

    const showError = (message) => {
        if (!errorMessage) return;
        errorMessage.textContent = message;
        errorMessage.classList.add('show');
    };

    const clearError = () => {
        if (!errorMessage) return;
        errorMessage.textContent = '';
        errorMessage.classList.remove('show');
    };

    const openPicker = () => fileInput?.click();
    uploadArea?.addEventListener('click', openPicker);
    uploadArea?.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); } });

    uploadArea?.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea?.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
    uploadArea?.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            if (fileInput) fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });

    fileInput?.addEventListener('change', (e) => {
        const target = e.target;
        if (target && target.files && target.files.length > 0) {
            handleFileSelect(target.files[0]);
        }
    });

    function handleFileSelect(file) {
        state.fileName = file?.name || '';
        state.originalFile = null;
        setOutputVisibility(false);
        clearError();
        displayOriginalDocument();
        if (convertBtn) convertBtn.disabled = false;
        
        // Show filename in upload area
        if (uploadFilename) {
            uploadFilename.textContent = state.fileName;
            uploadFilename.classList.add('show');
        }
    }

    convertBtn?.addEventListener('click', async () => {
        const file = fileInput?.files?.[0];
        if (!file) return;

        setLoadingState(true);
        setOutputVisibility(false);
        clearError();

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/convert', { method: 'POST', body: formData });
            const data = await response.json().catch(() => ({}));
            if (response.ok) {
                state.markdown = data.markdown || '';
                state.originalFile = data.original_file || null;
                state.fileName = data.filename || state.fileName;
                if (state.originalFile && state.originalFile.original_name) {
                    state.fileName = state.originalFile.original_name;
                }
                displayOriginalDocument();
                displayOutput();
                setOutputVisibility(true);
                // Auto scroll to the output and to the bottom of its content
                requestAnimationFrame(() => {
                    outputSection?.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    const outputContentEl = document.getElementById('outputContent');
                    if (outputContentEl) {
                        outputContentEl.scrollTo({ top: outputContentEl.scrollHeight, behavior: 'smooth' });
                    }
                });
            } else {
                throw new Error(data?.detail || 'Conversion failed');
            }
        } catch (error) {
            showError('Error: ' + (error?.message || error));
        } finally {
            setLoadingState(false);
        }
    });

    toggleSwitch?.addEventListener('click', () => {
        state.isPreview = !state.isPreview;
        toggleSwitch.classList.toggle('active', state.isPreview);
        toggleSwitch.setAttribute('aria-pressed', String(state.isPreview));
        displayOutput();
    });

    downloadBtn?.addEventListener('click', () => {
        const blob = new Blob([state.markdown || ''], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const base = state.fileName?.replace(/\.[^/.]+$/, '') || 'document';
        a.download = base + '.md';
        a.click();
        URL.revokeObjectURL(url);
    });

    displayOriginalDocument();
    displayOutput();
});


