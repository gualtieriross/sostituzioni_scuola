from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from functools import wraps

app = Flask(__name__)

# 🔐 Cambialo con una stringa lunga e casuale
app.config['SECRET_KEY'] = 'cambia-questa-chiave-segreta'

# 🔧 Metti qui i dati del tuo MySQL su Aruba
# formato: mysql+pymysql://utente:password@host/nome_database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://Sql1904907:Pierino_68@31.11.38.14/Sql1904907_1'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================
# MODELLI
# ==================

class Utente(db.Model):
    __tablename__ = 'utenti'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    ruolo = db.Column(db.String(50), default='segreteria')

    def verifica_password(self, password):
        return check_password_hash(self.password_hash, password)


class Docente(db.Model):
    __tablename__ = 'docenti'
    id = db.Column(db.Integer, primary_key=True)
    cognome = db.Column(db.String(100), nullable=False)
    nome = db.Column(db.String(100))
    codice = db.Column(db.String(50), unique=True)
    attivo = db.Column(db.Boolean, default=True)


class Assenza(db.Model):
    __tablename__ = 'assenze'
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    ore = db.Column(db.String(50), nullable=False)  # es: "1,2,3"
    note = db.Column(db.Text)

    docente = db.relationship('Docente')


class Lezione(db.Model):
    __tablename__ = 'lezioni'
    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    activity_id = db.Column(db.Integer)
    day = db.Column(db.String(10), nullable=False)       # es: LUN, MAR, ...
    hour = db.Column(db.String(10), nullable=False)      # es: H1, H2, ...
    students_set = db.Column(db.String(50))              # classe / gruppo
    subject = db.Column(db.String(100))                  # materia
    room = db.Column(db.String(50))                      # aula
    note = db.Column(db.String(255))                     # commenti

    docente = db.relationship('Docente')

# ==================
# UTILITY
# ==================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'utente_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def codice_giorno_da_data(data_ass):
    """
    Converte una data Python in codice giorno dell'orario (LUN, MAR, MER, GIO, VEN, SAB, DOM).
    Si basa su weekday(): 0 = lunedì, 6 = domenica.
    """
    mappa = {
        0: 'LUN',
        1: 'MAR',
        2: 'MER',
        3: 'GIO',
        4: 'VEN',
        5: 'SAB',
        6: 'DOM',
    }
    return mappa[data_ass.weekday()]

# ==================
# ROTTE AUTENTICAZIONE
# ==================

