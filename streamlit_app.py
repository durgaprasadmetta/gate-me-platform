import streamlit as st
import sqlite3
import hashlib
import secrets
from datetime import datetime

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="GATE ME Platform",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_FILE = "gate_me.db"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            gate_branch TEXT DEFAULT 'Mechanical Engineering',
            target_year INTEGER DEFAULT 2027,
            daily_target INTEGER DEFAULT 60,
            weekly_target INTEGER DEFAULT 420,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_minutes INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            status TEXT DEFAULT 'NOT_STARTED',
            accuracy REAL DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


init_database()


# ============================================================
# PASSWORD SECURITY
# ============================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        100000,
    )

    return salt + ":" + hashed.hex()


def verify_password(password, stored_password):
    try:
        salt, stored_hash = stored_password.split(":")

        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000,
        )

        return secrets.compare_digest(
            hashed.hex(),
            stored_hash,
        )

    except Exception:
        return False


# ============================================================
# USER FUNCTIONS
# ============================================================

def create_user(email, password, name):

    conn = get_db()
    cur = conn.cursor()

    try:

        password_hash = hash_password(password)

        cur.execute("""
            INSERT INTO users
            (
                email,
                password_hash,
                full_name,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            email.lower().strip(),
            password_hash,
            name.strip(),
            datetime.now().isoformat(),
        ))

        conn.commit()

        user_id = cur.lastrowid

        conn.close()

        return True, user_id

    except sqlite3.IntegrityError:

        conn.close()

        return False, None


def authenticate(email, password):

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE email = ?
    """, (
        email.lower().strip(),
    )).fetchone()

    conn.close()

    if user is None:
        return None

    if verify_password(
        password,
        user["password_hash"],
    ):
        return dict(user)

    return None


def get_user(user_id):

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    conn.close()

    return dict(user) if user else None


# ============================================================
# SESSION STATE
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "focus_running" not in st.session_state:
    st.session_state.focus_running = False

if "focus_start" not in st.session_state:
    st.session_state.focus_start = None


# ============================================================
# LOGIN / REGISTER
# ============================================================

def authentication_screen():

    st.title("⚙️ GATE ME")
    st.subheader("Mechanical Engineering Preparation Platform")

    st.write(
        "Create your student account or login to continue."
    )

    login_tab, register_tab = st.tabs(
        [
            "🔐 Login",
            "📝 Create Account",
        ]
    )

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with login_tab:

        st.subheader("Student Login")

        email = st.text_input(
            "Email",
            key="login_email",
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password",
        )

        if st.button(
            "Login",
            type="primary",
            use_container_width=True,
        ):

            user = authenticate(
                email,
                password,
            )

            if user:

                st.session_state.logged_in = True
                st.session_state.user_id = user["id"]

                st.success("Login successful.")

                st.rerun()

            else:

                st.error(
                    "Invalid email or password."
                )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    with register_tab:

        st.subheader("Create Student Account")

        name = st.text_input(
            "Full Name",
            key="register_name",
        )

        email = st.text_input(
            "Email",
            key="register_email",
        )

        password = st.text_input(
            "Password",
            type="password",
            key="register_password",
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="register_confirm",
        )

        if st.button(
            "Create Account",
            type="primary",
            use_container_width=True,
        ):

            if not name.strip():
                st.error("Enter your full name.")

            elif "@" not in email:
                st.error("Enter a valid email address.")

            elif len(password) < 8:
                st.error(
                    "Password must contain at least 8 characters."
                )

            elif password != confirm_password:
                st.error(
                    "Passwords do not match."
                )

            else:

                success, user_id = create_user(
                    email,
                    password,
                    name,
                )

                if success:

                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id

                    st.success(
                        "Account created successfully."
                    )

                    st.rerun()

                else:

                    st.error(
                        "An account with this email already exists."
                    )


# ============================================================
# SIDEBAR
# ============================================================

def sidebar(user):

    with st.sidebar:

        st.title("⚙️ GATE ME")

        st.caption(
            "GATE Mechanical Engineering"
        )

        st.divider()

        st.write(
            f"👤 **{user['full_name']}**"
        )

        st.caption(
            user["email"]
        )

        st.divider()

        page = st.radio(
            "Navigation",
            [
                "🏠 Dashboard",
                "📚 Syllabus",
                "⏱️ Focus Mode",
                "📝 Practice",
                "📄 PYQs",
                "🔄 Revision",
                "👤 Profile",
            ],
        )

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True,
        ):

            st.session_state.logged_in = False
            st.session_state.user_id = None

            st.rerun()

    return page


# ============================================================
# DASHBOARD
# ============================================================

