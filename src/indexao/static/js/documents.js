// Indexao - Documents Page

let currentPage = 0;
const pageSize = 20;
let currentFilter = '';
let allDocuments = [];

// Load documents on page load
window.addEventListener('DOMContentLoaded', () => {
    loadStatistics();
    loadDocuments();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadStatistics();
        loadDocuments();
    }, 30000);
});

async function loadStatistics() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.status === 'success') {
            const stats = data.documents;
            
            document.getElementById('statTotal').innerHTML = `
                <i class="fas fa-file"></i>
                ${stats.total}
            `;
            
            document.getElementById('statCompleted').innerHTML = `
                <i class="fas fa-check-circle"></i>
                ${stats.completed}
            `;
            
            document.getElementById('statFailed').innerHTML = `
                <i class="fas fa-times-circle"></i>
                ${stats.failed}
            `;
            
            document.getElementById('statSuccess').innerHTML = `
                <i class="fas fa-percentage"></i>
                ${stats.success_rate}%
            `;
        }
    } catch (error) {
        console.error('Failed to load statistics:', error);
    }
}

async function loadDocuments() {
    try {
        const filter = document.getElementById('statusFilter').value;
        const url = filter 
            ? `/api/documents?status=${filter}&limit=100`
            : '/api/documents?limit=100';
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'success') {
            allDocuments = data.documents;
            currentPage = 0;
            displayDocuments();
        }
    } catch (error) {
        const list = document.getElementById('documentsList');
        list.innerHTML = `
            <p style="color: var(--accent-danger);">
                <i class="fas fa-exclamation-triangle"></i>
                Erreur de chargement: ${error.message}
            </p>
        `;
    }
}

function displayDocuments() {
    const list = document.getElementById('documentsList');
    const docCount = document.getElementById('docCount');
    
    if (allDocuments.length === 0) {
        list.innerHTML = `
            <p style="color: var(--text-secondary);">
                <i class="fas fa-inbox"></i>
                Aucun document trouvé
            </p>
        `;
        docCount.textContent = '';
        document.getElementById('pagination').style.display = 'none';
        return;
    }
    
    // Pagination
    const start = currentPage * pageSize;
    const end = start + pageSize;
    const pageDocuments = allDocuments.slice(start, end);
    
    docCount.textContent = `(${allDocuments.length})`;
    
    // Display documents
    list.innerHTML = pageDocuments.map(doc => `
        <div class="document-item" onclick="showDocumentDetails('${doc.doc_id}')">
            <div class="document-header">
                <div class="document-title">
                    <i class="fas ${getFileIcon(doc.metadata?.mime_type)}"></i>
                    <span>${doc.title || doc.doc_id}</span>
                </div>
                ${getStatusBadge(doc.status, doc.current_stage)}
            </div>
            
            <div class="document-meta">
                <span>
                    <i class="fas fa-calendar"></i>
                    ${formatDate(doc.created_at)}
                </span>
                <span>
                    <i class="fas fa-file-alt"></i>
                    ${doc.metadata?.file_size ? formatBytes(doc.metadata.file_size) : 'N/A'}
                </span>
                <span>
                    <i class="fas fa-clock"></i>
                    ${doc.metadata?.processing_duration ? doc.metadata.processing_duration.toFixed(3) + 's' : 'N/A'}
                </span>
                ${doc.indexed ? '<span class="badge badge-success"><i class="fas fa-check"></i> Indexé</span>' : ''}
            </div>
            
            <div class="document-preview">
                ${doc.content_preview || 'Aucun contenu'}
            </div>
            
            ${doc.translations && Object.keys(doc.translations).length > 0 ? `
                <div class="document-translations">
                    <i class="fas fa-language"></i>
                    Traductions: ${Object.keys(doc.translations).join(', ').toUpperCase()}
                </div>
            ` : ''}
        </div>
    `).join('');
    
    // Update pagination
    updatePagination();
}

function updatePagination() {
    const pagination = document.getElementById('pagination');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');
    
    const totalPages = Math.ceil(allDocuments.length / pageSize);
    
    if (totalPages <= 1) {
        pagination.style.display = 'none';
        return;
    }
    
    pagination.style.display = 'block';
    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = currentPage >= totalPages - 1;
    
    pageInfo.textContent = `Page ${currentPage + 1} / ${totalPages}`;
}

function prevPage() {
    if (currentPage > 0) {
        currentPage--;
        displayDocuments();
        window.scrollTo(0, 0);
    }
}

function nextPage() {
    const totalPages = Math.ceil(allDocuments.length / pageSize);
    if (currentPage < totalPages - 1) {
        currentPage++;
        displayDocuments();
        window.scrollTo(0, 0);
    }
}

function filterDocuments() {
    loadDocuments();
}

