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
    
    try {
        showAlert('Upload en cours...', 'info');
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(`✓ ${result.message}`, 'success');
            loadFiles();
        } else {
            showAlert(`✗ ${result.detail}`, 'error');
        }
    } catch (error) {
        showAlert(`✗ Upload échoué: ${error.message}`, 'error');
    }
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
