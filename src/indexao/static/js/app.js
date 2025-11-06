// Indexao - Upload & File Management

// Upload area drag & drop
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');

if (uploadArea && fileInput) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.add('dragover');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.remove('dragover');
        }, false);
    });
    
    uploadArea.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileSelect, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }
    
    function handleFileSelect(e) {
        const files = e.target.files;
        handleFiles(files);
    }
}

async function handleFiles(files) {
    if (files.length === 0) return;
    
    const file = files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    // Show progress UI
    showProgress();
    updateProgress(0, 'Préparation de l\'upload...');
    
    try {
        // Stage 1: Upload
        updateStage('upload', 'active');
        updateProgress(10, 'Upload du fichier...');
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Upload échoué');
        }
        
        updateStage('upload', 'completed');
        updateProgress(30, `Fichier uploadé: ${result.filename}`);
        
        // Stage 2-5: Process document
        const docId = result.document_id;
        await processDocument(docId);
        
    } catch (error) {
        updateProgress(100, `✗ Erreur: ${error.message}`, true);
        showProgressClose();
        showAlert(`✗ ${error.message}`, 'error');
    }
}

async function processDocument(docId) {
    try {
        updateProgress(40, 'Traitement du document...');
        
        // Trigger processing
        const response = await fetch('/api/process', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error('Traitement échoué');
        }
        
        // Find our document in results
        const docResult = result.results.find(r => r.document_id === docId);
        
        if (docResult) {
            // Simulate stage progression
            const stages = ['detection', 'extraction', 'translation', 'indexing'];
            const stagesCompleted = docResult.stages_completed || [];
            
            for (let i = 0; i < stages.length; i++) {
                const stage = stages[i];
                const progress = 50 + (i * 10);
                
                updateStage(stage, 'active');
                updateProgress(progress, `${stage}...`);
                
                await new Promise(resolve => setTimeout(resolve, 300));
                
                if (stagesCompleted.includes(stage.replace('-', '_'))) {
                    updateStage(stage, 'completed');
                }
            }
            
            if (docResult.status === 'completed') {
                updateProgress(100, '✓ Document traité avec succès !');
                showAlert('✓ Document traité avec succès !', 'success');
            } else if (docResult.status === 'failed') {
                throw new Error(docResult.error_message || 'Traitement échoué');
            }
        } else {
            updateProgress(100, '✓ Document uploadé (traitement en attente)');
        }
        
        showProgressClose();
        loadFiles();
        
    } catch (error) {
        updateProgress(100, `✗ ${error.message}`, true);
        showProgressClose();
        showAlert(`✗ ${error.message}`, 'error');
    }
}

function showProgress() {
    const progress = document.getElementById('uploadProgress');
    const stages = document.getElementById('processingStages');
    
    if (progress) {
        progress.style.display = 'block';
        // Reset all stages
        ['upload', 'detection', 'extraction', 'translation', 'indexing'].forEach(stage => {
            const stageEl = document.getElementById(`stage-${stage}`);
            if (stageEl) {
                stageEl.classList.remove('active', 'completed');
                const spinner = stageEl.querySelector('.stage-spinner');
                const check = stageEl.querySelector('.stage-check');
                if (spinner) spinner.style.display = 'none';
                if (check) check.style.display = 'none';
            }
        });
    }
    
    if (stages) stages.style.display = 'flex';
}

function updateProgress(percent, status, isError = false) {
    const fill = document.getElementById('progressFill');
    const percentEl = document.getElementById('progressPercent');
    const statusEl = document.getElementById('progressStatus');
    const title = document.getElementById('progressTitle');
    
    if (fill) fill.style.width = `${percent}%`;
    if (percentEl) percentEl.textContent = `${percent}%`;
    if (statusEl) {
        statusEl.textContent = status;
        statusEl.style.color = isError ? 'var(--accent-danger)' : 'var(--text-secondary)';
    }
    
    if (title && percent === 100) {
        title.textContent = isError ? 'Erreur' : 'Terminé !';
        title.style.color = isError ? 'var(--accent-danger)' : 'var(--accent-secondary)';
    }
}

function updateStage(stageName, status) {
    const stageEl = document.getElementById(`stage-${stageName}`);
    if (!stageEl) return;
    
    const spinner = stageEl.querySelector('.stage-spinner');
    const check = stageEl.querySelector('.stage-check');
    
    // Remove previous states
    stageEl.classList.remove('active', 'completed');
    if (spinner) spinner.style.display = 'none';
    if (check) check.style.display = 'none';
    
    if (status === 'active') {
        stageEl.classList.add('active');
        if (spinner) spinner.style.display = 'inline-block';
    } else if (status === 'completed') {
        stageEl.classList.add('completed');
        if (check) check.style.display = 'inline-block';
    }
}

function showProgressClose() {
    const closeBtn = document.getElementById('progressClose');
    if (closeBtn) closeBtn.style.display = 'block';
}

function closeProgress() {
    const progress = document.getElementById('uploadProgress');
    if (progress) progress.style.display = 'none';
    
    // Reset file input
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';
}

async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const result = await response.json();
        
        const fileList = document.getElementById('fileList');
        
        if (!fileList) return;
        
        if (result.files.length === 0) {
            fileList.innerHTML = '<p style="color: var(--text-secondary);">Aucun fichier uploadé</p>';
            return;
        }
        
        fileList.innerHTML = result.files.map(file => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name">
                        <i class="fas fa-file-alt"></i>
                        ${file.filename}
                        <span class="badge badge-info">${file.extension}</span>
                    </div>
                    <div class="file-meta">
                        ${formatBytes(file.size_bytes)} • ${formatDate(file.modified)}
                    </div>
                </div>
                <span class="badge badge-success">
                    <i class="fas fa-check-circle"></i>
                    Uploaded
                </span>
            </div>
        `).join('');
        
    } catch (error) {
        const fileList = document.getElementById('fileList');
        if (fileList) {
            fileList.innerHTML = 
                `<p style="color: var(--accent-danger);">Erreur: ${error.message}</p>`;
        }
    }
}

function showAlert(message, type) {
    const alert = document.getElementById('alert');
    if (!alert) return;
    
    alert.className = `alert alert-${type} show`;
    alert.textContent = message;
    
    setTimeout(() => {
        alert.classList.remove('show');
    }, 5000);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('fr-FR');
}

// Load files on page load
if (document.getElementById('fileList')) {
    loadFiles();
}
