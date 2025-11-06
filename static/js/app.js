let currentMarkdown = '';
let currentFileName = '';
let currentOriginalFile = null;
let isPreview = false;

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

function displayOriginalDocument() {
    const originalViewer = document.getElementById('originalViewer');
    if (!originalViewer || !currentOriginalFile) return;

    const { url, content_type } = currentOriginalFile;

    // Debug logging
    console.log('Displaying original document:', { url, content_type });

    // Clear previous content
    originalViewer.innerHTML = '';

    if (content_type.startsWith('image/')) {
        // Display images directly
        const img = document.createElement('img');
        img.src = url;
        img.alt = 'Original document';
        img.style.maxWidth = '100%';
        img.style.maxHeight = '100%';
        img.onerror = () => console.error('Failed to load image:', url);
        originalViewer.appendChild(img);
    } else if (content_type === 'application/pdf') {
        // Use object tag for better PDF support
        const pdfObject = document.createElement('object');
        pdfObject.data = url;
        pdfObject.type = 'application/pdf';
        pdfObject.style.width = '100%';
        pdfObject.style.height = '100%';
        pdfObject.style.border = 'none';

        // Add fallback content
        pdfObject.innerHTML = `
            <p>Your browser cannot display PDFs directly.
            <a href="${url}" target="_blank" style="color: var(--primary);">Click here to open the PDF</a></p>
        `;

        // If object fails, try embed as fallback
        pdfObject.onerror = () => {
            console.warn('Object failed, trying embed');
            const embed = document.createElement('embed');
            embed.src = url;
            embed.type = 'application/pdf';
            embed.style.width = '100%';
            embed.style.height = '100%';
            embed.style.border = 'none';
            originalViewer.innerHTML = '';
            originalViewer.appendChild(embed);
        };

        originalViewer.appendChild(pdfObject);
    } else if (content_type.includes('word') || content_type.includes('document')) {
        // For DOCX files, show download link since browsers can't display them natively
        const container = document.createElement('div');
        container.style.textAlign = 'center';
        container.style.padding = '20px';

        const icon = document.createElement('div');
        icon.textContent = '📄';
        icon.style.fontSize = '48px';
        icon.style.marginBottom = '16px';

        const message = document.createElement('p');
        message.textContent = 'DOCX file uploaded';
        message.style.marginBottom = '16px';
        message.style.color = 'var(--muted)';

        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = currentFileName;
        downloadLink.textContent = 'Download Original';
        downloadLink.style.display = 'inline-block';
        downloadLink.style.padding = '8px 16px';
        downloadLink.style.background = 'var(--primary)';
        downloadLink.style.color = 'white';
        downloadLink.style.borderRadius = '6px';
        downloadLink.style.textDecoration = 'none';

        container.appendChild(icon);
        container.appendChild(message);
        container.appendChild(downloadLink);
        originalViewer.appendChild(container);
    } else {
        // For other file types, show a generic message with download link
        const container = document.createElement('div');
        container.style.textAlign = 'center';
        container.style.padding = '20px';

        const icon = document.createElement('div');
        icon.textContent = '📄';
        icon.style.fontSize = '48px';
        icon.style.marginBottom = '16px';

        const message = document.createElement('p');
        message.textContent = `File: ${currentFileName}`;
        message.style.marginBottom = '16px';
        message.style.color = 'var(--muted)';

        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = currentFileName;
        downloadLink.textContent = 'Download Original';
        downloadLink.style.display = 'inline-block';
        downloadLink.style.padding = '8px 16px';
        downloadLink.style.background = 'var(--primary)';
        downloadLink.style.color = 'white';
        downloadLink.style.borderRadius = '6px';
        downloadLink.style.textDecoration = 'none';

        container.appendChild(icon);
        container.appendChild(message);
        container.appendChild(downloadLink);
        originalViewer.appendChild(container);
    }
}

function displayOutput() {
    const outputContent = document.getElementById('outputContent');
    if (!outputContent) return;
    if (isPreview) {
        outputContent.innerHTML = marked.parse(currentMarkdown || '');
        outputContent.classList.remove('markdown-raw');
        outputContent.classList.add('markdown-preview');
    } else {
        outputContent.textContent = currentMarkdown || '';
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
    const selectedFile = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const convertBtn = document.getElementById('convertBtn');
    const loading = document.getElementById('loading');
    const outputSection = document.getElementById('outputSection');
    const toggleSwitch = document.getElementById('toggleSwitch');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorMessage = document.getElementById('errorMessage');

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
        currentFileName = file?.name || '';
        currentOriginalFile = null;
        if (fileName) fileName.textContent = currentFileName;
        selectedFile?.classList.add('show');
        if (convertBtn) convertBtn.disabled = false;
        outputSection?.classList.remove('show');
        errorMessage?.classList.remove('show');
    }

    convertBtn?.addEventListener('click', async () => {
        const file = fileInput?.files?.[0];
        if (!file) return;

        if (convertBtn) convertBtn.disabled = true;
        loading?.classList.add('show');
        outputSection?.classList.remove('show');
        errorMessage?.classList.remove('show');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/convert', { method: 'POST', body: formData });
            const data = await response.json();
            if (response.ok) {
                currentMarkdown = data.markdown || '';
                currentOriginalFile = data.original_file || null;
                displayOriginalDocument();
                displayOutput();
                outputSection?.classList.add('show');
                // Auto scroll to the output and to the bottom of its content
                requestAnimationFrame(() => {
                    outputSection?.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    const outputContentEl = document.getElementById('outputContent');
                    if (outputContentEl) {
                        outputContentEl.scrollTo({ top: outputContentEl.scrollHeight, behavior: 'smooth' });
                    }
                });
            } else {
                throw new Error(data.detail || 'Conversion failed');
            }
        } catch (error) {
            if (errorMessage) {
                errorMessage.textContent = 'Error: ' + (error?.message || error);
                errorMessage.classList.add('show');
            }
        } finally {
            loading?.classList.remove('show');
            if (convertBtn) convertBtn.disabled = false;
        }
    });

    toggleSwitch?.addEventListener('click', () => {
        isPreview = !isPreview;
        toggleSwitch.classList.toggle('active');
        toggleSwitch.setAttribute('aria-pressed', String(isPreview));
        displayOutput();
    });

    downloadBtn?.addEventListener('click', () => {
        const blob = new Blob([currentMarkdown || ''], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const base = currentFileName?.replace(/\.[^/.]+$/, '') || 'document';
        a.download = base + '.md';
        a.click();
        URL.revokeObjectURL(url);
    });
});


