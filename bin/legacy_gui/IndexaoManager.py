#!/usr/bin/env python3
"""
IndexaoManager - Menu Bar App for Meilisearch + Indexao
Simple macOS menu bar application to manage services
"""
import sys
import rumps
import subprocess
import os
import webbrowser
from pathlib import Path

# Ajouter la racine du projet au PATH pour trouver les modules si nécessaire
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'src'))


class IndexaoManager(rumps.App):
    def __init__(self):
        super().__init__(name="Indexao", title="🔍")
        self.meilisearch_script = Path.home() / "pCloudSync/Projets/meilisearch/meilisearch-tao.sh"
        # Détection dynamique via indexao.config
        try:
            from indexao.config import load_config
            # Force reload to ensure we get fresh paths
            self.config = load_config()
            self.indexao_path = project_root
            
            # Use config for all paths
            db_dir = self.config.db_path.parent
            self.throttle_cfg_path = db_dir / "throttling.json"
            self.state_file_path = db_dir / "cloud_indexer_state.json"
            
            # Scripts locations (still relative to project root properly)
            self.docs_script = self.indexao_path / "bin/docs-serve.sh"
            
            print(f"Loaded config: State file at {self.state_file_path}")
        except Exception as e:
            rumps.alert(f"Config Error: {e}")
            sys.exit(1)

        # Références pour fenêtres PyQt6
        self.status_win = None
        self.throttle_win = None
        # Initialiser QApplication pour PyQt6
        self._init_qt_app()
        self.update_status()
        self._ensure_throttle_defaults()
    
    def _init_qt_app(self):
        """Initialise QApplication si PyQt6 disponible"""
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            import sys
            if QApplication.instance() is None:
                self.qt_app = QApplication(sys.argv)
                # Timer pour traiter les événements Qt sans bloquer rumps
                self.qt_timer = QTimer()
                self.qt_timer.timeout.connect(lambda: self.qt_app.processEvents())
                self.qt_timer.start(100)  # Traiter les événements toutes les 100ms
        except ImportError:
            self.qt_app = None

    def _ensure_throttle_defaults(self):
        import json
        if not self.throttle_cfg_path.exists():
            self._save_throttle_config({'batch_size': 100, 'sleep_ms': 1000, 'max_docs_per_minute': 5000})

    def _load_throttle_config(self):
        import json
        try:
            with open(self.throttle_cfg_path) as f:
                return json.load(f)
        except Exception:
            return {'batch_size': 100, 'sleep_ms': 1000, 'max_docs_per_minute': 5000}

    def _save_throttle_config(self, data):
        import json
        try:
            self.throttle_cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.throttle_cfg_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            rumps.alert("Erreur", f"Sauvegarde throttle impossible: {e}")

    @rumps.clicked("Configuration Throttle")
    def configure_throttle(self, _):
        try:
            import sys
            sys.path.insert(0, str(self.indexao_path))
            from throttle_config_window import show_throttle_config
            self.throttle_win = show_throttle_config(str(self.throttle_cfg_path))
        except Exception as e:
            # Fallback vers interface texte si PyQt6 fail
            cfg = self._load_throttle_config()
            current = f"batch_size={cfg['batch_size']}\nsleep_ms={cfg['sleep_ms']}\nmax_docs_per_minute={cfg['max_docs_per_minute']}"
            win = rumps.Window(
                message="Paramètres (format clé=valeur, un par ligne):",
                default_text=current,
                title="Configuration Throttle",
                ok="Enregistrer",
                cancel="Annuler"
            )
            resp = win.run()
            if resp.clicked:
                lines = [l.strip() for l in resp.text.split('\n') if l.strip()]
                new_cfg = {}
                for line in lines:
                    if '=' in line:
                        k,v = line.split('=',1)
                        k = k.strip(); v = v.strip()
                        if v.isdigit():
                            new_cfg[k] = int(v)
                        else:
                            try:
                                new_cfg[k] = int(float(v))
                            except:
                                rumps.alert("Erreur", f"Valeur non numérique pour {k}: {v}")
                                return
                # Validate keys
                for req in ['batch_size','sleep_ms','max_docs_per_minute']:
                    if req not in new_cfg:
                        rumps.alert("Erreur", f"Clé manquante: {req}")
                        return
                self._save_throttle_config(new_cfg)
                rumps.notification("Throttle", "Configuration mise à jour", str(new_cfg))

    @rumps.clicked("Statut détaillé")
    def show_detailed_status(self, _):
        import json
        import psutil
        # PID Meilisearch
        pid = self.get_meilisearch_pid()
        cpu = mem = net_in = net_out = "?"
        net_in_proc = net_out_proc = "?"
        gpu = "N/A (ARM)"
        scan_status = "Aucun scan en cours"
        volume_name = "-"
        progress = "0/0"
        # CPU/MEM/NET
        if pid:
            try:
                p = psutil.Process(pid)
                cpu = f"{p.cpu_percent(interval=0.2):.1f}%"
                mem = f"{p.memory_info().rss/1024/1024:.1f} Mo"
                # Réseau global (pas process, limitation psutil sur macOS)
                net = psutil.net_io_counters()
                net_in = f"{net.bytes_recv/1024/1024:.1f} Mo"
                net_out = f"{net.bytes_sent/1024/1024:.1f} Mo"
                # Réseau par process (tentative via nettop)
                try:
                    import subprocess, re
                    out = subprocess.check_output([
                        "nettop","-P","-p", str(pid),"-J","bytes_in,bytes_out","-l","1"
                    ], text=True, timeout=2)
                    # Cherche deux colonnes de bytes en dernière ligne non vide
                    lines = [ln for ln in out.splitlines() if ln.strip()]
                    if lines:
                        last = lines[-1]
                        nums = re.findall(r"(\d+(?:\.\d+)?\s*[KMG]?B)", last, re.I)
                        if len(nums) >= 2:
                            net_in_proc, net_out_proc = nums[0], nums[1]
                except Exception:
                    pass
            except Exception as e:
                cpu = mem = net_in = net_out = f"Erreur: {e}"
        # Scan/volume depuis state JSON
        try:
            # Use dynamically resolved path
            state_path = self.state_file_path
            
            with open(state_path) as f:
                state = json.load(f)
            vols = state.get("volumes", {})
            for vol_id, v in vols.items():
                total = v.get("total_files", 0)
                indexed = v.get("indexed_files", 0)
                if total > 0:
                    scan_status = "Scan terminé" if indexed >= total else "Scan en cours"
                    volume_name = v.get("name", vol_id)
                    progress = f"{indexed}/{total}"
                    break
        except Exception as e:
            scan_status = f"Aucun scan détecté"
        
        # Queue stats
        queue_stats = self._get_queue_stats()
        
        # Construire dict pour PyQt
        status_data = {
            'meilisearch': '✅ En cours' if self.is_meilisearch_running() else '❌ Arrêté',
            'indexao': '✅ En cours' if self.is_indexao_running() else '❌ Arrêté',
            'scan_status': scan_status,
            'volume_name': volume_name,
            'progress': progress,
            'queue': queue_stats,
            'cpu': cpu,
            'ram': mem,
            'gpu': gpu,
            'net_in_proc': net_in_proc,
            'net_out_proc': net_out_proc,
            'net_in': net_in,
            'net_out': net_out
        }
        
        # Lancer fenêtre PyQt6
        try:
            import sys
            sys.path.insert(0, str(self.indexao_path))
            # Debug: afficher les données
            debug_log = "/tmp/indexao_status_debug.txt"
            with open(debug_log, 'w') as f:
                f.write("=== Données status_data ===\n")
                for k, v in status_data.items():
                    f.write(f"{k}: {v}\n")
            from status_window import show_status_window
            self.status_win = show_status_window(status_data)
        except Exception as e:
            # Fallback vers rumps si PyQt6 fail
            msg = f"""
Meilisearch : {status_data['meilisearch']}
Indexao : {status_data['indexao']}
Scan : {scan_status}
Volume : {volume_name}
Progression : {progress}
CPU : {cpu}
RAM : {mem}
GPU : {gpu}
Queue : pending={queue_stats['pending']} processing={queue_stats['processing']} done={queue_stats['done']} error={queue_stats['error']}
Réseau (Meilisearch) :\n  IN  : {net_in_proc}\n  OUT : {net_out_proc}
Réseau (total machine) :\n  IN  : {net_in}\n  OUT : {net_out}

Erreur PyQt6: {e}
"""
            rumps.alert("Statut détaillé", msg)

    def get_meilisearch_pid(self):
        try:
            out = subprocess.check_output(["pgrep", "-f", "meilisearch"])
            return int(out.decode().strip().split("\n")[0])
        except:
            return None

    def _get_queue_stats(self):
        try:
            import sys
            sys.path.insert(0, str(self.indexao_path))
            from src.indexao.database import DocumentDatabase
            # Use configured path instead of hardcoded
            db = DocumentDatabase(db_path=str(self.config.db_path))
            return db.index_queue_stats()
        except Exception as e:
            return {'total': 0, 'pending': 0, 'processing': 0, 'done': 0, 'error': 0}
    
    def update_status(self):
        """Update menu bar icon based on service status"""
        meili_running = self.is_meilisearch_running()
        indexao_running = self.is_indexao_running()
        
        if meili_running and indexao_running:
            self.title = "🟢"
        elif meili_running or indexao_running:
            self.title = "🟡"
        else:
            self.title = "🔴"
    
    def is_meilisearch_running(self):
        """Check if Meilisearch is running"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "meilisearch"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def is_indexao_running(self):
        """Check if Indexao is running"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "uvicorn.*indexao"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False

    def is_docs_running(self):
        """Check if Documentation is running"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "mkdocs serve"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    @rumps.clicked("Documentation")
    def docs_menu(self, _):
        pass

    @rumps.clicked("Documentation/Démarrer Serveur")
    def start_docs(self, _):
        if self.is_docs_running():
             rumps.alert("Docs", "La documentation tourne déjà sur http://127.0.0.1:8001")
             return
        
        try:
            subprocess.run([str(self.docs_script)])
            rumps.notification("Documentation", "Démarrage...", "Serveur lancé sur http://127.0.0.1:8001")
        except Exception as e:
            rumps.alert("Erreur", f"Impossible de lancer docs-serve.sh: {e}")

    @rumps.clicked("Documentation/Arrêter Serveur")
    def stop_docs(self, _):
        if not self.is_docs_running():
             rumps.alert("Docs", "La documentation n'est pas en cours d'exécution.")
             return
        
        try:
            # Kill mkdocs
            subprocess.run(["pkill", "-f", "mkdocs serve"])
            rumps.notification("Documentation", "Arrêt", "Serveur de documentation arrêté")
        except Exception as e:
            rumps.alert("Erreur", f"Erreur à l'arrêt: {e}")

    @rumps.clicked("Documentation/Ouvrir dans le navigateur")
    def open_docs_browser(self, _):
        webbrowser.open("http://127.0.0.1:8001")
    
    @rumps.clicked("Démarrer tout")
    def start_all(self, _):
        """Start both Meilisearch and Indexao"""
        rumps.notification("Indexao Manager", "Démarrage des services", "Démarrage en cours...")
        
        # Start Meilisearch
        if not self.is_meilisearch_running():
            subprocess.run([str(self.meilisearch_script), "start"])
        
        # Start Indexao
        if not self.is_indexao_running():
            script = f"""
            cd {self.indexao_path}
            source venv/bin/activate
            PYTHONPATH=src nohup uvicorn indexao.webui:app --host 127.0.0.1 --port 8000 > data/logs/indexao_webui.log 2>&1 &
            """
            subprocess.run(["bash", "-c", script])
        
        import time
        time.sleep(2)
        self.update_status()
        rumps.notification("Indexao Manager", "Démarrage terminé", "Les services sont en cours d'exécution")
    
    @rumps.clicked("Arrêter tout")
    def stop_all(self, _):
        """Stop both services"""
        rumps.notification("Indexao Manager", "Arrêt des services", "Arrêt en cours...")
        
        # Stop Indexao
        subprocess.run(["pkill", "-f", "uvicorn.*indexao"])
        
        # Stop Meilisearch
        subprocess.run([str(self.meilisearch_script), "stop"])
        
        import time
        time.sleep(1)
        self.update_status()
        rumps.notification("Indexao Manager", "Arrêt terminé", "Les services sont arrêtés")
    
    @rumps.clicked("Redémarrer tout")
    def restart_all(self, _):
        """Restart both services"""
        self.stop_all(None)
        import time
        time.sleep(2)
        self.start_all(None)
    
    @rumps.clicked("Ouvrir Indexao Web UI")
    def open_indexao_ui(self, _):
        """Open Indexao web interface"""
        webbrowser.open("http://127.0.0.1:8000")
    
    @rumps.clicked("Ouvrir Meilisearch Dashboard")
    def open_meilisearch_ui(self, _):
        """Open Meilisearch web interface"""
        webbrowser.open("http://127.0.0.1:7700")
    
    @rumps.clicked("Status")
    def show_status(self, _):
        """Show detailed status"""
        meili_status = "✅ En cours" if self.is_meilisearch_running() else "❌ Arrêté"
        indexao_status = "✅ En cours" if self.is_indexao_running() else "❌ Arrêté"
        
        message = f"Meilisearch: {meili_status}\nIndexao: {indexao_status}"
        rumps.alert("Status des services", message)
    
    @rumps.clicked("Voir les logs")
    def view_logs(self, sender):
        """Open logs submenu"""
        pass
    
    @rumps.clicked("Voir les logs/Meilisearch")
    def view_meilisearch_logs(self, _):
        """Open Meilisearch logs in Console"""
        log_path = Path.home() / "pCloudSync/Projets/meilisearch/meilisearch.log"
        subprocess.run(["open", "-a", "Console", str(log_path)])
    
    @rumps.clicked("Voir les logs/Indexao")
    def view_indexao_logs(self, _):
        """Open Indexao logs in Console"""
        subprocess.run(["open", "-a", "Console", "/tmp/indexao.log"])
    
    @rumps.clicked("Rafraîchir status")
    def refresh_status(self, _):
        """Manually refresh status"""
        self.update_status()
        rumps.notification("Indexao Manager", "Status rafraîchi", "")


if __name__ == "__main__":
    IndexaoManager().run()