function getStatusBadge(status, stage) {
    const badges = {
        'pending': '<span class="status-badge status-pending"><i class="fas fa-clock"></i> En attente</span>',
        'processing': '<span class="status-badge status-processing"><i class="fas fa-spinner fa-spin"></i> Traitement</span>',
        'completed': '<span class="status-badge status-completed"><i class="fas fa-check-circle"></i> Complété</span>',
        'failed': '<span class="status-badge status-failed"><i class="fas fa-times-circle"></i> Échoué</span>'
    };
    
    return badges[status] || badges['pending'];
}

function getFileIcon(mimeType) {
    if (!mimeType) return 'fa-file';
    
    if (mimeType.startsWith('image/')) return 'fa-file-image';
    if (mimeType.startsWith('text/')) return 'fa-file-alt';
    if (mimeType.includes('pdf')) return 'fa-file-pdf';
    if (mimeType.includes('word')) return 'fa-file-word';
    
    return 'fa-file';
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
    return date.toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

async function showDocumentDetails(docId) {
    try {
        const response = await fetch(`/api/documents/${docId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            const doc = data.document;
            
            document.getElementById('modalTitle').innerHTML = `
                <i class="fas ${getFileIcon(doc.metadata?.mime_type)}"></i>
                ${doc.title || doc.doc_id}
            `;
            
            const modalBody = document.getElementById('modalBody');
            modalBody.innerHTML = `
                <div style="margin-bottom: 1rem;">
                    ${getStatusBadge(doc.status, doc.current_stage)}
                </div>
                
                <div class="detail-section">
                    <h4><i class="fas fa-info-circle"></i> Informations</h4>
                    <table class="detail-table">
                        <tr>
                            <td>Document ID</td>
                            <td><code>${doc.doc_id}</code></td>
                        </tr>
                        <tr>
                            <td>Fichier</td>
                            <td>${doc.metadata?.filename || 'N/A'}</td>
                        </tr>
                        <tr>
                            <td>Type MIME</td>
                            <td>${doc.metadata?.mime_type || 'N/A'}</td>
                        </tr>
                        <tr>
                            <td>Taille</td>
                            <td>${doc.metadata?.file_size ? formatBytes(doc.metadata.file_size) : 'N/A'}</td>
                        </tr>
                        <tr>
                            <td>Créé le</td>
                            <td>${formatDate(doc.created_at)}</td>
                        </tr>
                        <tr>
                            <td>Traité le</td>
                            <td>${doc.processed_at ? formatDate(doc.processed_at) : 'N/A'}</td>
                        </tr>
                        <tr>
                            <td>Durée</td>
                            <td>${doc.metadata?.processing_duration ? doc.metadata.processing_duration.toFixed(3) + 's' : 'N/A'}</td>
                        </tr>
                        <tr>
                            <td>Indexé</td>
                            <td>${doc.indexed ? `<span class="badge badge-success"><i class="fas fa-check"></i> Oui (${doc.search_engine})</span>` : '<span class="badge badge-secondary">Non</span>'}</td>
                        </tr>
                    </table>
                </div>
                
                ${doc.metadata?.stages_completed && doc.metadata.stages_completed.length > 0 ? `
                    <div class="detail-section">
                        <h4><i class="fas fa-tasks"></i> Étapes complétées</h4>
                        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            ${doc.metadata.stages_completed.map(stage => 
                                `<span class="badge badge-success">${stage}</span>`
                            ).join('')}
                        </div>
                    </div>
                ` : ''}
                
                <div class="detail-section">
                    <h4><i class="fas fa-align-left"></i> Contenu</h4>
                    <div class="content-box">
                        ${doc.content || 'Aucun contenu'}
                    </div>
                </div>
                
                ${doc.translations && Object.keys(doc.translations).length > 0 ? `
                    <div class="detail-section">
                        <h4><i class="fas fa-language"></i> Traductions</h4>
                        ${Object.entries(doc.translations).map(([lang, text]) => `
                            <div style="margin-bottom: 1rem;">
                                <strong style="color: var(--accent-primary);">${lang.toUpperCase()}:</strong>
                                <div class="content-box" style="margin-top: 0.5rem;">
                                    ${text}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                
                ${doc.error_message ? `
                    <div class="detail-section">
                        <h4 style="color: var(--accent-danger);"><i class="fas fa-exclamation-triangle"></i> Erreur</h4>
                        <div class="content-box" style="background: rgba(244, 67, 54, 0.1); border-color: var(--accent-danger);">
                            ${doc.error_message}
                        </div>
                    </div>
                ` : ''}
            `;
            
            document.getElementById('modal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Failed to load document details:', error);
    }
}

function closeModal(event) {
    if (!event || event.target.id === 'modal') {
        document.getElementById('modal').style.display = 'none';
    }
}