@app.route('/init_admin')
def init_admin():
    """
    Rotta una tantum per creare l'utente admin.
    Dopo averla usata con successo, ELIMINA o COMMENTA questa funzione.
    """
    username = 'admin'
    password = 'admin123'  # cambiala subito dopo il primo login

    if Utente.query.filter_by(username=username).first():
        return "Admin esiste già."

    hash_pw = generate_password_hash(password)
    admin = Utente(username=username, password_hash=hash_pw, ruolo='admin')
    db.session.add(admin)
    db.session.commit()
    return "Utente admin creato (username: admin, password: admin123). Ricorda di cambiare la password."


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        utente = Utente.query.filter_by(username=username).first()
        if utente and utente.verifica_password(password):
            session['utente_id'] = utente.id
            session['username'] = utente.username
            session['ruolo'] = utente.ruolo
            return redirect(url_for('gestione_assenze'))
        else:
            flash('Credenziali errate', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==================
# ROTTE PRINCIPALI
# ==================

@app.route('/')
@login_required
def home():
    return redirect(url_for('gestione_assenze'))




@app.route('/assenze', methods=['GET', 'POST'])
@login_required
def gestione_assenze():
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome, Docente.nome).all()
    oggi_iso = date.today().isoformat()

    # -----------------
    # INSERIMENTO / AGGIORNAMENTO ASSENZE (POST)
    # -----------------
    if request.method == 'POST':
        docente_id = request.form.get('docente_id')
        data_inizio_str = request.form.get('data_inizio')
        data_fine_str = request.form.get('data_fine') or data_inizio_str
        note_val = request.form.get('note', '')

        if not docente_id or not data_inizio_str:
            flash("Seleziona docente e almeno la data di inizio.", 'warning')
            return redirect(url_for('gestione_assenze'))

        # converto in date
        a_i, m_i, g_i = map(int, data_inizio_str.split('-'))
        a_f, m_f, g_f = map(int, data_fine_str.split('-'))
        data_inizio = date(a_i, m_i, g_i)
        data_fine = date(a_f, m_f, g_f)

        # se l'utente mette fine prima dell'inizio, inverto
        if data_fine < data_inizio:
            data_inizio, data_fine = data_fine, data_inizio

        giorni_con_lezioni = 0

        d = data_inizio
        while d <= data_fine:
            codice_g = codice_giorno_da_data(d)

            # lezioni di quel docente in quel giorno
            lezioni = Lezione.query.filter_by(
                docente_id=int(docente_id),
                day=codice_g
            ).all()

            ore_orario_set = set()
            for l in lezioni:
                h = ''.join(ch for ch in (l.hour or '') if ch.isdigit())
                if h:
                    ore_orario_set.add(h)

            if not ore_orario_set:
                # nessuna lezione in quel giorno: passo al successivo
                d = d.fromordinal(d.toordinal() + 1)
                continue

            giorni_con_lezioni += 1

            # assenze già presenti per quel docente in quel giorno
            esistenti = Assenza.query.filter_by(
                docente_id=int(docente_id),
                data=d
            ).all()

            ore_esistenti = set()
            for a in esistenti:
                for o in (a.ore or '').split(','):
                    o = o.strip()
                    if o:
                        ore_esistenti.add(o)

            # unisco ore già assenti + ore da orario
            ore_combinate = sorted(ore_esistenti.union(ore_orario_set), key=lambda x: int(x))
            ore_str = ",".join(ore_combinate)

            if esistenti:
                principale = esistenti[0]
                principale.ore = ore_str
                if note_val:
                    if principale.note:
                        principale.note += " | " + note_val
                    else:
                        principale.note = note_val

                # elimino eventuali record duplicati
                for extra in esistenti[1:]:
                    db.session.delete(extra)
            else:
                nuova = Assenza(
                    docente_id=int(docente_id),
                    data=d,
                    ore=ore_str,
                    note=note_val
                )
                db.session.add(nuova)

            d = d.fromordinal(d.toordinal() + 1)

        db.session.commit()

        if giorni_con_lezioni == 0:
            flash("Nell'intervallo selezionato non risultano ore a orario per questo docente.", 'warning')
        elif giorni_con_lezioni == 1:
            flash("Assenza inserita/aggiornata per 1 giorno.", 'success')
        else:
            flash(f"Assenze inserite/aggiornate per {giorni_con_lezioni} giorni.", 'success')

        return redirect(url_for('gestione_assenze'))

    # -----------------
    # FILTRI (GET) + VISTA
    # -----------------
    f_docente_id = request.args.get('f_docente_id')
    f_data = request.args.get('f_data')
    view_mode = request.args.get('view', 'extended')  # 'compact' oppure 'extended'

    query = Assenza.query

    if f_docente_id:
        try:
            query = query.filter(Assenza.docente_id == int(f_docente_id))
        except ValueError:
            pass

    if f_data:
        try:
            a, m, g = map(int, f_data.split('-'))
            data_filtro = date(a, m, g)
            query = query.filter(Assenza.data == data_filtro)
        except ValueError:
            pass

    assenze = query.order_by(Assenza.data.desc(), Assenza.id.desc()).all()

    return render_template(
        'assenze.html',
        docenti=docenti,
        assenze=assenze,
        f_docente_id=f_docente_id,
        f_data=f_data,
        data_oggi=oggi_iso,   # per default data_inizio
        view_mode=view_mode
    )


# 🔹 Cancella una singola ora da un'assenza
@app.route('/assenze/cancella', methods=['POST'])
@login_required
def cancella_assenza_ora():
    assenza_id = request.form.get('assenza_id')
    ora = request.form.get('ora')

    if not assenza_id or not ora:
        flash("Dati mancanti per la cancellazione.", 'warning')
        return redirect(url_for('gestione_assenze'))

    assenza = Assenza.query.get(assenza_id)
    if not assenza:
        flash("Assenza non trovata.", 'danger')
        return redirect(url_for('gestione_assenze'))

    ore_list = [x for x in (assenza.ore or '').split(',') if x]

    if ora in ore_list:
        ore_list.remove(ora)

    if ore_list:
        assenza.ore = ",".join(ore_list)
        db.session.commit()
        flash(f"Ora {ora} rimossa dall'assenza.", 'success')
    else:
        db.session.delete(assenza)
        db.session.commit()
        flash("Assenza eliminata (nessuna ora residua).", 'success')

    return redirect(url_for('gestione_assenze'))


# Rotta di debug opzionale per vedere l'orario di un docente
@app.route('/debug_orario/<int:docente_id>')
@login_required
def debug_orario(docente_id):
    lez = Lezione.query.filter_by(docente_id=docente_id).order_by(Lezione.day, Lezione.hour).all()
    out = []
    for l in lez:
        out.append(f"{l.day} {l.hour} {l.students_set} {l.subject} ({l.room})")
    return "<br>".join(out) or "Nessuna lezione"


if __name__ == '__main__':
    app.run(debug=True)
