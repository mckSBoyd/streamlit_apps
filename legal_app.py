import streamlit as st
import hashlib
import datetime
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark import Session

@st.cache_resource
def get_session():
    return Session.builder.configs({
        "account": st.secrets["snowflake"]["account"],
        "user": st.secrets["snowflake"]["user"],
        "password": st.secrets["snowflake"]["password"],
        "warehouse": st.secrets["snowflake"]["warehouse"],
        "role": st.secrets["snowflake"]["role"],
    }).create()

session = get_session()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def run_query(sql):
    return session.sql(sql).collect()


def run_query_df(sql):
    return session.sql(sql).to_pandas()


def authenticate(username, password):
    pw_hash = hash_password(password)
    rows = run_query(
        f"SELECT USER_ID, USERNAME, FULL_NAME, ROLE, DEPARTMENT_ID "
        f"FROM LEGAL_REVIEW.APP.USERS "
        f"WHERE USERNAME = '{username}' AND PASSWORD_HASH = '{pw_hash}' AND IS_ACTIVE = TRUE"
    )
    if rows:
        return rows[0]
    return None


def init_passwords():
    users = run_query("SELECT USERNAME FROM LEGAL_REVIEW.APP.USERS")
    for u in users:
        pw_hash = hash_password("city2026")
        session.sql(
            f"UPDATE LEGAL_REVIEW.APP.USERS SET PASSWORD_HASH = '{pw_hash}' WHERE USERNAME = '{u['USERNAME']}'"
        ).collect()


def show_login():
    st.title("City Attorney Document Review System")
    st.subheader("Sign in")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
            return
        user = authenticate(username, password)
        if user:
            st.session_state["user_id"] = user["USER_ID"]
            st.session_state["username"] = user["USERNAME"]
            st.session_state["full_name"] = user["FULL_NAME"]
            st.session_state["role"] = user["ROLE"]
            st.session_state["department_id"] = user["DEPARTMENT_ID"]
            st.session_state["logged_in"] = True
            st.experimental_rerun()
        else:
            st.error("Invalid username or password.")

    st.caption("Default password for all users: city2026")


