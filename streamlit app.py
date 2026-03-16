import streamlit as st
from snowflake.snowpark import Session

@st.cache_resource
def get_session():
    return Session.builder.configs({
        "account": st.secrets["snowflake"]["account"],
        "user": st.secrets["snowflake"]["user"],
        "password": st.secrets["snowflake"]["password"],
        "warehouse": st.secrets["snowflake"]["warehouse"],
        "database": st.secrets["snowflake"]["database"],
        "schema": st.secrets["snowflake"]["schema"],
    }).create()

session = get_session()

st.title("Airbnb Permit Application")
st.markdown("Complete this form to apply for a short-term rental permit.")

with st.form("permit_application"):
    st.subheader("Applicant Information")
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First name")
        email = st.text_input("Email")
    with col2:
        last_name = st.text_input("Last name")
        phone = st.text_input("Phone number")
    
    st.subheader("Property Details")
    property_address = st.text_input("Property address")
    col3, col4, col5 = st.columns(3)
    with col3:
        city = st.text_input("City")
    with col4:
        state = st.text_input("State")
    with col5:
        zip_code = st.text_input("ZIP code")
    
    col6, col7 = st.columns(2)
    with col6:
        property_type = st.selectbox("Property type", ["Entire home/apt", "Private room", "Shared room", "Hotel room"])
        bedrooms = st.number_input("Number of bedrooms", min_value=0, max_value=20, value=1)
    with col7:
        permit_type = st.selectbox("Permit type", ["New permit", "Renewal", "Transfer of ownership"])
        max_guests = st.number_input("Maximum guests", min_value=1, max_value=50, value=2)
    
    st.subheader("Additional Information")
    is_primary_residence = st.checkbox("This is my primary residence")
    has_liability_insurance = st.checkbox("I have liability insurance coverage")
    additional_notes = st.text_area("Additional notes or comments")
    agree_terms = st.checkbox("I agree to the terms and conditions")
    
    submitted = st.form_submit_button("Submit Application")
    
    if submitted:
        if not all([first_name, last_name, email, property_address, city, state, zip_code]):
            st.error("Please fill in all required fields.")
        elif not agree_terms:
            st.error("You must agree to the terms and conditions.")
        else:
            try:
                session.sql("""
                    INSERT INTO PERMIT_APPLICATIONS 
                    (FIRST_NAME, LAST_NAME, EMAIL, PHONE, PROPERTY_ADDRESS, CITY, STATE, ZIP_CODE,
                     PROPERTY_TYPE, BEDROOMS, PERMIT_TYPE, MAX_GUESTS, IS_PRIMARY_RESIDENCE, 
                     HAS_LIABILITY_INSURANCE, ADDITIONAL_NOTES)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [first_name, last_name, email, phone, property_address, city, state, zip_code,
                      property_type, bedrooms, permit_type, max_guests, is_primary_residence,
                      has_liability_insurance, additional_notes]).collect()
                st.success("Application submitted successfully!")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")
