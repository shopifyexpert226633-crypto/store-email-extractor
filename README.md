# Privacy Policy Email Extractor — Fixed

This corrected build fixes the Python string syntax error in the email cleanup line.

## Windows
1. Extract this ZIP into a NEW folder.
2. Open Command Prompt in that folder.
3. Run: `py -m pip install -r requirements.txt`
4. Run: `py -m streamlit run app.py`
5. Open `http://localhost:8501`.

Stop any older running app first with Ctrl+C in its Command Prompt.

## Features
- Scans only `/policies/privacy-policy` when the checkbox is enabled.
- Toggle to append that path to every store URL.
- Single and bulk scanning, up to 2,000 unique store URLs.
- CSV or Excel upload with a `url` column.
- CSV downloads for scan summaries and extracted emails.

Some stores use a different privacy-policy URL. A public policy email is not proof that it belongs to the owner. Large batches can take time. Keep the app and terminal open.