def show_sidebar():
    with st.sidebar:
        st.markdown(f"**{st.session_state['full_name']}**")
        role_label = "Legal Team" if st.session_state["role"] == "LEGAL" else "Department Staff"
        st.caption(role_label)

        if st.session_state["role"] != "LEGAL":
            dept = run_query(
                f"SELECT DEPARTMENT_NAME FROM LEGAL_REVIEW.APP.DEPARTMENTS "
                f"WHERE DEPARTMENT_ID = {st.session_state['department_id']}"
            )
            if dept:
                st.caption(dept[0]["DEPARTMENT_NAME"])

        st.divider()

        if st.session_state["role"] == "LEGAL":
            page = st.radio(
                "Navigation",
                ["Dashboard", "All reviews", "My assigned reviews", "Document detail"],
                label_visibility="collapsed",
            )
        else:
            page = st.radio(
                "Navigation",
                ["My reviews", "Submit document", "Document detail"],
                label_visibility="collapsed",
            )

        st.divider()
        if st.button("Sign out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_rerun()

    return page


def show_dashboard():
    st.title("Legal review dashboard")

    df_status = run_query_df(
        "SELECT STATUS, COUNT(*) AS CNT FROM LEGAL_REVIEW.APP.DOCUMENTS GROUP BY STATUS"
    )

    status_map = {}
    for _, row in df_status.iterrows():
        status_map[row["STATUS"]] = int(row["CNT"])

    awaiting = status_map.get("SUBMITTED", 0) + status_map.get("IN_REVIEW", 0) + status_map.get("DEPT_REVIEW", 0) + status_map.get("PAST_DUE", 0)
    completed = status_map.get("COMPLETED", 0)
    past_due_count = status_map.get("PAST_DUE", 0)
    total = sum(status_map.values())

    col1, col2, col3 = st.columns(3)
    col1.metric("Awaiting review", awaiting)
    col2.metric("Completed", completed)
    col3.metric("Total documents", total)

    past_due_from_completed = run_query(
        "SELECT COUNT(*) AS CNT FROM LEGAL_REVIEW.APP.DOCUMENTS "
        "WHERE STATUS = 'COMPLETED' AND COMPLETED_AT > DUE_DATE"
    )
    past_due_completed = past_due_from_completed[0]["CNT"] if past_due_from_completed else 0
    total_past_due = past_due_count + past_due_completed
    pct_past_due = float(total_past_due / total * 100) if total > 0 else 0.0

    avg_time = run_query(
        "SELECT ROUND(AVG(DURATION_HOURS), 1) AS AVG_HRS "
        "FROM LEGAL_REVIEW.APP.REVIEW_TIME_LOG WHERE TO_PARTY = 'Legal'"
    )
    avg_hours = float(avg_time[0]["AVG_HRS"]) if avg_time and avg_time[0]["AVG_HRS"] else 0.0

    avg_rounds = run_query(
        "SELECT ROUND(AVG(ROUNDS), 1) AS AVG_ROUNDS FROM ("
        "  SELECT DOCUMENT_ID, COUNT(*) AS ROUNDS "
        "  FROM LEGAL_REVIEW.APP.REVIEW_TIME_LOG GROUP BY DOCUMENT_ID"
        ")"
    )
    avg_back_forth = float(avg_rounds[0]["AVG_ROUNDS"]) if avg_rounds and avg_rounds[0]["AVG_ROUNDS"] else 0.0

    col4, col5, col6 = st.columns(3)
    col4.metric("Avg legal review time (hrs)", avg_hours)
    col5.metric("Avg back-and-forth rounds", avg_back_forth)
    col6.metric("Past due %", f"{pct_past_due:.1f}%")

    st.divider()

    st.subheader("Documents by status")
    if not df_status.empty:
        st.bar_chart(df_status.set_index("STATUS")["CNT"])

    st.subheader("Review time by department")
    df_dept_time = run_query_df(
        "SELECT FROM_PARTY AS DEPARTMENT, ROUND(AVG(DURATION_HOURS), 1) AS AVG_HOURS "
        "FROM LEGAL_REVIEW.APP.REVIEW_TIME_LOG WHERE TO_PARTY = 'Legal' "
        "GROUP BY FROM_PARTY ORDER BY AVG_HOURS DESC"
    )
    if not df_dept_time.empty:
        st.bar_chart(df_dept_time.set_index("DEPARTMENT")["AVG_HOURS"])

    st.subheader("Legal team workload")
    df_workload = run_query_df(
        "SELECT u.FULL_NAME, d.STATUS, COUNT(*) AS CNT "
        "FROM LEGAL_REVIEW.APP.DOCUMENTS d "
        "JOIN LEGAL_REVIEW.APP.USERS u ON d.ASSIGNED_LEGAL_REVIEWER = u.USER_ID "
        "GROUP BY u.FULL_NAME, d.STATUS ORDER BY u.FULL_NAME"
    )
    if not df_workload.empty:
        pivot = df_workload.pivot_table(index="FULL_NAME", columns="STATUS", values="CNT", fill_value=0)
        st.dataframe(pivot, use_container_width=True)


def show_all_reviews():
    st.title("All reviews")

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "SUBMITTED", "IN_REVIEW", "DEPT_REVIEW", "COMPLETED", "PAST_DUE"],
    )

    where = ""
    if status_filter and status_filter != "All":
        where = f"WHERE d.STATUS = '{status_filter}'"

    df = run_query_df(
        f"SELECT d.DOCUMENT_ID, d.TITLE, d.DOCUMENT_TYPE, d.STATUS, "
        f"dep.DEPARTMENT_NAME, u.FULL_NAME AS SUBMITTED_BY, "
        f"lu.FULL_NAME AS LEGAL_REVIEWER, d.DUE_DATE, d.CREATED_AT "
        f"FROM LEGAL_REVIEW.APP.DOCUMENTS d "
        f"JOIN LEGAL_REVIEW.APP.DEPARTMENTS dep ON d.DEPARTMENT_ID = dep.DEPARTMENT_ID "
        f"JOIN LEGAL_REVIEW.APP.USERS u ON d.SUBMITTED_BY = u.USER_ID "
        f"LEFT JOIN LEGAL_REVIEW.APP.USERS lu ON d.ASSIGNED_LEGAL_REVIEWER = lu.USER_ID "
        f"{where} ORDER BY d.CREATED_AT DESC"
    )

    if df.empty:
        st.info("No documents found.")
        return

    st.dataframe(df, use_container_width=True)

    selected_id = st.number_input("Enter document ID to view details", min_value=1, step=1)
    if st.button("View document"):
        st.session_state["selected_doc_id"] = int(selected_id)
        st.experimental_rerun()


