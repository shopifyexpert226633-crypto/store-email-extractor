import re
import socket
import ipaddress
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

APP_NAME = "Privacy Policy Email Extractor"
USER_AGENT = "PrivacyPolicyContactFinder/1.0 (public business contact discovery)"
EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]{1,64}@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}")

st.set_page_config(page_title=APP_NAME, page_icon="✉️", layout="wide")

def validate_public_host(host):
    host = (host or "").lower().rstrip(".")
    if not host or host in {"localhost", "localhost.localdomain"}:
        raise ValueError("Please enter a valid public website.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("Private or non-public IP addresses are not allowed.")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
        try:
            for info in socket.getaddrinfo(host, None):
                if not ipaddress.ip_address(info[4][0]).is_global:
                    raise ValueError("This domain resolves to a non-public IP address.")
        except socket.gaierror:
            raise ValueError("The domain could not be resolved.")
    return host

def normalize_store_url(raw):
    raw = str(raw).strip()
    if not raw:
        raise ValueError("Empty URL")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only valid HTTP or HTTPS URLs are supported.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing login credentials are not accepted.")
    validate_public_host(parsed.hostname)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

def privacy_policy_url(store_url, append_policy):
    base = normalize_store_url(store_url)
    return base.rstrip("/") + "/policies/privacy-policy" if append_policy else base

def extract_emails(text):
    found = set()
    for email in EMAIL_RE.findall(text or ""):
        email = email.strip(".,;:!?)]}>").lower()
        if len(email) <= 254:
            found.add(email)
    return found

def scan_policy(store_url, append_policy=True, timeout=15):
    target = privacy_policy_url(store_url, append_policy)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        response = session.get(target, timeout=timeout, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            return {
                "Store URL": normalize_store_url(store_url), "Scanned page": target,
                "Status": "Redirected (not followed)", "Emails found": 0,
                "HTTP status": response.status_code,
                "Notes": "The privacy-policy page redirected. Redirects are not followed in this version."
            }, []
        response.raise_for_status()
        if "html" not in response.headers.get("Content-Type", "").lower():
            return {
                "Store URL": normalize_store_url(store_url), "Scanned page": target,
                "Status": "Not an HTML page", "Emails found": 0,
                "HTTP status": response.status_code, "Notes": "The requested page did not return HTML."
            }, []
        soup = BeautifulSoup(response.text[:3_000_000], "html.parser")
        found = extract_emails(soup.get_text(" ", strip=True) + " " + response.text)
        rows = [{"Store URL": normalize_store_url(store_url), "Email": e, "Found on": target}
                for e in sorted(found)]
        return {
            "Store URL": normalize_store_url(store_url), "Scanned page": target,
            "Status": "Emails found" if found else "No public email found",
            "Emails found": len(found), "HTTP status": response.status_code, "Notes": ""
        }, rows
    except requests.RequestException as exc:
        return {
            "Store URL": normalize_store_url(store_url), "Scanned page": target,
            "Status": "Request failed", "Emails found": 0, "HTTP status": "",
            "Notes": str(exc)[:220]
        }, []

st.title("✉️ Privacy Policy Email Extractor")
st.caption("Scans only the store's privacy-policy page. It does not crawl other pages.")
st.info("For Shopify stores, the common path is `/policies/privacy-policy`. Some stores use a different URL.")

with st.sidebar:
    st.header("Scan options")
    append_policy = st.checkbox(
        "Add /policies/privacy-policy to all store URLs",
        value=True,
        help="When checked, each input is treated as a store homepage and this exact path is appended."
    )
    st.caption("When unchecked, the exact URL entered is scanned.")

single_tab, bulk_tab = st.tabs(["Single store", "Bulk stores"])

with single_tab:
    one_url = st.text_input("Store URL", placeholder="https://example-store.com")
    if one_url.strip():
        try:
            st.caption("Target page preview:")
            st.code(privacy_policy_url(one_url, append_policy))
        except ValueError:
            pass
    if st.button("Scan privacy policy", type="primary"):
        if not one_url.strip():
            st.error("Enter a store URL first.")
        else:
            try:
                with st.spinner("Checking the privacy-policy page only..."):
                    summary, rows = scan_policy(one_url, append_policy)
                st.subheader("Result")
                st.dataframe(pd.DataFrame([summary]), use_container_width=True, hide_index=True)
                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Download emails as CSV", df.to_csv(index=False).encode("utf-8-sig"),
                                       "privacy_policy_emails.csv", "text/csv")
                else:
                    st.warning("No public email address was found on this privacy-policy page.")
            except ValueError as exc:
                st.error(str(exc))

with bulk_tab:
    st.write("Paste up to 2,000 store URLs, one per line, or upload CSV/Excel with a column named `url`.")
    bulk_text = st.text_area("Store URLs", height=170, placeholder="https://store-one.com\nhttps://store-two.com")
    upload = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
    st.caption("The path option above applies to every store in this batch.")
    if st.button("Scan all privacy-policy pages", type="primary"):
        urls = [line.strip() for line in bulk_text.splitlines() if line.strip()]
        if upload is not None:
            try:
                data = pd.read_excel(upload) if upload.name.lower().endswith(".xlsx") else pd.read_csv(upload)
                if "url" not in data.columns:
                    st.error("Your file must contain a column named 'url'.")
                    urls = []
                else:
                    urls.extend(data["url"].dropna().astype(str).tolist())
            except Exception as exc:
                st.error(f"Could not read your file: {exc}")
                urls = []
        unique, seen = [], set()
        for item in urls:
            try:
                key = normalize_store_url(item).lower()
            except ValueError:
                key = item.strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        if not unique:
            st.warning("Add at least one store URL.")
        elif len(unique) > 2000:
            st.error("The maximum is 2,000 unique store URLs per batch.")
        else:
            summaries, contacts = [], []
            progress = st.progress(0)
            status = st.empty()
            for index, store in enumerate(unique, 1):
                status.write(f"Scanning privacy policy {index} of {len(unique)}: {store}")
                try:
                    summary, rows = scan_policy(store, append_policy)
                except ValueError as exc:
                    summary = {"Store URL": store, "Scanned page": "", "Status": "Invalid URL",
                               "Emails found": 0, "HTTP status": "", "Notes": str(exc)}
                    rows = []
                summaries.append(summary)
                contacts.extend(rows)
                progress.progress(index / len(unique))
            status.write(f"Finished: {len(unique)} store URLs processed.")
            summary_df = pd.DataFrame(summaries)
            st.subheader("Store scan summary")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            st.download_button("Download all scan results (CSV)",
                               summary_df.to_csv(index=False).encode("utf-8-sig"),
                               "privacy_policy_scan_summary.csv", "text/csv")
            st.subheader("Email addresses found")
            if contacts:
                contact_df = pd.DataFrame(contacts).drop_duplicates(subset=["Store URL", "Email"])
                st.dataframe(contact_df, use_container_width=True, hide_index=True)
                st.download_button("Download extracted emails (CSV)",
                                   contact_df.to_csv(index=False).encode("utf-8-sig"),
                                   "privacy_policy_emails.csv", "text/csv")
            else:
                st.warning("No public email addresses were found in the scanned privacy-policy pages.")

st.divider()
st.caption("A privacy-policy email is not necessarily the store owner's email. Use public business contact information responsibly and follow applicable privacy, site-use, and anti-spam rules.")
