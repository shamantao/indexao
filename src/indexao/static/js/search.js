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
        const language = document.getElementById('searchLanguage') ? document.getElementById('searchLanguage').value : '';
        const limit = document.getElementById('searchLimit') ? parseInt(document.getElementById('searchLimit').value) : 25;
        
        // Build query parameters
        const params = new URLSearchParams({ query, limit });
        if (language) {
            params.append('language', language);
        }
        
        // Call real Meilisearch API
        const response = await fetch(`/api/search?${params.toString()}`);
        
        if (!response.ok) {
            throw new Error(`Search failed: ${response.statusText}`);
        }
        
        const results = await response.json();
        
        displayResults(results, query);
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
    
    // Render Meilisearch results
    resultsDiv.innerHTML = results.map(doc => {
        // Get language flag
        const langFlag = doc.language === 'fr' ? '🇫🇷' : 
                        doc.language === 'en' ? '🇬🇧' : 
                        doc.language === 'zh-TW' ? '🇹🇼' : '🌍';
        
        // Format score (Meilisearch uses 0-1 scale)
        const score = doc._score ? `${(doc._score * 100).toFixed(0)}%` : 'N/A';
        
        // Extract metadata
        const metadata = doc.metadata || {};
        const contentPreview = doc.content ? doc.content.substring(0, 200) + '...' : 'Aucun contenu';
        
        return `
            <div class="search-result-item" onclick="viewDocument('${doc.doc_id}')">
                <div class="result-header">
                    <div class="result-title">
                        ${langFlag}
                        <i class="fas ${getFileIcon(metadata.mime_type)}"></i>
                        <span>${highlightText(doc.title || doc.doc_id, query)}</span>
                    </div>
                    <span class="result-score" title="Score de pertinence">${score}</span>
                </div>
                
                <div class="result-preview">
                    ${highlightText(contentPreview, query)}
                </div>
                
                <div class="result-meta">
                    <span>
                        <i class="fas fa-file-alt"></i>
                        ${metadata.file_extension || 'N/A'}
                    </span>
                    <span>
                        <i class="fas fa-hdd"></i>
                        ${metadata.file_size ? formatBytes(metadata.file_size) : 'N/A'}
                    </span>
                    ${metadata.pages ? `
                        <span>
                            <i class="fas fa-file-pdf"></i>
                            ${metadata.pages} page${metadata.pages > 1 ? 's' : ''}
                        </span>
                    ` : ''}
                    ${metadata.ocr_confidence ? `
                        <span title="Confiance OCR">
                            <i class="fas fa-eye"></i>
                            ${(metadata.ocr_confidence * 100).toFixed(0)}%
                        </span>
                    ` : ''}
                    <button onclick="event.stopPropagation(); copyDocumentText('${doc.doc_id}')" 
                            class="btn-sm btn-secondary" 
                            title="Copier le texte">
                        <i class="fas fa-copy"></i> Copier
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// Copy document text to clipboard
async function copyDocumentText(docId) {
    try {
        const response = await fetch(`/api/search/document/${docId}`);
        const doc = await response.json();
        
        await navigator.clipboard.writeText(doc.content || '');
        
        // Visual feedback
        alert('✅ Texte copié dans le presse-papier');
    } catch (error) {
        console.error('Failed to copy:', error);
        alert('❌ Erreur lors de la copie');
    }
}

// View document details
function viewDocument(docId) {
    window.location.href = `/documents?id=${docId}`;
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
