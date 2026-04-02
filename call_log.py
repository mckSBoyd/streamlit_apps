import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, time as time_type, timedelta
from collections import defaultdict
import uuid
import io

st.set_page_config(page_title="📞 Phone Call Log", page_icon="📞", layout="wide")

# ─────────────────────────── Custom CSS ────────────────────────────
st.markdown("""
<style>
  /* Tighten default padding */
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
  /* Status badges */
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .badge-pending     { background:#3d3010; color:#f7b731; }
  .badge-returned    { background:#0d3326; color:#38d9a9; }
  .badge-transferred { background:#2d1f5e; color:#a78bfa; }
  /* Detail card */
  .detail-card {
    background: #1a1d27;
    border: 1px solid #2e3348;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 8px;
  }
  .detail-label { font-size:0.75rem; color:#6b7499; font-weight:600; margin-bottom:2px; }
  .detail-value { font-size:0.9rem; color:#e8ecf4; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────── State Init ────────────────────────────
def init():
    defaults = {
        "entries":      [],
        "reasons":      ["General Inquiry","Billing Question","Technical Support",
                         "Complaint","Follow-Up","Scheduling","Transfer/Forwarded","Other"],
        "caller_types": ["Customer","Vendor","Employee","Contractor",
                         "Government","Unknown","Other"],
        "departments":  ["Front Desk","Accounting","IT","HR",
                         "Sales","Operations","Management","Other"],
        "file_prefix":  "call_log",
        "sheet_name":   "Call Log",
        "return_id":    None,
        "delete_id":    None,
        "view_id":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()

# ─────────────────────────── Helpers ───────────────────────────────
def uid():
    return str(uuid.uuid4())[:8]

def get_status(e):
    if e.get("transferred_to"): return "Transferred"
    if e.get("return_date"):    return "Returned"
    return "Pending"

def status_badge(status):
    cls = {"Pending":"badge-pending","Returned":"badge-returned","Transferred":"badge-transferred"}[status]
    return f'<span class="badge {cls}">{status}</span>'

def fmt_date(d):
    if not d: return ""
    try: return datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
    except: return d

def fmt_time(t):
    if not t: return ""
    try:
        h, m = map(int, t.split(":"))
        return f"{h%12 or 12}:{m:02d} {'PM' if h>=12 else 'AM'}"
    except: return t

def to_excel():
    rows = []
    for i, e in enumerate(st.session_state.entries):
        rows.append({
            "#": i+1,
            "Caller Name": e.get("name",""),
            "Phone": e.get("phone",""),
            "Email": e.get("email",""),
            "Caller Type": e.get("caller_type",""),
            "Reason for Call": e.get("reason",""),
            "Transferred To": e.get("transferred_to",""),
            "Date Called": fmt_date(e.get("date","")),
            "Time Called": fmt_time(e.get("time","")),
            "Return Date": fmt_date(e.get("return_date","")),
            "Return Time": fmt_time(e.get("return_time","")),
            "Status": get_status(e),
            "Notes": e.get("notes",""),
            "Return Notes": e.get("return_notes",""),
        })
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, sheet_name=st.session_state.sheet_name,
                                index=False, engine="openpyxl")
    return buf.getvalue()

def clean(v):
    s = str(v).strip()
    return "" if s in ("nan","None","") else s

def parse_import_date(v):
    s = clean(v)
    if not s: return ""
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except: pass
    return ""

# ─────────────────────────── Dialogs ───────────────────────────────
@st.dialog("📞 Log Return Call", width="large")
def return_dialog():
    entry = next((e for e in st.session_state.entries
                  if e["id"] == st.session_state.return_id), None)
    if not entry:
        st.session_state.return_id = None
        st.rerun()
        return

    st.markdown(f"**Caller:** {entry['name']}"
                + (f"  •  {entry['phone']}" if entry.get("phone") else ""))
    col1, col2 = st.columns(2)
    with col1:
        dval = date.today()
        if entry.get("return_date"):
            try: dval = datetime.strptime(entry["return_date"], "%Y-%m-%d").date()
            except: pass
        ret_date = st.date_input("Return Call Date *", value=dval)
    with col2:
        tval = datetime.now().time().replace(second=0, microsecond=0)
        if entry.get("return_time"):
            try:
                h, m = map(int, entry["return_time"].split(":"))
                tval = time_type(h, m)
            except: pass
        ret_time = st.time_input("Return Call Time", value=tval)

    ret_notes = st.text_area("Return Call Notes",
                              value=entry.get("return_notes",""),
                              placeholder="Outcome, follow-up needed…", height=120)
    b1, b2 = st.columns(2)
    if b1.button("✔ Save Return Call", type="primary", use_container_width=True):
        entry["return_date"]  = ret_date.strftime("%Y-%m-%d")
        entry["return_time"]  = ret_time.strftime("%H:%M")
        entry["return_notes"] = ret_notes
        st.session_state.return_id = None
        st.rerun()
    if b2.button("Cancel", use_container_width=True):
        st.session_state.return_id = None
        st.rerun()

@st.dialog("🗑 Confirm Delete")
def delete_dialog():
    entry = next((e for e in st.session_state.entries
                  if e["id"] == st.session_state.delete_id), None)
    if entry:
        st.warning(f"Permanently delete entry for **{entry['name']}** "
                   f"({fmt_date(entry.get('date',''))})?\n\nThis cannot be undone.")
    b1, b2 = st.columns(2)
    if b1.button("🗑 Delete", type="primary", use_container_width=True):
        st.session_state.entries = [e for e in st.session_state.entries
                                    if e["id"] != st.session_state.delete_id]
        st.session_state.delete_id = None
        if st.session_state.view_id == (entry["id"] if entry else None):
            st.session_state.view_id = None
        st.rerun()
    if b2.button("Cancel", use_container_width=True):
        st.session_state.delete_id = None
        st.rerun()

# Trigger dialogs
if st.session_state.return_id: return_dialog()
if st.session_state.delete_id: delete_dialog()

# ─────────────────────────── Header ────────────────────────────────
h1, h2 = st.columns([2, 3])
with h1:
    st.title("📞 Phone Call Log")

with h2:
    st.write("")  # vertical spacer
    hc1, hc2, hc3 = st.columns(3)

    # Import
    uploaded = hc1.file_uploader(
        "Import", type=["xlsx","xls","csv"],
        label_visibility="collapsed", key="import_file"
    )
    if uploaded:
        try:
            df_imp = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                      else pd.read_excel(uploaded))
            col_map = {
                "name":          ["caller name","name","caller","contact"],
                "phone":         ["phone","phone number","tel","mobile"],
                "email":         ["email","e-mail","email address"],
                "caller_type":   ["caller type","type"],
                "reason":        ["reason","reason for call","purpose"],
                "transferred_to":["transferred to","transfer","department"],
                "date":          ["date called","date","received"],
                "time":          ["time called","time"],
                "notes":         ["notes","incoming notes","message"],
                "return_date":   ["return date","callback date"],
                "return_time":   ["return time","callback time"],
                "return_notes":  ["return notes","outcome"],
            }
            col_lower = {c.lower().strip(): c for c in df_imp.columns}
            field_map = {}
            for field, kws in col_map.items():
                for kw in kws:
                    if kw in col_lower:
                        field_map[field] = col_lower[kw]; break

            added = 0
            for _, row in df_imp.iterrows():
                name = clean(row.get(field_map["name"],"")) if "name" in field_map else ""
                if not name: continue
                entry = {
                    "id": uid(), "name": name,
                    **{f: clean(row.get(field_map[f],"")) if f in field_map else ""
                       for f in ["phone","email","caller_type","reason","transferred_to",
                                 "time","notes","return_time","return_notes"]},
                    "date":        parse_import_date(row.get(field_map["date"],"")) if "date" in field_map else "",
                    "return_date": parse_import_date(row.get(field_map["return_date"],"")) if "return_date" in field_map else "",
                }
                st.session_state.entries.append(entry)
                added += 1
            st.toast(f"✅ Imported {added} entries.")
            st.rerun()
        except Exception as ex:
            st.error(f"Import failed: {ex}")

    hc1.caption("📥 Import XLSX / CSV")

    # Export
    if st.session_state.entries:
        hc2.download_button(
            "📤 Export XLSX",
            data=to_excel(),
            file_name=f"{st.session_state.file_prefix}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        hc2.button("📤 Export XLSX", disabled=True, use_container_width=True)

    # Settings popover
    with hc3.popover("⚙️ Export Settings", use_container_width=True):
        new_prefix = st.text_input("File Name Prefix", value=st.session_state.file_prefix)
        new_sheet  = st.text_input("Sheet Tab Name",   value=st.session_state.sheet_name)
        st.caption(f"Saves as: `{new_prefix or 'call_log'}_{date.today()}.xlsx`")
        if st.button("Save", type="primary"):
            st.session_state.file_prefix = new_prefix or "call_log"
            st.session_state.sheet_name  = new_sheet  or "Call Log"
            st.toast("✅ Settings saved.")

st.divider()

# ─────────────────────────── Tabs ──────────────────────────────────
tab_log, tab_dash, tab_cfg = st.tabs(["📞 Call Log", "📊 Dashboard", "⚙️ Configure Dropdowns"])

# ══════════════════════════ CALL LOG TAB ═══════════════════════════
with tab_log:

    # ── Add Entry Form ──────────────────────────────────────────────
    with st.expander("➕ Log New Call",
                     expanded=len(st.session_state.entries) == 0):
        with st.form("add_form", clear_on_submit=True):
            r1c1, r1c2, r1c3 = st.columns(3)
            name   = r1c1.text_input("Caller Name \\*", placeholder="Jane Smith")
            phone  = r1c2.text_input("Phone Number",    placeholder="555-000-0000")
            email  = r1c3.text_input("Email Address",   placeholder="jane@example.com")

            r2c1, r2c2, r2c3 = st.columns(3)
            caller_type   = r2c1.selectbox("Caller Type",
                                ["— Select —"] + st.session_state.caller_types)
            reason        = r2c2.selectbox("Reason for Call",
                                ["— Select —"] + st.session_state.reasons)
            transferred   = r2c3.selectbox("Transferred To",
                                ["— None —"] + st.session_state.departments)

            r3c1, r3c2 = st.columns(2)
            call_date = r3c1.date_input("Date Called \\*", value=date.today())
            call_time = r3c2.time_input(
                "Time Called",
                value=datetime.now().time().replace(second=0, microsecond=0)
            )
            notes = st.text_area("Notes",
                                 placeholder="Reason for call, message left, etc.",
                                 height=90)

            if st.form_submit_button("➕ Add Entry", type="primary"):
                if not name.strip():
                    st.error("⚠️ Caller name is required.")
                else:
                    st.session_state.entries.insert(0, {
                        "id": uid(),
                        "name": name.strip(),
                        "phone": phone.strip(),
                        "email": email.strip(),
                        "caller_type":   "" if "Select" in caller_type   else caller_type,
                        "reason":        "" if "Select" in reason         else reason,
                        "transferred_to":"" if "None"   in transferred    else transferred,
                        "date":          call_date.strftime("%Y-%m-%d"),
                        "time":          call_time.strftime("%H:%M"),
                        "notes":         notes.strip(),
                        "return_date":   "",
                        "return_time":   "",
                        "return_notes":  "",
                    })
                    st.toast("✅ Call entry added.")
                    st.rerun()

    # ── Search + Metrics ────────────────────────────────────────────
    sc1, sc2, sc3, sc4 = st.columns([4, 1, 1, 1])
    search = sc1.text_input("🔍 Search", label_visibility="collapsed",
                            placeholder="Search name, phone, reason, caller type…")

    entries = st.session_state.entries
    total      = len(entries)
    pending    = sum(1 for e in entries if not e.get("return_date") and not e.get("transferred_to"))
    returned   = sum(1 for e in entries if e.get("return_date"))
    transferred_n = sum(1 for e in entries if e.get("transferred_to"))

    sc2.metric("Total",      total)
    sc3.metric("🟡 Pending", pending)
    sc4.metric("🟢 Returned",returned)

    # Apply search filter
    filtered = entries
    if search:
        q = search.lower()
        filtered = [e for e in entries
                    if any(q in str(v).lower() for v in e.values())]
        st.caption(f"Showing {len(filtered)} of {total} entries")

    # ── Log Table ───────────────────────────────────────────────────
    if not filtered:
        if search:
            st.info(f"No entries match '{search}'.")
        else:
            st.info("No calls logged yet. Use the form above to add your first entry.")
    else:
        status_icon = {"Pending":"🟡","Returned":"🟢","Transferred":"🟣"}
        rows = []
        for e in filtered:
            s = get_status(e)
            rows.append({
                "#":             entries.index(e) + 1,
                "Caller":        e["name"],
                "Phone":         e.get("phone",""),
                "Caller Type":   e.get("caller_type",""),
                "Reason":        e.get("reason",""),
                "Transferred To":e.get("transferred_to",""),
                "Date Called":   fmt_date(e.get("date","")),
                "Time":          fmt_time(e.get("time","")),
                "Return Date":   fmt_date(e.get("return_date","")),
                "Status":        f"{status_icon[s]} {s}",
                "Notes":         (e.get("notes","") or "")[:70]
                                 + ("…" if len(e.get("notes","") or "") > 70 else ""),
            })
        df_display = pd.DataFrame(rows)
        st.dataframe(df_display, use_container_width=True, hide_index=True, height=380)

        # ── Entry Actions ───────────────────────────────────────────
        st.markdown("**Select an entry to take action:**")
        labels = [
            f"#{entries.index(e)+1}  —  {e['name']}  ({fmt_date(e.get('date',''))})"
            for e in filtered
        ]
        ac1, ac2, ac3, ac4 = st.columns([4, 1, 1, 1])
        sel_label = ac1.selectbox("Entry", labels, label_visibility="collapsed")
        sel_entry = filtered[labels.index(sel_label)]

        if ac2.button("📞 Return Call", use_container_width=True):
            st.session_state.return_id = sel_entry["id"]
            st.rerun()

        view_toggle = ac3.button(
            "👁 Details" if st.session_state.view_id != sel_entry["id"] else "✕ Close",
            use_container_width=True
        )
        if view_toggle:
            st.session_state.view_id = (
                None if st.session_state.view_id == sel_entry["id"]
                else sel_entry["id"]
            )
            st.rerun()

        if ac4.button("🗑 Delete", use_container_width=True):
            st.session_state.delete_id = sel_entry["id"]
            st.rerun()

        # ── Detail Panel ────────────────────────────────────────────
        if st.session_state.view_id == sel_entry["id"]:
            e = sel_entry
            s = get_status(e)
            with st.container(border=True):
                hdr1, hdr2 = st.columns([3,1])
                hdr1.subheader(f"📋 {e['name']}")
                hdr2.markdown(status_badge(s), unsafe_allow_html=True)

                d1, d2, d3 = st.columns(3)
                d1.markdown(f"**Phone**  \n{e.get('phone','') or '—'}")
                d2.markdown(f"**Email**  \n{e.get('email','') or '—'}")
                d3.markdown(f"**Caller Type**  \n{e.get('caller_type','') or '—'}")
                d1.markdown(f"**Reason**  \n{e.get('reason','') or '—'}")
                d2.markdown(f"**Transferred To**  \n{e.get('transferred_to','') or '—'}")
                d3.markdown(
                    f"**Date / Time**  \n"
                    f"{fmt_date(e.get('date',''))} {fmt_time(e.get('time',''))}"
                )
                if e.get("notes"):
                    st.markdown(f"**Notes**  \n{e['notes']}")

                if e.get("return_date"):
                    st.divider()
                    r1, r2 = st.columns(2)
                    r1.markdown(
                        f"**Return Date / Time**  \n"
                        f"{fmt_date(e['return_date'])} {fmt_time(e.get('return_time',''))}"
                    )
                    if e.get("return_notes"):
                        r2.markdown(f"**Return Notes**  \n{e['return_notes']}")

# ═══════════════════════════ DASHBOARD TAB ═════════════════════════
with tab_dash:
    entries = st.session_state.entries
    if not entries:
        st.info("No data yet — add some calls to see your dashboard.")
    else:
        total = len(entries)
        pend  = sum(1 for e in entries if not e.get("return_date") and not e.get("transferred_to"))
        ret   = sum(1 for e in entries if e.get("return_date"))
        trans = sum(1 for e in entries if e.get("transferred_to"))
        trans_pct = round(trans / total * 100) if total else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Calls",           total)
        m2.metric("🟡 Pending Returns",    pend)
        m3.metric("🟢 Returned",           ret)
        m4.metric("🟣 Transferred",        f"{trans} ({trans_pct}%)")

        st.divider()

        ch1, ch2 = st.columns(2)

        # Calls by Reason (donut)
        r_counts = defaultdict(int)
        for e in entries: r_counts[e.get("reason") or "Unspecified"] += 1
        if r_counts:
            df_r = pd.DataFrame({"Reason":list(r_counts.keys()),
                                  "Count": list(r_counts.values())})
            ch1.plotly_chart(
                px.pie(df_r, names="Reason", values="Count",
                       title="Calls by Reason", hole=0.38,
                       color_discrete_sequence=px.colors.qualitative.Set3),
                use_container_width=True
            )

        # Calls by Caller Type (bar)
        ct_counts = defaultdict(int)
        for e in entries: ct_counts[e.get("caller_type") or "Unspecified"] += 1
        if ct_counts:
            df_ct = pd.DataFrame({"Type":list(ct_counts.keys()),
                                   "Count":list(ct_counts.values())})
            ch2.plotly_chart(
                px.bar(df_ct, x="Type", y="Count",
                       title="Calls by Caller Type",
                       color="Count",
                       color_continuous_scale="Blues"),
                use_container_width=True
            )

        ch3, ch4 = st.columns(2)

        # Transfers by Department (horizontal bar)
        t_counts = defaultdict(int)
        for e in entries:
            if e.get("transferred_to"): t_counts[e["transferred_to"]] += 1
        if t_counts:
            df_t = pd.DataFrame({"Dept":list(t_counts.keys()),
                                  "Count":list(t_counts.values())})
            ch3.plotly_chart(
                px.bar(df_t, x="Count", y="Dept", orientation="h",
                       title="Transfers by Department",
                       color="Count",
                       color_continuous_scale="Purples"),
                use_container_width=True
            )
        else:
            ch3.info("No transferred calls yet.")

        # Calls over last 30 days (line)
        day_counts = defaultdict(int)
        for e in entries:
            if e.get("date"): day_counts[e["date"]] += 1
        today = date.today()
        days  = [(today - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(29, -1, -1)]
        df_time = pd.DataFrame({
            "Date":  [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in days],
            "Calls": [day_counts.get(d, 0) for d in days],
        })
        ch4.plotly_chart(
            px.line(df_time, x="Date", y="Calls",
                    title="Calls Over Last 30 Days",
                    markers=True,
                    color_discrete_sequence=["#4f9cf9"]),
            use_container_width=True
        )

# ════════════════════════ CONFIGURE DROPDOWNS TAB ══════════════════
with tab_cfg:
    cfg1, cfg2, cfg3 = st.columns(3)

    # ── Reasons ────────────────────────────────────────────────────
    with cfg1:
        st.subheader("📋 Reasons for Call")
        for i, r in enumerate(st.session_state.reasons):
            rc1, rc2 = st.columns([5, 1])
            rc1.write(r)
            if rc2.button("✕", key=f"del_reason_{i}", help="Remove"):
                st.session_state.reasons.pop(i)
                st.rerun()
        st.divider()
        nr = st.text_input("New reason", placeholder="Add new reason…",
                           label_visibility="collapsed", key="new_reason")
        if st.button("➕ Add Reason", key="btn_reason"):
            nr = nr.strip()
            if nr and nr not in st.session_state.reasons:
                st.session_state.reasons.append(nr)
                st.toast("✅ Reason added.")
                st.rerun()
            elif nr:
                st.warning("Already exists.")

    # ── Caller Types ───────────────────────────────────────────────
    with cfg2:
        st.subheader("👤 Caller Types")
        for i, c in enumerate(st.session_state.caller_types):
            cc1, cc2 = st.columns([5, 1])
            cc1.write(c)
            if cc2.button("✕", key=f"del_ct_{i}", help="Remove"):
                st.session_state.caller_types.pop(i)
                st.rerun()
        st.divider()
        nc = st.text_input("New type", placeholder="Add new caller type…",
                           label_visibility="collapsed", key="new_ct")
        if st.button("➕ Add Caller Type", key="btn_ct"):
            nc = nc.strip()
            if nc and nc not in st.session_state.caller_types:
                st.session_state.caller_types.append(nc)
                st.toast("✅ Caller type added.")
                st.rerun()
            elif nc:
                st.warning("Already exists.")

    # ── Departments ────────────────────────────────────────────────
    with cfg3:
        st.subheader("🏢 Departments (Transfer To)")
        for i, d in enumerate(st.session_state.departments):
            dc1, dc2 = st.columns([5, 1])
            dc1.write(d)
            if dc2.button("✕", key=f"del_dept_{i}", help="Remove"):
                st.session_state.departments.pop(i)
                st.rerun()
        st.divider()
        nd = st.text_input("New dept", placeholder="Add new department…",
                           label_visibility="collapsed", key="new_dept")
        if st.button("➕ Add Department", key="btn_dept"):
            nd = nd.strip()
            if nd and nd not in st.session_state.departments:
                st.session_state.departments.append(nd)
                st.toast("✅ Department added.")
                st.rerun()
            elif nd:
                st.warning("Already exists.")

    # ── Export Settings ────────────────────────────────────────────
    st.divider()
    st.subheader("⚙️ Export Settings")
    s1, s2, s3 = st.columns([2, 2, 1])
    new_prefix = s1.text_input("File Name Prefix",
                                value=st.session_state.file_prefix)
    new_sheet  = s2.text_input("Sheet Tab Name",
                                value=st.session_state.sheet_name)
    s3.write("")
    s3.write("")
    if s3.button("💾 Save", use_container_width=True):
        st.session_state.file_prefix = new_prefix.strip() or "call_log"
        st.session_state.sheet_name  = new_sheet.strip()  or "Call Log"
        st.toast("✅ Settings saved.")
    st.caption(
        f"Exports will save as: "
        f"`{st.session_state.file_prefix}_{date.today()}.xlsx`  "
        f"with sheet tab **{st.session_state.sheet_name}**"
    )
