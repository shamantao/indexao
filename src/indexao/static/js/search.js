// Indexao - Search Page

let searchResults = [];

function performSearch(event) {
    if (event) event.preventDefault();
    
    const query = document.getElementById('searchQuery').value.trim();
    
    if (!query) {
        alert('Veuillez entrer un terme de recherche');
        return;
    }
    
    // Show loading
    const resultsCard = document.getElementById('resultsCard');
    const searchResults = document.getElementById('searchResults');
    
    resultsCard.style.display = 'block';
    searchResults.innerHTML = '<p style="color: var(--text-secondary);"><i class="fas fa-spinner fa-spin"></i> Recherche en cours...</p>';
    
    // Perform search
    searchDocuments(query);
}

async function searchDocuments(query) {
    try {
        const status = document.getElementById('searchStatus').value;
        const searchContent = document.getElementById('searchContent').checked;
        const searchTranslations = document.getElementById('searchTranslations').checked;
        const searchFilenames = document.getElementById('searchFilenames').checked;
        
        // Get all documents (in real implementation, this would be a search API)
        const url = status 
            ? `/api/documents?status=${status}&limit=100`
            : '/api/documents?limit=100';
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'success') {
            // Filter documents client-side (mock search)
            const queryLower = query.toLowerCase();
            const results = data.documents.filter(doc => {
                let match = false;
                
                // Search in content
                if (searchContent && doc.content_preview) {
                    match = match || doc.content_preview.toLowerCase().includes(queryLower);
                }
                
                // Search in translations
                if (searchTranslations && doc.translations) {
                    for (const text of Object.values(doc.translations)) {
                        match = match || text.toLowerCase().includes(queryLower);
                    }
                }
                
                // Search in filename
                if (searchFilenames && doc.title) {
                    match = match || doc.title.toLowerCase().includes(queryLower);
                }
                
                return match;
            });
            
            displayResults(results, query);
        }
    } catch (error) {
        const searchResults = document.getElementById('searchResults');
        searchResults.innerHTML = `
            <p style="color: var(--accent-danger);">
                <i class="fas fa-exclamation-triangle"></i>
                Erreur: ${error.message}
            </p>
        `;
    }
}

function displayResults(results, query) {
    const resultsDiv = document.getElementById('searchResults');
    const resultsCount = document.getElementById('resultsCount');
    
    resultsCount.textContent = `(${results.length} résultat${results.length > 1 ? 's' : ''})`;
    
    if (results.length === 0) {
        resultsDiv.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <i class="fas fa-inbox" style="font-size: 3em; color: var(--text-secondary); margin-bottom: 1rem;"></i>
                <p style="color: var(--text-secondary);">Aucun résultat trouvé pour "${query}"</p>
            </div>
        `;
        return;
    }
    
    searchResults = results;
    
    resultsDiv.innerHTML = results.map(doc => `
        <div class="search-result-item" onclick="showDocumentDetails('${doc.doc_id}')">
            <div class="result-header">
                <div class="result-title">
                    <i class="fas ${getFileIcon(doc.metadata?.mime_type)}"></i>
                    <span>${highlightText(doc.title || doc.doc_id, query)}</span>
                </div>
                ${getStatusBadge(doc.status)}
            </div>
            
            <div class="result-preview">
                ${highlightText(doc.content_preview || 'Aucun contenu', query)}
            </div>
            
            ${doc.translations && Object.keys(doc.translations).length > 0 ? `
                <div class="result-translations">
                    <i class="fas fa-language"></i>
                    ${Object.entries(doc.translations).map(([lang, text]) => {
                        const preview = text.substring(0, 100);
                        return `<div><strong>${lang.toUpperCase()}:</strong> ${highlightText(preview, query)}${text.length > 100 ? '...' : ''}</div>`;
                    }).join('')}
                </div>
            ` : ''}
            
            <div class="result-meta">
                <span>
                    <i class="fas fa-calendar"></i>
                    ${formatDate(doc.created_at)}
                </span>
                <span>
                    <i class="fas fa-file-alt"></i>
                    ${doc.metadata?.file_size ? formatBytes(doc.metadata.file_size) : 'N/A'}
                </span>
                ${doc.indexed ? '<span class="badge badge-success"><i class="fas fa-check"></i> Indexé</span>' : ''}
            </div>
        </div>
    `).join('');
}

function highlightText(text, query) {
    if (!text || !query) return text || '';
    
    const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function searchExample(query) {
    document.getElementById('searchQuery').value = query;
    performSearch();
}

function clearSearch() {
    document.getElementById('searchQuery').value = '';
    document.getElementById('resultsCard').style.display = 'none';
    searchResults = [];
}

function getStatusBadge(status) {
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

// Document details modal (reuse from documents.js)
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
                    ${getStatusBadge(doc.status)}
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
                            <td>Indexé</td>
                            <td>${doc.indexed ? `<span class="badge badge-success"><i class="fas fa-check"></i> Oui (${doc.search_engine})</span>` : '<span class="badge badge-secondary">Non</span>'}</td>
                        </tr>
                    </table>
                </div>
                
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
