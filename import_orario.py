import csv
from app import db, Docente, Lezione, app

# 👉 se il file non è nella stessa cartella, metti qui il percorso completo
CSV_PATH = "defdef_timetable.csv"


def trova_colonna_teachers(row):
    """Trova la colonna 'Teachers' anche se ha spazi strani."""
    for k in row.keys():
        if k and k.strip().lower() == "teachers":
            return row[k]
    return ""


def token_to_docente(nome_raw: str):
    nome_raw = nome_raw.strip()
    if not nome_raw:
        return None
    # Nella tabella docenti abbiamo messo in 'cognome' esattamente i valori di Teachers
    return Docente.query.filter_by(cognome=nome_raw).first()


def main():
    with app.app_context():
        try:
            f = open(CSV_PATH, newline='', encoding='utf-8')
        except FileNotFoundError:
            print("❌ File CSV non trovato:", CSV_PATH)
            return

        with f:
            reader = csv.DictReader(f)
            print("📌 Header CSV:", reader.fieldnames)

            total_rows = 0
            rows_con_teachers = 0
            lezioni_inserite = 0
            docenti_mancanti = set()

            for row in reader:
                total_rows += 1

                teachers = trova_colonna_teachers(row)
                if not teachers:
                    continue

                rows_con_teachers += 1

                # separa compresenze: GAL ANIKO+MOSCHELLA
                parts = teachers.replace(",", "+").split("+")
                parts = [p.strip() for p in parts if p.strip()]

                for t in parts:
                    docente = token_to_docente(t)
                    if not docente:
                        docenti_mancanti.add(t)
                        continue

                    lezione = Lezione(
                        docente_id=docente.id,
                        activity_id=int(row.get("Activity Id") or 0),
                        day=(row.get("Day") or "").strip(),
                        hour=(row.get("Hour") or "").strip(),
                        students_set=(row.get("Students Sets") or "").strip(),
                        subject=(row.get("Subject") or "").strip(),
                        room=(row.get("Room") or "").strip(),
                        note=(row.get("Comments") or "").strip(),
                    )
                    db.session.add(lezione)
                    lezioni_inserite += 1

            db.session.commit()

            print("✅ Righe totali nel CSV:", total_rows)
            print("✅ Righe con Teachers valorizzato:", rows_con_teachers)
            print("✅ Lezioni inserite:", lezioni_inserite)

            if docenti_mancanti:
                print("\n⚠ Docenti presenti nell'orario ma NON trovati nella tabella docenti:")
                for d in sorted(docenti_mancanti):
                    print(" -", d)


if __name__ == "__main__":
    main()
