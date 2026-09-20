import streamlit as st

st.set_page_config(
    page_title="GATE ME Platform",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ GATE ME Platform")
st.subheader("GATE Mechanical Engineering Preparation")

st.success("Application is running successfully!")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Target Year", "2027")

with col2:
    st.metric("Daily Target", "1 Hour")

with col3:
    st.metric("Weekly Target", "7 Hours")

st.divider()

st.header("📚 Learning Workspace")

option = st.selectbox(
    "Select Module",
    [
        "Dashboard",
        "Syllabus",
        "Focus Mode",
        "Practice",
        "PYQs",
        "Revision",
    ],
)

if option == "Dashboard":
    st.write("Welcome to your GATE Mechanical Engineering dashboard.")

elif option == "Syllabus":
    st.write("GATE Mechanical Engineering syllabus will be available here.")

elif option == "Focus Mode":
    st.write("Focus Mode will track explicitly started study sessions.")

elif option == "Practice":
    st.write("Practice question module.")

elif option == "PYQs":
    st.write("Previous Year Questions module.")

elif option == "Revision":
    st.write("Revision and weakness-recovery module.")