def show_my_reviews():
    st.title("My reviews")

    user_id = st.session_state["user_id"]
    role = st.session_state["role"]

    if role == "LEGAL":
        df = run_query_df(
            f"SELECT d.DOCUMENT_ID, d.TITLE, d.DOCUMENT_TYPE, d.STATUS, "
            f"dep.DEPARTMENT_NAME, u.FULL_NAME AS SUBMITTED_BY, d.DUE_DATE, d.CREATED_AT "
            f"FROM LEGAL_REVIEW.APP.DOCUMENTS d "
            f"JOIN LEGAL_REVIEW.APP.DEPARTMENTS dep ON d.DEPARTMENT_ID = dep.DEPARTMENT_ID "
            f"JOIN LEGAL_REVIEW.APP.USERS u ON d.SUBMITTED_BY = u.USER_ID "
            f"WHERE d.ASSIGNED_LEGAL_REVIEWER = {user_id} ORDER BY d.CREATED_AT DESC"
        )
    else:
        df = run_query_df(
            f"SELECT d.DOCUMENT_ID, d.TITLE, d.DOCUMENT_TYPE, d.STATUS, "
            f"dep.DEPARTMENT_NAME, lu.FULL_NAME AS LEGAL_REVIEWER, d.DUE_DATE, d.CREATED_AT "
            f"FROM LEGAL_REVIEW.APP.DOCUMENTS d "
            f"JOIN LEGAL_REVIEW.APP.DEPARTMENTS dep ON d.DEPARTMENT_ID = dep.DEPARTMENT_ID "
            f"LEFT JOIN LEGAL_REVIEW.APP.USERS lu ON d.ASSIGNED_LEGAL_REVIEWER = lu.USER_ID "
            f"WHERE d.SUBMITTED_BY = {user_id} ORDER BY d.CREATED_AT DESC"
        )

    if df.empty:
        st.info("You have no reviews.")
        return

    st.dataframe(df)

    selected_id = st.number_input("Enter document ID to view details", min_value=1, step=1)
    if st.button("View document"):
        st.session_state["selected_doc_id"] = int(selected_id)
        st.experimental_rerun()