def dashboard(user):

    st.title("🏠 Dashboard")

    st.caption(
        "Your personal GATE Mechanical Engineering workspace."
    )

    conn = get_db()

    row = conn.execute("""
        SELECT
            COALESCE(SUM(duration_minutes), 0)
            AS total_minutes
        FROM focus_sessions
        WHERE user_id = ?
    """, (
        user["id"],
    )).fetchone()

    total_minutes = row["total_minutes"]

    conn.close()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Today's Target",
        f"{user['daily_target']} min",
    )

    col2.metric(
        "Weekly Target",
        f"{user['weekly_target']} min",
    )

    col3.metric(
        "Total Focus Time",
        f"{total_minutes} min",
    )

    col4.metric(
        "Target GATE Year",
        user["target_year"],
    )

    st.divider()

    st.subheader("📊 Study Workspace")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.info(
            "### 📚 Learn\n\n"
            "Build concepts step by step."
        )

    with c2:
        st.info(
            "### 📝 Practice\n\n"
            "Solve engineering problems."
        )

    with c3:
        st.info(
            "### 📄 PYQs\n\n"
            "Apply concepts to GATE questions."
        )

    with c4:
        st.info(
            "### 🔄 Revision\n\n"
            "Recover weak concepts."
        )

    st.divider()

    st.subheader("🎯 Learning Pipeline")

    st.progress(
        0,
        text="Overall syllabus progress: 0%",
    )

    st.caption(
        "Your progress engine will be connected to individual topics and assessments."
    )


# ============================================================
# SYLLABUS
# ============================================================

SYLLABUS = {

    "Engineering Mathematics": [

        "Linear Algebra",
        "Calculus",
        "Differential Equations",
        "Probability and Statistics",
        "Numerical Methods",

    ],

    "Engineering Mechanics": [

        "Free Body Diagrams",
        "Equilibrium",
        "Friction",
        "Kinematics",
        "Dynamics",
        "Work Energy",
        "Impulse and Momentum",

    ],

    "Mechanics of Materials": [

        "Stress and Strain",
        "Principal Stresses",
        "Shear Force and Bending Moment",
        "Bending Stress",
        "Shear Stress",
        "Torsion",
        "Deflection",
        "Columns",

    ],

    "Theory of Machines": [

        "Kinematics of Mechanisms",
        "Velocity Analysis",
        "Acceleration Analysis",
        "Gears",
        "Gear Trains",
        "Flywheels",
        "Balancing",
        "Governors",
        "Vibrations",

    ],

    "Machine Design": [

        "Design Fundamentals",
        "Failure Theories",
        "Shafts",
        "Keys and Couplings",
        "Bearings",
        "Gears",
        "Clutches",
        "Brakes",
        "Springs",

    ],

    "Thermodynamics": [

        "Basic Concepts",
        "First Law",
        "Second Law",
        "Entropy",
        "Properties of Pure Substances",
        "Power Cycles",
        "Gas Power Cycles",

    ],

    "Fluid Mechanics": [

        "Fluid Properties",
        "Fluid Statics",
        "Fluid Kinematics",
        "Fluid Dynamics",
        "Bernoulli Equation",
        "Dimensional Analysis",
        "Pipe Flow",
        "Boundary Layer",
        "Turbomachinery",

    ],

    "Heat Transfer": [

        "Conduction",
        "Convection",
        "Radiation",
        "Heat Exchangers",
        "Transient Heat Transfer",

    ],

    "Manufacturing": [

        "Casting",
        "Metal Forming",
        "Machining",
        "Cutting Mechanics",
        "Welding",
        "CNC",
        "Metrology",
        "Non-Traditional Machining",

    ],

    "Industrial Engineering": [

        "Production Planning",
        "Inventory",
        "Operations Research",
        "Work Study",
        "Quality Control",
        "Maintenance",
        "Project Management",

    ],
}


def syllabus_page():

    st.title("📚 GATE Mechanical Engineering Syllabus")

    st.write(
        "Select a subject to explore its topics."
    )

    for subject, topics in SYLLABUS.items():

        with st.expander(
            f"⚙️ {subject}"
        ):

            for topic in topics:

                st.checkbox(
                    topic,
                    key=f"{subject}_{topic}",
                )


# ============================================================
# FOCUS MODE
# ============================================================

