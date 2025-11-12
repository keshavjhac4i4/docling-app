const state = Object.seal({
    markdown: '',
    fileName: '',
    originalFile: null,
    json: null,
    report: null,
    isPreview: false
});

const VIEW = Object.freeze({ markdown: 'markdown', json: 'json' });

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

function displayJsonOutput() {
    const jsonOutput = document.getElementById('jsonOutput');
    const jsonReportInfo = document.getElementById('jsonReportInfo');
    const jsonContent = document.getElementById('jsonContent');
    const tabJson = document.getElementById('tabJson');
    const tabPanelJson = document.getElementById('tabPanelJson');
    const copyJsonBtnEl = document.getElementById('copyJsonBtn');
    const downloadJsonBtnEl = document.getElementById('downloadJsonBtn');

    if (!jsonOutput) return;

    if (!state.json) {
        jsonOutput.classList.remove('show');
        tabJson?.setAttribute('aria-disabled', 'true');
        tabJson?.classList.add('disabled');
        tabPanelJson?.classList.remove('has-data');
        if (jsonContent) jsonContent.textContent = '';
        if (jsonReportInfo) jsonReportInfo.textContent = '';
        if (copyJsonBtnEl) copyJsonBtnEl.disabled = true;
        if (downloadJsonBtnEl) downloadJsonBtnEl.disabled = true;
        return;
    }

    jsonOutput.classList.add('show');
    tabJson?.removeAttribute('aria-disabled');
    tabJson?.classList.remove('disabled');
    tabPanelJson?.classList.add('has-data');
    if (jsonContent) jsonContent.textContent = JSON.stringify(state.json, null, 2);
    if (jsonReportInfo) {
        const { report } = state;
        if (report?.name) {
            jsonReportInfo.textContent = `${report.name}${typeof report.score === 'number' ? ` • score ${report.score.toFixed(2)}` : ''}`;
        } else {
            jsonReportInfo.textContent = '';
        }
    }
    if (copyJsonBtnEl) copyJsonBtnEl.disabled = false;
    if (downloadJsonBtnEl) downloadJsonBtnEl.disabled = false;
}

