import streamlit as st
import pandas as pd
from snowflake.snowpark import Session

@st.cache_resource
def get_session():
    return Session.builder.configs({
        "account": st.secrets["snowflake"]["account"],
        "user": st.secrets["snowflake"]["user"],
        "password": st.secrets["snowflake"]["password"],
        "role": st.secrets["snowflake"]["role"],
        "warehouse": st.secrets["snowflake"]["warehouse"],
    }).create()

session = get_session()

st.title("Excel to Snowflake Loader")

database = st.text_input("Database", value="")
schema = st.text_input("Schema", value="")
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx", "xls"])

if uploaded_file and database and schema:
    df = pd.read_excel(uploaded_file)
    st.subheader("Preview")
    st.dataframe(df.head(20))
    st.write(f"**Rows:** {len(df)} | **Columns:** {len(df.columns)}")

    table_name = st.text_input(
        "Table name",
        value=uploaded_file.name.rsplit(".", 1)[0].upper().replace(" ", "_"),
    )

    if st.button("Load into Snowflake"):
        with st.spinner("Writing data..."):
            clean_cols = []
            for c in df.columns:
                clean = str(c).strip().upper().replace(" ", "_")
                clean = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in clean)
                if clean[0].isdigit():
                    clean = "_" + clean
                clean_cols.append(clean)
            df.columns = clean_cols

            fq_table = f"{database}.{schema}.{table_name}"
            snowpark_df = session.create_dataframe(df)
            snowpark_df.write.mode("overwrite").save_as_table(fq_table)

        st.success(f"Loaded {len(df)} rows into `{fq_table}`")
