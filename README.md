# Love Mug MVP

MVP Flask per attivazione tazze con QR unico, varianti Lei/Lui/Neutro, scadenza annuale e rinnovo.

## Avvio in locale su Mac

1. Apri **Terminale**.
2. Entra nella cartella del progetto:
   ```bash
   cd ~/Downloads/love_mug_mvp
   ```
3. Crea ambiente virtuale:
   ```bash
   python3 -m venv .venv
   ```
4. Attivalo:
   ```bash
   source .venv/bin/activate
   ```
5. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
6. Avvia il progetto:
   ```bash
   python app.py
   ```
7. Apri nel browser:
   - http://127.0.0.1:5000/love
   - http://127.0.0.1:5000/admin/login

## Credenziali iniziali admin

- Username: `admin`
- Password: `cambia-subito-questa-password`

## Password admin sicura

Per Render usa una password hashata. Da terminale:

```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('LA-TUA-PASSWORD'))"
```

Copia il risultato e incollalo nella variabile Render `ADMIN_PASSWORD_HASH`.

## URL da usare per il QR

Quando il sito sarà online, usa:

```text
https://tuo-sito.onrender.com/love
```

## Nota importante

Questo è un MVP serio, ma non ancora una piattaforma enterprise. Prima di venderlo in scala conviene:
- passare da SQLite a Postgres
- aggiungere Stripe o PayPal
- inserire email automatiche di scadenza
- mettere rate limit sui tentativi dei codici