def focus_mode(user):

    st.title("⏱️ Focus Mode")

    st.write(
        "Only explicitly started sessions are counted."
    )

    categories = [

        "TECHNICAL_LEARNING",
        "PRACTICE",
        "PYQS",
        "REVISION",
        "STRATEGY",

    ]

    category = st.selectbox(
        "Study Category",
        categories,
    )

    if not st.session_state.focus_running:

        st.info(
            "No focus session is currently running."
        )

        if st.button(
            "▶ START FOCUS SESSION",
            type="primary",
            use_container_width=True,
        ):

            st.session_state.focus_running = True

            st.session_state.focus_start = datetime.now()

            st.rerun()

    else:

        st.success(
            f"FOCUS SESSION ACTIVE — {category}"
        )

        started = st.session_state.focus_start

        elapsed = datetime.now() - started

        minutes = int(
            elapsed.total_seconds() / 60
        )

        seconds = int(
            elapsed.total_seconds()
        ) % 60

        st.metric(
            "Current Session",
            f"{minutes} min {seconds} sec",
        )

        st.warning(
            "Keep the Focus Mode page active while studying."
        )

        if st.button(
            "■ STOP & SAVE SESSION",
            type="primary",
            use_container_width=True,
        ):

            duration = max(
                1,
                minutes,
            )

            conn = get_db()

            conn.execute("""
                INSERT INTO focus_sessions
                (
                    user_id,
                    category,
                    start_time,
                    end_time,
                    duration_minutes
                )
                VALUES (?, ?, ?, ?, ?)
            """, (

                user["id"],
                category,
                started.isoformat(),
                datetime.now().isoformat(),
                duration,

            ))

            conn.commit()
            conn.close()

            st.session_state.focus_running = False
            st.session_state.focus_start = None

            st.success(
                f"Saved {duration} minute study session."
            )

            st.rerun()

    st.divider()

    st.subheader("Recent Sessions")

    conn = get_db()

    sessions = conn.execute("""
        SELECT
            category,
            start_time,
            end_time,
            duration_minutes
        FROM focus_sessions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (
        user["id"],
    )).fetchall()

    conn.close()

    if sessions:

        st.dataframe(
            [dict(x) for x in sessions],
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No completed sessions yet."
        )


# ============================================================
# PRACTICE
# ============================================================

def practice_page():

    st.title("📝 Practice")

    st.info(
        "The question engine is the next module to connect here."
    )

    st.selectbox(
        "Subject",
        list(SYLLABUS.keys()),
    )

    st.text_area(
        "Practice notes",
        placeholder="Write your solution or doubts here...",
    )

    st.button(
        "Save Practice Session",
        use_container_width=True,
    )


# ============================================================
# PYQs
# ============================================================

def pyq_page():

    st.title("📄 GATE Previous Year Questions")

    st.info(
        "The CBT/PYQ engine will be connected in the next phase."
    )

    st.selectbox(
        "Select Subject",
        list(SYLLABUS.keys()),
    )

    st.selectbox(
        "Question Type",
        [
            "MCQ",
            "MSQ",
            "NAT",
        ],
    )

    st.button(
        "Start PYQ Session",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# REVISION
# ============================================================

def revision_page():

    st.title("🔄 Revision")

    st.info(
        "Your weak-topic engine will automatically populate this area after assessment data is available."
    )

    st.subheader(
        "Revision Queue"
    )

    st.warning(
        "No weak concepts have been detected yet."
    )


# ============================================================
# PROFILE
# ============================================================

def profile_page(user):

    st.title("👤 Profile")

    with st.form("profile_form"):

        name = st.text_input(
            "Full Name",
            value=user["full_name"],
        )

        branch = st.text_input(
            "GATE Branch",
            value=user["gate_branch"],
        )

        year = st.number_input(
            "Target GATE Year",
            min_value=2026,
            max_value=2035,
            value=user["target_year"],
        )

        daily = st.number_input(
            "Daily Study Target (minutes)",
            min_value=15,
            max_value=720,
            value=user["daily_target"],
            step=15,
        )

        weekly = st.number_input(
            "Weekly Study Target (minutes)",
            min_value=60,
            max_value=5000,
            value=user["weekly_target"],
            step=30,
        )

        if st.form_submit_button(
            "Save Profile",
            use_container_width=True,
        ):

            conn = get_db()

            conn.execute("""
                UPDATE users
                SET
                    full_name = ?,
                    gate_branch = ?,
                    target_year = ?,
                    daily_target = ?,
                    weekly_target = ?
                WHERE id = ?
            """, (

                name,
                branch,
                year,
                daily,
                weekly,
                user["id"],

            ))

            conn.commit()
            conn.close()

            st.success(
                "Profile updated."
            )

            st.rerun()


# ============================================================
# MAIN APPLICATION
# ============================================================

if not st.session_state.logged_in:

    authentication_screen()

else:

    user = get_user(
        st.session_state.user_id
    )

    if user is None:

        st.session_state.logged_in = False
        st.session_state.user_id = None

        st.rerun()

    page = sidebar(user)

    if page == "🏠 Dashboard":
        dashboard(user)

    elif page == "📚 Syllabus":
        syllabus_page()

    elif page == "⏱️ Focus Mode":
        focus_mode(user)

    elif page == "📝 Practice":
        practice_page()

    elif page == "📄 PYQs":
        pyq_page()

    elif page == "🔄 Revision":
        revision_page()

    elif page == "👤 Profile":
        profile_page(user)
