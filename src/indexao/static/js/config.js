function configManager() {
    return {
        activeTab: 'indexao',
        loading: false,
        indexes: [],
        showCreateModal: false,
        // Browser state
        showBrowserModal: false,
        browserPath: '',
        browserItems: [],
        browserLoading: false,

        config: {},

        newIndex: {
            uid: '',
            primaryKey: ''
        },
        
        async init() {
            await this.loadConfig();
            await this.loadCloudVolumes();
            // Preload indexes for dropdown
            if (this.activeTab === 'meilisearch' || this.showAddVolumeModal) {
                this.loadMeiliIndexes(); 
            }
        },

        async loadConfig() {
            try {
                const response = await fetch('/api/config');
                if (response.ok) {
                    this.config = await response.json();
                }
            } catch (error) {
                console.error('Error loading config:', error);
            }
        },
        
        // Cloud volumes management
        loadingVolumes: false,
        cloudVolumes: [],
        showAddVolumeModal: false,
        newVolume: {
            name: '',
            mount_path: '',
            index_name: '',
            file_patterns: '*.pdf,*.doc,*.docx,*.txt,*.md'
        },

        async loadMeiliIndexes() {
            if (this.indexes.length > 0) return; // Already loaded
            
            this.loading = true;
            try {
                const response = await fetch('/api/meilisearch/indexes');
                const data = await response.json();
                this.indexes = data.results || [];
            } catch (error) {
                console.error('Error loading indexes:', error);
                showAlert('Erreur lors du chargement des index', 'error');
            } finally {
                this.loading = false;
            }
        },

        async createIndex() {
            try {
                const response = await fetch('/api/meilisearch/indexes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.newIndex)
                });

                if (!response.ok) throw new Error('Failed to create index');

                const data = await response.json();
                showAlert('Index créé avec succès', 'success');
                
                // Store created index UID
                const createdUid = this.newIndex.uid;
                
                this.showCreateModal = false;
                this.newIndex = { uid: '', primaryKey: '' };
                this.indexes = []; // Force reload
                await this.loadMeiliIndexes();
                
                // If we were adding a volume, pre-select the new index
                if (this.showAddVolumeModal) {
                    this.newVolume.index_name = createdUid;
                }
            } catch (error) {
                console.error('Error creating index:', error);
                showAlert('Erreur lors de la création de l\'index', 'error');
            }
        },

        async deleteIndex(uid) {
            if (!confirm(`Êtes-vous sûr de vouloir supprimer l'index "${uid}" ?`)) return;

            try {
                const response = await fetch(`/api/meilisearch/indexes/${uid}`, {
                    method: 'DELETE'
                });

                if (!response.ok) throw new Error('Failed to delete index');

                showAlert('Index supprimé avec succès', 'success');
                this.indexes = this.indexes.filter(idx => idx.uid !== uid);
            } catch (error) {
                console.error('Error deleting index:', error);
                showAlert('Erreur lors de la suppression de l\'index', 'error');
            }
        },

        configureIndex(uid) {
            // TODO: Open configuration modal
            showAlert('Configuration de l\'index à venir', 'info');
        },
        
        // Cloud volumes functions
        async loadCloudVolumes() {
            this.loadingVolumes = true;
            try {
                const response = await fetch('/api/cloud/volumes');
                const data = await response.json();
                this.cloudVolumes = data.volumes || [];
            } catch (error) {
                console.error('Error loading cloud volumes:', error);
                showAlert('Erreur lors du chargement des volumes cloud', 'error');
            } finally {
                this.loadingVolumes = false;
            }
        },
        
        async addVolume() {
            if (!this.newVolume.name || !this.newVolume.mount_path) {
                showAlert('Le nom et le chemin sont requis', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/cloud/volumes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.newVolume)
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to add volume');
                }

                const data = await response.json();
                showAlert('Volume ajouté avec succès', 'success');
                this.showAddVolumeModal = false;
                this.newVolume = { name: '', mount_path: '', index_name: '', file_patterns: '*.pdf,*.doc,*.docx,*.txt,*.md' };
                await this.loadCloudVolumes();
            } catch (error) {
                console.error('Error adding volume:', error);
                showAlert(error.message || 'Erreur lors de l\'ajout du volume', 'error');
            }
        },
        
        async scanVolume(name) {
            try {
                const response = await fetch(`/api/cloud/volumes/${name}/scan`, {
                    method: 'POST'
                });

                if (!response.ok) throw new Error('Failed to start scan');

                const data = await response.json();
                
                if (data.status === 'already_running') {
                    showAlert('Un scan est déjà en cours pour ce volume', 'warning');
                } else if (data.status === 'started') {
                    showAlert('Scan démarré en arrière-plan. Rechargement automatique toutes les 5s...', 'success');
                    
                    // Poll status every 5 seconds
                    this.pollScanStatus(name);
                }
                
                // Reload volumes immediately to show initial state
                this.loadCloudVolumes();
            } catch (error) {
                console.error('Error scanning volume:', error);
                showAlert('Erreur lors du lancement du scan', 'error');
            }
        },
        
        async pollScanStatus(name) {
            const interval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/cloud/volumes/${name}/scan/status`);
                    const data = await response.json();
                    
                    if (data.status === 'completed') {
                        clearInterval(interval);
                        showAlert(`Scan terminé pour ${name}!`, 'success');
                        this.loadCloudVolumes();
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        showAlert(`Erreur lors du scan: ${data.error}`, 'error');
                        this.loadCloudVolumes();
                    } else if (data.status === 'running') {
                        // Update UI with progress if available
                        this.loadCloudVolumes();
                    }
                } catch (error) {
                    console.error('Error polling scan status:', error);
                    clearInterval(interval);
                }
            }, 5000); // Poll every 5 seconds
        },
        
        async deleteVolume(name) {
            if (!confirm(`Êtes-vous sûr de vouloir supprimer le volume "${name}" ?`)) return;

            try {
                const response = await fetch(`/api/cloud/volumes/${name}`, {
                    method: 'DELETE'
                });

                if (!response.ok) throw new Error('Failed to delete volume');

                showAlert('Volume supprimé avec succès', 'success');
                this.cloudVolumes = this.cloudVolumes.filter(v => v.name !== name);
            } catch (error) {
                console.error('Error deleting volume:', error);
                showAlert('Erreur lors de la suppression du volume', 'error');
            }
        },

        // File Browser Logic
        async openBrowser(initialPath) {
            this.showBrowserModal = true;
            await this.browse(initialPath || '');
        },

        async browse(path) {
            this.browserLoading = true;
            try {
                const encodedPath = encodeURIComponent(path);
                const response = await fetch(`/api/system/browse?path=${encodedPath}`);
                if (!response.ok) throw new Error('Failed to list directory');
                
                const data = await response.json();
                this.browserPath = data.current;
                this.browserItems = data.items;
            } catch (error) {
                console.error('Browse error:', error);
                showAlert('Erreur de navigation: ' + error.message, 'error');
                // If path invalid, go home
                if (path !== '') await this.browse('');
            } finally {
                this.browserLoading = false;
            }
        },

        selectPath() {
            this.newVolume.mount_path = this.browserPath;
            this.showBrowserModal = false;
        }
    };
}
