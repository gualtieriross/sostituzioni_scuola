from werkzeug.security import generate_password_hash

# Importa app, db e il modello Utente dal tuo progetto
from app import app, db, Utente   # <-- se il tuo modello NON si chiama Utente, cambia qui

USERNAME = "segreteria"
PASSWORD = "segreteria123@"
RUOLO = "segreteria"

with app.app_context():
    # Cerca se esiste già
    user = Utente.query.filter_by(username=USERNAME).first()
    if user:
        print("Utente già esistente:", USERNAME)
    else:
        user = Utente(
            username=USERNAME,
            password_hash=generate_password_hash(PASSWORD),
            ruolo=RUOLO
        )
        db.session.add(user)
        db.session.commit()
        print("✅ Creato utente:", USERNAME, "ruolo:", RUOLO)