def show_submit_document():
    st.title("Submit document for legal review")

    dept_id = st.session_state["department_id"]
    dept = run_query(
        f"SELECT DEPARTMENT_NAME FROM LEGAL_REVIEW.APP.DEPARTMENTS WHERE DEPARTMENT_ID = {dept_id}"
    )
    dept_name = dept[0]["DEPARTMENT_NAME"] if dept else "Unknown"
    st.caption(f"Submitting from: **{dept_name}**")

    uploaded_file = st.file_uploader(
        "Upload document file from your computer",
        type=["pdf", "docx", "doc", "xlsx", "txt", "csv"],
    )

    with st.form("submit_doc"):
        title = st.text_input("Document title")
        description = st.text_area("Description")
        doc_type = st.selectbox(
            "Document type",
            ["Contract", "Agreement", "MOU", "Policy", "Ordinance", "Resolution", "Application", "Waiver", "Other"],
        )
        due_date = st.date_input("Requested review due date", min_value=datetime.date.today())

        legal_members = run_query(
            "SELECT USER_ID, FULL_NAME FROM LEGAL_REVIEW.APP.USERS WHERE ROLE = 'LEGAL' AND IS_ACTIVE = TRUE"
        )
        legal_options = {r["FULL_NAME"]: r["USER_ID"] for r in legal_members}
        assigned_to = st.selectbox("Assign to legal reviewer", list(legal_options.keys()))

        needs_dept_review = st.checkbox("Request additional department reviews")
        dept_reviewers = []
        if needs_dept_review:
            all_depts = run_query(
                f"SELECT d.DEPARTMENT_ID, d.DEPARTMENT_NAME "
                f"FROM LEGAL_REVIEW.APP.DEPARTMENTS d WHERE d.DEPARTMENT_ID != {dept_id} "
                f"ORDER BY d.DEPARTMENT_NAME"
            )
            dept_options = {r["DEPARTMENT_NAME"]: r["DEPARTMENT_ID"] for r in all_depts}
            selected_depts = st.multiselect("Select departments for review", list(dept_options.keys()))
            dept_reviewers = [(dept_options[d], d) for d in selected_depts]

        initial_comment = st.text_area("Initial comments for legal team")
        submitted = st.form_submit_button("Submit document")

    if submitted:
        if not title:
            st.error("Document title is required.")
            return

        legal_user_id = legal_options[assigned_to]
        session.sql(
            f"INSERT INTO LEGAL_REVIEW.APP.DOCUMENTS "
            f"(TITLE, DESCRIPTION, DOCUMENT_TYPE, SUBMITTED_BY, DEPARTMENT_ID, "
            f"ASSIGNED_LEGAL_REVIEWER, STATUS, DUE_DATE) VALUES "
            f"('{title.replace(chr(39), chr(39)+chr(39))}', "
            f"'{description.replace(chr(39), chr(39)+chr(39))}', "
            f"'{doc_type}', {st.session_state['user_id']}, {dept_id}, "
            f"{legal_user_id}, "
            f"'{'DEPT_REVIEW' if dept_reviewers else 'SUBMITTED'}', "
            f"'{due_date}')"
        ).collect()

        new_doc = run_query("SELECT MAX(DOCUMENT_ID) AS DOC_ID FROM LEGAL_REVIEW.APP.DOCUMENTS")
        doc_id = new_doc[0]["DOC_ID"]

        if uploaded_file is not None:
            safe_name = f"doc_{doc_id}_{uploaded_file.name}"
            tmp_path = f"/tmp/{safe_name}"
            with open(tmp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            session.file.put(
                tmp_path,
                "@LEGAL_REVIEW.APP.DOCUMENTS_STAGE",
                auto_compress=False,
                overwrite=True,
            )
            session.sql(
                f"UPDATE LEGAL_REVIEW.APP.DOCUMENTS "
                f"SET FILE_NAME = '{safe_name}', "
                f"STAGE_PATH = '@LEGAL_REVIEW.APP.DOCUMENTS_STAGE/{safe_name}' "
                f"WHERE DOCUMENT_ID = {doc_id}"
            ).collect()

        if initial_comment:
            session.sql(
                f"INSERT INTO LEGAL_REVIEW.APP.REVIEW_COMMENTS "
                f"(DOCUMENT_ID, USER_ID, COMMENT_TEXT, COMMENT_TYPE) VALUES "
                f"({doc_id}, {st.session_state['user_id']}, "
                f"'{initial_comment.replace(chr(39), chr(39)+chr(39))}', 'SUBMISSION')"
            ).collect()

        session.sql(
            f"INSERT INTO LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
            f"(DOCUMENT_ID, FROM_PARTY, TO_PARTY, SENT_AT) VALUES "
            f"({doc_id}, '{dept_name}', 'Legal', CURRENT_TIMESTAMP())"
        ).collect()

        for dept_review_id, dept_review_name in dept_reviewers:
            reviewer = run_query(
                f"SELECT USER_ID FROM LEGAL_REVIEW.APP.USERS WHERE DEPARTMENT_ID = {dept_review_id} LIMIT 1"
            )
            if reviewer:
                session.sql(
                    f"INSERT INTO LEGAL_REVIEW.APP.DEPARTMENT_REVIEWS "
                    f"(DOCUMENT_ID, DEPARTMENT_ID, REVIEWER_USER_ID, STATUS) VALUES "
                    f"({doc_id}, {dept_review_id}, {reviewer[0]['USER_ID']}, 'PENDING')"
                ).collect()

        st.success(f"Document submitted successfully! Document ID: {doc_id}")


def show_document_detail():
    st.title("Document detail")

    doc_id = st.session_state.get("selected_doc_id")
    if not doc_id:
        doc_id = st.number_input("Enter document ID", min_value=1, step=1)
        if not st.button("Load document"):
            return

    user_id = st.session_state["user_id"]
    role = st.session_state["role"]

    doc = run_query(
        f"SELECT d.*, dep.DEPARTMENT_NAME, u.FULL_NAME AS SUBMITTER_NAME, "
        f"lu.FULL_NAME AS REVIEWER_NAME "
        f"FROM LEGAL_REVIEW.APP.DOCUMENTS d "
        f"JOIN LEGAL_REVIEW.APP.DEPARTMENTS dep ON d.DEPARTMENT_ID = dep.DEPARTMENT_ID "
        f"JOIN LEGAL_REVIEW.APP.USERS u ON d.SUBMITTED_BY = u.USER_ID "
        f"LEFT JOIN LEGAL_REVIEW.APP.USERS lu ON d.ASSIGNED_LEGAL_REVIEWER = lu.USER_ID "
        f"WHERE d.DOCUMENT_ID = {doc_id}"
    )

    if not doc:
        st.error("Document not found.")
        return

    doc = doc[0]

    if role != "LEGAL":
        is_submitter = doc["SUBMITTED_BY"] == user_id
        is_dept_reviewer = run_query(
            f"SELECT 1 FROM LEGAL_REVIEW.APP.DEPARTMENT_REVIEWS "
            f"WHERE DOCUMENT_ID = {doc_id} AND REVIEWER_USER_ID = {user_id}"
        )
        if not is_submitter and not is_dept_reviewer:
            st.error("You do not have permission to view this document.")
            return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {doc['TITLE']}")
        st.caption(f"Type: {doc['DOCUMENT_TYPE']} | Status: {doc['STATUS']}")
        st.markdown(f"**Description:** {doc['DESCRIPTION'] or 'N/A'}")
    with col2:
        st.markdown(f"**Department:** {doc['DEPARTMENT_NAME']}")
        st.markdown(f"**Submitted by:** {doc['SUBMITTER_NAME']}")
        st.markdown(f"**Legal reviewer:** {doc['REVIEWER_NAME'] or 'Unassigned'}")
        st.markdown(f"**Due date:** {doc['DUE_DATE']}")
        st.markdown(f"**Created:** {doc['CREATED_AT']}")

    if doc.get("STAGE_PATH"):
        file_name = doc["FILE_NAME"]
        tmp_dl = f"/tmp/dl_{file_name}"
        session.file.get(
            f"@LEGAL_REVIEW.APP.DOCUMENTS_STAGE/{file_name}",
            "/tmp/",
        )
        with open(tmp_dl, "rb") as f:
            file_bytes = f.read()
        st.download_button(
            label=f"Download: {file_name}",
            data=file_bytes,
            file_name=file_name,
        )
    else:
        st.caption("No file attached.")

    dept_reviews = run_query(
        f"SELECT dr.*, dep.DEPARTMENT_NAME, u.FULL_NAME "
        f"FROM LEGAL_REVIEW.APP.DEPARTMENT_REVIEWS dr "
        f"JOIN LEGAL_REVIEW.APP.DEPARTMENTS dep ON dr.DEPARTMENT_ID = dep.DEPARTMENT_ID "
        f"JOIN LEGAL_REVIEW.APP.USERS u ON dr.REVIEWER_USER_ID = u.USER_ID "
        f"WHERE dr.DOCUMENT_ID = {doc_id}"
    )
    if dept_reviews:
        st.subheader("Department reviews")
        for dr in dept_reviews:
            status_icon = "+" if dr["STATUS"] == "COMPLETED" else "..."
            st.markdown(f"{status_icon} **{dr['DEPARTMENT_NAME']}** - {dr['FULL_NAME']} - {dr['STATUS']}")

    st.divider()

    time_logs = run_query_df(
        f"SELECT FROM_PARTY, TO_PARTY, SENT_AT, RESPONDED_AT, DURATION_HOURS "
        f"FROM LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
        f"WHERE DOCUMENT_ID = {doc_id} ORDER BY SENT_AT"
    )
    if not time_logs.empty:
        st.subheader("Review timeline")
        st.dataframe(time_logs, use_container_width=True)

    st.divider()
    st.subheader("Comments")

    comments = run_query(
        f"SELECT rc.COMMENT_TEXT, rc.COMMENT_TYPE, rc.CREATED_AT, u.FULL_NAME, u.ROLE "
        f"FROM LEGAL_REVIEW.APP.REVIEW_COMMENTS rc "
        f"JOIN LEGAL_REVIEW.APP.USERS u ON rc.USER_ID = u.USER_ID "
        f"WHERE rc.DOCUMENT_ID = {doc_id} ORDER BY rc.CREATED_AT ASC"
    )

    for c in comments:
        is_legal = c["ROLE"] == "LEGAL"
        label = "Legal" if is_legal else "Department"
        st.markdown(f"**{c['FULL_NAME']}** ({label}) - {c['CREATED_AT']}")
        st.markdown(f"> {c['COMMENT_TEXT']}")
        st.markdown("")

    st.divider()

    if doc["STATUS"] != "COMPLETED":
        st.subheader("Add comment")
        if role == "LEGAL":
            comment_type = st.selectbox(
                "Comment type",
                ["LEGAL_FEEDBACK", "APPROVAL", "REJECTION"],
            )
        else:
            is_dept_reviewer_for_doc = run_query(
                f"SELECT 1 FROM LEGAL_REVIEW.APP.DEPARTMENT_REVIEWS "
                f"WHERE DOCUMENT_ID = {doc_id} AND REVIEWER_USER_ID = {user_id}"
            )
            if is_dept_reviewer_for_doc:
                comment_type = "DEPARTMENT_REVIEW"
            else:
                comment_type = "DEPARTMENT_RESPONSE"

        new_comment = st.text_area("Your comment")
        if st.button("Submit comment"):
            if not new_comment:
                st.error("Please enter a comment.")
            else:
                session.sql(
                    f"INSERT INTO LEGAL_REVIEW.APP.REVIEW_COMMENTS "
                    f"(DOCUMENT_ID, USER_ID, COMMENT_TEXT, COMMENT_TYPE) VALUES "
                    f"({doc_id}, {user_id}, "
                    f"'{new_comment.replace(chr(39), chr(39)+chr(39))}', '{comment_type}')"
                ).collect()

                if comment_type == "DEPARTMENT_REVIEW":
                    session.sql(
                        f"UPDATE LEGAL_REVIEW.APP.DEPARTMENT_REVIEWS "
                        f"SET STATUS = 'COMPLETED', COMPLETED_AT = CURRENT_TIMESTAMP() "
                        f"WHERE DOCUMENT_ID = {doc_id} AND REVIEWER_USER_ID = {user_id}"
                    ).collect()

                if role == "LEGAL" and comment_type == "LEGAL_FEEDBACK":
                    session.sql(
                        f"UPDATE LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
                        f"SET RESPONDED_AT = CURRENT_TIMESTAMP(), "
                        f"DURATION_HOURS = TIMESTAMPDIFF(HOUR, SENT_AT, CURRENT_TIMESTAMP()) "
                        f"WHERE DOCUMENT_ID = {doc_id} AND RESPONDED_AT IS NULL"
                    ).collect()

                    dept_name = doc["DEPARTMENT_NAME"]
                    session.sql(
                        f"INSERT INTO LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
                        f"(DOCUMENT_ID, FROM_PARTY, TO_PARTY, SENT_AT) VALUES "
                        f"({doc_id}, 'Legal', '{dept_name}', CURRENT_TIMESTAMP())"
                    ).collect()

                    session.sql(
                        f"UPDATE LEGAL_REVIEW.APP.DOCUMENTS SET STATUS = 'IN_REVIEW', "
                        f"UPDATED_AT = CURRENT_TIMESTAMP() WHERE DOCUMENT_ID = {doc_id}"
                    ).collect()

                elif role != "LEGAL" and comment_type == "DEPARTMENT_RESPONSE":
                    session.sql(
                        f"UPDATE LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
                        f"SET RESPONDED_AT = CURRENT_TIMESTAMP(), "
                        f"DURATION_HOURS = TIMESTAMPDIFF(HOUR, SENT_AT, CURRENT_TIMESTAMP()) "
                        f"WHERE DOCUMENT_ID = {doc_id} AND RESPONDED_AT IS NULL"
                    ).collect()

                    dept_name = doc["DEPARTMENT_NAME"]
                    session.sql(
                        f"INSERT INTO LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
                        f"(DOCUMENT_ID, FROM_PARTY, TO_PARTY, SENT_AT) VALUES "
                        f"({doc_id}, '{dept_name}', 'Legal', CURRENT_TIMESTAMP())"
                    ).collect()

                elif comment_type == "APPROVAL":
                    session.sql(
                        f"UPDATE LEGAL_REVIEW.APP.REVIEW_TIME_LOG "
                        f"SET RESPONDED_AT = CURRENT_TIMESTAMP(), "
                        f"DURATION_HOURS = TIMESTAMPDIFF(HOUR, SENT_AT, CURRENT_TIMESTAMP()) "
                        f"WHERE DOCUMENT_ID = {doc_id} AND RESPONDED_AT IS NULL"
                    ).collect()

                    session.sql(
                        f"UPDATE LEGAL_REVIEW.APP.DOCUMENTS SET STATUS = 'COMPLETED', "
                        f"COMPLETED_AT = CURRENT_TIMESTAMP(), UPDATED_AT = CURRENT_TIMESTAMP() "
                        f"WHERE DOCUMENT_ID = {doc_id}"
                    ).collect()

                st.success("Comment added.")
                st.experimental_rerun()
    else:
        st.caption("This document review is complete.")


def main():
    if "passwords_initialized" not in st.session_state:
        init_passwords()
        st.session_state["passwords_initialized"] = True

    if not st.session_state.get("logged_in"):
        show_login()
        return

    page = show_sidebar()

    if page == "Dashboard":
        show_dashboard()
    elif page == "All reviews":
        show_all_reviews()
    elif page in ("My reviews", "My assigned reviews"):
        show_my_reviews()
    elif page == "Submit document":
        show_submit_document()
    elif page == "Document detail":
        show_document_detail()


main()
