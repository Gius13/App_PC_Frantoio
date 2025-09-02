import sys
from PyQt6 import QtWidgets
from app_frantoio.util.config import load_config
from app_frantoio.core.auth import AuthClient
from app_frantoio.core.fb_client import FirebaseRestClient
from app_frantoio.core.sqlite_client import SQLiteClient
from app_frantoio.core.repository import HybridRepository
from app_frantoio.ui.main_window import MainWindow, LoginDialog
from app_frantoio.ui.main_window import _app_icon

def main():
    cfg = load_config()
    api_key = cfg.get("api_key", "").strip()
    db_url = cfg.get("database_url", "").strip()
    collection = cfg.get("collection", "molitura")
    archive_db = cfg.get("archive_db", "frantoio_archive.db")
    hybrid_days = int(cfg.get("hybrid_days", 7))
    retention_days = int(cfg.get("retention_days", 7))
    
    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.setWindowIcon(_app_icon())

    if not api_key or not db_url:
        QtWidgets.QMessageBox.critical(None, "Config mancante",
                                       "Imposta 'api_key' e 'database_url' in config.json")
        sys.exit(1)

    # Login email/password
    auth = AuthClient(api_key)
    dlg = LoginDialog()
    while True:
        result = dlg.exec()
        if result == QtWidgets.QDialog.DialogCode.Accepted:
            email, password = dlg.get_credentials()
            if not email or not password:
                QtWidgets.QMessageBox.warning(None, "Errore", "Inserisci email e password.")
                continue
            try:
                auth.sign_in_password(email, password)
                break
            except Exception as e:
                QtWidgets.QMessageBox.warning(None, "Login fallito", str(e))
                continue
        else:
            sys.exit(0)

    # Clienti
    fb = FirebaseRestClient(db_url, collection, get_token_callable=lambda: auth.id_token)
    sql = SQLiteClient(archive_db)
    repo = HybridRepository(fb, sql, hybrid_days, retention_days)

    # UI
    win = MainWindow(cfg, repo)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