function setActiveTab(view) {
    const tabMarkdown = document.getElementById('tabMarkdown');
    const tabJson = document.getElementById('tabJson');
    const panelMarkdown = document.getElementById('tabPanelMarkdown');
    const panelJson = document.getElementById('tabPanelJson');

    const isMarkdown = view === VIEW.markdown;

    tabMarkdown?.classList.toggle('active', isMarkdown);
    tabMarkdown?.setAttribute('aria-selected', String(isMarkdown));
    panelMarkdown?.classList.toggle('active', isMarkdown);
    panelMarkdown?.setAttribute('aria-hidden', String(!isMarkdown));

    const hasJsonData = Boolean(state.json);
    const jsonActive = !isMarkdown && hasJsonData;
    tabJson?.classList.toggle('active', jsonActive);
    tabJson?.setAttribute('aria-selected', String(jsonActive));
    panelJson?.classList.toggle('active', jsonActive);
    panelJson?.setAttribute('aria-hidden', String(!jsonActive));
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
    const reportSelect = document.getElementById('reportSelect');
    const convertBtn = document.getElementById('convertBtn');
    const loading = document.getElementById('loading');
    const loadingFileName = document.getElementById('loadingFileName');
    const outputSection = document.getElementById('outputSection');
    const toggleSwitch = document.getElementById('toggleSwitch');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorMessage = document.getElementById('errorMessage');
    const copyJsonBtn = document.getElementById('copyJsonBtn');
    const downloadJsonBtn = document.getElementById('downloadJsonBtn');
    const tabMarkdown = document.getElementById('tabMarkdown');
    const tabJson = document.getElementById('tabJson');

    const setLoadingState = (isLoading) => {
        loading?.classList.toggle('show', isLoading);
        if (convertBtn) convertBtn.disabled = isLoading;
        if (isLoading && loadingFileName) {
            loadingFileName.textContent = state.fileName;
        }
        if (uploadFilename) {
            if (isLoading) {
                uploadFilename.classList.remove('show');
            } else if (state.fileName) {
                uploadFilename.textContent = state.fileName;
                uploadFilename.classList.add('show');
            }
        }
    };

    const setOutputVisibility = (isVisible) => {
        outputSection?.classList.toggle('show', isVisible);
    };

    const showError = (message, detail) => {
        if (!errorMessage) return;
        clearElement(errorMessage);

        if (message) {
            const messageEl = document.createElement('p');
            messageEl.textContent = message;
            errorMessage.appendChild(messageEl);
        }

        const candidates = detail?.candidates;
        if (Array.isArray(candidates) && candidates.length > 0) {
            const wrapper = document.createElement('div');
            wrapper.className = 'report-candidate-list';

            const hint = document.createElement('p');
            hint.className = 'candidate-hint';
            hint.textContent = 'Select a report type:';
            wrapper.appendChild(hint);

            const buttonRow = document.createElement('div');
            buttonRow.className = 'candidate-button-row';

            candidates.forEach((candidate) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'candidate-btn';
                button.textContent = candidate.name || candidate.id;
                button.addEventListener('click', () => {
                    if (reportSelect) {
                        reportSelect.value = candidate.id || '';
                    }
                    showError(`Selected ${candidate.name || candidate.id}. Click "Convert to Markdown" to continue.`);
                });
                buttonRow.appendChild(button);
            });

            wrapper.appendChild(buttonRow);
            errorMessage.appendChild(wrapper);
        }

        errorMessage.classList.add('show');
    };

    const clearError = () => {
        if (!errorMessage) return;
        clearElement(errorMessage);
        errorMessage.classList.remove('show');
    };

    async function fetchReports() {
        if (!reportSelect) return;
        try {
            const response = await fetch('/reports');
            const data = await response.json();
            const reports = Array.isArray(data?.reports) ? data.reports : [];
            reports.forEach((report) => {
                if (!report?.id) return;
                const option = document.createElement('option');
                option.value = report.id;
                option.textContent = report.name || report.id;
                reportSelect.appendChild(option);
            });
        } catch (error) {
            console.warn('Failed to load report list', error);
        }
    }

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
        state.json = null;
        state.report = null;
        setOutputVisibility(false);
        clearError();
        displayOriginalDocument();
        displayJsonOutput();
        if (convertBtn) convertBtn.disabled = false;
        setActiveTab(VIEW.markdown);
        
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
        state.json = null;
        state.report = null;
        displayJsonOutput();
        setActiveTab(VIEW.markdown);

        const formData = new FormData();
        formData.append('file', file);
        if (reportSelect && reportSelect.value) {
            formData.append('report_id', reportSelect.value);
        }

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
                const detectionInfo = data.report_detection;
                state.json = data.json || null;
                state.report = data.report || null;
                if (!reportSelect?.value && state.report?.id) {
                    reportSelect.value = state.report.id;
                }
                clearError();
                displayOriginalDocument();
                displayOutput();
                displayJsonOutput();
                setOutputVisibility(true);
                if (state.json) {
                    setActiveTab(VIEW.json);
                } else {
                    setActiveTab(VIEW.markdown);
                }
                if (detectionInfo?.message || (Array.isArray(detectionInfo?.candidates) && detectionInfo.candidates.length > 0)) {
                    showError(
                        detectionInfo.message || 'JSON conversion is not available for this document.',
                        detectionInfo
                    );
                }
                // Auto scroll to the output and to the bottom of its content
                requestAnimationFrame(() => {
                    outputSection?.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    const outputContentEl = document.getElementById('outputContent');
                    if (outputContentEl) {
                        outputContentEl.scrollTo({ top: outputContentEl.scrollHeight, behavior: 'smooth' });
                    }
                });
            } else {
                const message = typeof data?.detail === 'string'
                    ? data.detail
                    : data?.detail?.message || 'Conversion failed';
                const error = new Error(message);
                error.detail = data?.detail;
                error.status = response.status;
                throw error;
            }
        } catch (error) {
            state.json = null;
            state.report = null;
            displayJsonOutput();
            if (error?.detail?.candidates) {
                showError(error.detail.message || 'Multiple matching report types found.', error.detail);
            } else {
                showError('Error: ' + (error?.message || error));
            }
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

    copyJsonBtn?.addEventListener('click', async () => {
        if (!state.json) return;
        const text = JSON.stringify(state.json, null, 2);
        try {
            await navigator.clipboard.writeText(text);
            const originalLabel = copyJsonBtn.textContent;
            copyJsonBtn.textContent = 'Copied!';
            setTimeout(() => {
                copyJsonBtn.textContent = originalLabel || 'Copy JSON';
            }, 2000);
        } catch (err) {
            console.warn('Failed to copy JSON', err);
            showError('Unable to copy JSON to clipboard.');
        }
    });

    downloadJsonBtn?.addEventListener('click', async () => {
        if (!state.json) return;
        try {
            const response = await fetch('/convert/json-binary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ json: state.json })
            });
            if (!response.ok) {
                throw new Error('Failed to download JSON');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const base = state.fileName?.replace(/\.[^/.]+$/, '') || 'document';
            a.download = `${base}.pickle`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.warn('Failed to download JSON binary', err);
            showError('Unable to download JSON binary.');
        }
    });

    reportSelect?.addEventListener('change', () => {
        clearError();
    });

    tabMarkdown?.addEventListener('click', () => {
        setActiveTab(VIEW.markdown);
    });

    tabJson?.addEventListener('click', () => {
        if (!state.json) return;
        setActiveTab(VIEW.json);
    });

    fetchReports();

    displayOriginalDocument();
    displayOutput();
    displayJsonOutput();
    setActiveTab(VIEW.markdown);
});


