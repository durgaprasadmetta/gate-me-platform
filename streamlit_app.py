import streamlit as st
import sqlite3
import hashlib
import secrets
import random
from datetime import datetime, timedelta, date

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
# CONSTANTS
# ============================================================

FOCUS_CATEGORIES = [
    "TECHNICAL_LEARNING",
    "PRACTICE",
    "PYQS",
    "REVISION",
    "STRATEGY",
]

SESSION_TIMEOUT_SECONDS = 300
HEARTBEAT_SECONDS = 30

QUESTION_TYPES = [
    "MCQ",
    "MSQ",
    "NAT",
]

MASTERY_THRESHOLD = 90.0


# ============================================================
# DATABASE
# ============================================================

def get_db():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    return conn


def column_exists(
    conn,
    table_name,
    column_name,
):

    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        column["name"] == column_name
        for column in columns
    )


def add_column_if_missing(
    conn,
    table_name,
    column_name,
    column_definition,
):

    if not column_exists(
        conn,
        table_name,
        column_name,
    ):

        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}
            """
        )


def init_database():

    conn = get_db()

    cur = conn.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cur.execute(
        """
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
        """
    )

    # --------------------------------------------------------
    # FOCUS SESSIONS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_minutes INTEGER DEFAULT 0,
            status TEXT DEFAULT 'COMPLETED',
            last_heartbeat TEXT,
            active_seconds INTEGER DEFAULT 0,
            paused_seconds INTEGER DEFAULT 0,
            last_activity TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # --------------------------------------------------------
    # STUDY PROGRESS
    # --------------------------------------------------------

    cur.execute(
        """
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
        """
    )

    # --------------------------------------------------------
    # STUDY EVENTS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS study_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id INTEGER,
            event_type TEXT NOT NULL,
            event_time TEXT NOT NULL,
            category TEXT,
            duration_seconds INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(session_id) REFERENCES focus_sessions(id)
        )
        """
    )

    # --------------------------------------------------------
    # STUDY PLAN
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS study_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_date TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            planned_minutes INTEGER DEFAULT 30,
            status TEXT DEFAULT 'PLANNED',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # --------------------------------------------------------
    # REVISION QUEUE
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS revision_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            next_revision TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            difficulty INTEGER DEFAULT 2,
            source_type TEXT DEFAULT 'ORIGINAL',
            created_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # QUESTION RESPONSES
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS question_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_answer TEXT,
            is_correct INTEGER NOT NULL,
            response_time_seconds INTEGER DEFAULT 0,
            attempted_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
        """
    )

    # --------------------------------------------------------
    # CBT SESSIONS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cbt_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_questions INTEGER DEFAULT 0,
            attempted_questions INTEGER DEFAULT 0,
            correct_questions INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            status TEXT DEFAULT 'ACTIVE',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # --------------------------------------------------------
    # CBT SESSION QUESTIONS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cbt_session_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cbt_session_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            question_order INTEGER NOT NULL,
            selected_answer TEXT,
            is_correct INTEGER,
            answered INTEGER DEFAULT 0,
            FOREIGN KEY(cbt_session_id) REFERENCES cbt_sessions(id),
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
        """
    )

    # --------------------------------------------------------
    # PHASE 4 MIGRATION
    # --------------------------------------------------------

    add_column_if_missing(
        conn,
        "study_progress",
        "mastery_status",
        "TEXT DEFAULT 'NOT_STARTED'",
    )

    add_column_if_missing(
        conn,
        "study_progress",
        "last_attempt_at",
        "TEXT",
    )

    add_column_if_missing(
        conn,
        "study_progress",
        "weakness_score",
        "REAL DEFAULT 0",
    )

    conn.commit()

    conn.close()


init_database()


# ============================================================
# ORIGINAL GATE-STYLE QUESTION BANK
# ============================================================

ORIGINAL_QUESTIONS = [

    {
        "subject": "Engineering Mechanics",
        "topic": "Equilibrium",
        "text": (
            "A body is in static equilibrium under coplanar "
            "forces. Which condition must be satisfied?"
        ),
        "type": "MCQ",
        "a": "Only sum of forces is zero",
        "b": "Only sum of moments is zero",
        "c": "Sum of forces and moments are both zero",
        "d": "Velocity must be constant",
        "answer": "C",
        "explanation": (
            "For planar static equilibrium, both the resultant "
            "force and resultant moment must be zero."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Mechanics of Materials",
        "topic": "Stress and Strain",
        "text": (
            "A uniform bar carries an axial tensile load P. "
            "If its cross-sectional area is A, the normal stress is:"
        ),
        "type": "MCQ",
        "a": "P/A",
        "b": "A/P",
        "c": "P+A",
        "d": "P-A",
        "answer": "A",
        "explanation": (
            "Normal stress is defined as axial force divided "
            "by cross-sectional area."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Thermodynamics",
        "topic": "First Law",
        "text": (
            "For a closed system, neglecting changes in kinetic "
            "and potential energy, the first law relates heat, "
            "work and change in internal energy."
        ),
        "type": "MCQ",
        "a": "Q = W + ΔU",
        "b": "Q = W - ΔU",
        "c": "Q = ΔU - W",
        "d": "Q = 0 always",
        "answer": "A",
        "explanation": (
            "Using the convention of work done by the system, "
            "Q = ΔU + W."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Fluid Mechanics",
        "topic": "Bernoulli Equation",
        "text": (
            "For steady incompressible inviscid flow along a "
            "streamline, which quantity remains constant?"
        ),
        "type": "MCQ",
        "a": "Mass flow rate only",
        "b": "Total mechanical energy per unit weight",
        "c": "Velocity only",
        "d": "Pressure only",
        "answer": "B",
        "explanation": (
            "Bernoulli's equation represents conservation of "
            "mechanical energy per unit weight."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Heat Transfer",
        "topic": "Conduction",
        "text": (
            "For one-dimensional steady conduction through a "
            "plane wall with constant thermal conductivity, "
            "the temperature profile is:"
        ),
        "type": "MCQ",
        "a": "Linear",
        "b": "Parabolic",
        "c": "Exponential",
        "d": "Sinusoidal",
        "answer": "A",
        "explanation": (
            "For constant conductivity and no internal heat "
            "generation, the temperature distribution is linear."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Manufacturing",
        "topic": "Machining",
        "text": (
            "In orthogonal cutting, the cutting velocity is "
            "normally considered perpendicular to the cutting edge."
        ),
        "type": "MCQ",
        "a": "True",
        "b": "False",
        "c": "Only for grinding",
        "d": "Only for casting",
        "answer": "A",
        "explanation": (
            "Orthogonal cutting is an idealized two-dimensional "
            "cutting model."
        ),
        "difficulty": 2,
    },

    {
        "subject": "Theory of Machines",
        "topic": "Gears",
        "text": (
            "For two externally meshing gears, the direction "
            "of rotation of the gears is:"
        ),
        "type": "MCQ",
        "a": "Same",
        "b": "Opposite",
        "c": "Always zero",
        "d": "Independent of gearing",
        "answer": "B",
        "explanation": (
            "External gears rotate in opposite directions."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Industrial Engineering",
        "topic": "Inventory",
        "text": (
            "The economic order quantity model primarily attempts "
            "to balance ordering cost and:"
        ),
        "type": "MCQ",
        "a": "Holding cost",
        "b": "Machine cost",
        "c": "Labour wage",
        "d": "Transportation speed",
        "answer": "A",
        "explanation": (
            "EOQ balances ordering cost against inventory holding cost."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Machine Design",
        "topic": "Shafts",
        "text": (
            "A circular shaft subjected to pure torsion develops "
            "maximum shear stress at:"
        ),
        "type": "MCQ",
        "a": "Centre",
        "b": "Outer surface",
        "c": "Mid-radius",
        "d": "Everywhere equally",
        "answer": "B",
        "explanation": (
            "For a circular shaft, shear stress varies linearly "
            "with radius and is maximum at the outer surface."
        ),
        "difficulty": 1,
    },

    {
        "subject": "Engineering Mathematics",
        "topic": "Linear Algebra",
        "text": (
            "For a square matrix, a zero determinant indicates that "
            "the matrix is:"
        ),
        "type": "MCQ",
        "a": "Singular",
        "b": "Orthogonal",
        "c": "Identity",
        "d": "Diagonal",
        "answer": "A",
        "explanation": (
            "A square matrix with zero determinant is singular "
            "and does not have an ordinary inverse."
        ),
        "difficulty": 1,
    },

]


def seed_questions():

    conn = get_db()

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM questions"
    ).fetchone()["c"]

    if count == 0:

        for q in ORIGINAL_QUESTIONS:

            conn.execute(
                """
                INSERT INTO questions
                (
                    subject,
                    topic,
                    question_text,
                    question_type,
                    option_a,
                    option_b,
                    option_c,
                    option_d,
                    correct_answer,
                    explanation,
                    difficulty,
                    source_type,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q["subject"],
                    q["topic"],
                    q["text"],
                    q["type"],
                    q["a"],
                    q["b"],
                    q["c"],
                    q["d"],
                    q["answer"],
                    q["explanation"],
                    q["difficulty"],
                    "ORIGINAL",
                    datetime.now().isoformat(),
                ),
            )

        conn.commit()

    conn.close()


seed_questions()


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


def verify_password(
    password,
    stored_password,
):

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

def create_user(
    email,
    password,
    name,
):

    conn = get_db()

    try:

        password_hash = hash_password(
            password
        )

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users
            (
                email,
                password_hash,
                full_name,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                email.lower().strip(),
                password_hash,
                name.strip(),
                datetime.now().isoformat(),
            ),
        )

        conn.commit()

        user_id = cur.lastrowid

        conn.close()

        return True, user_id

    except sqlite3.IntegrityError:

        conn.close()

        return False, None


def authenticate(
    email,
    password,
):

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (
            email.lower().strip(),
        ),
    ).fetchone()

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

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()

    conn.close()

    return dict(user) if user else None


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "logged_in": False,
    "user_id": None,
    "focus_running": False,
    "focus_session_id": None,
    "focus_category": None,
    "focus_start": None,
    "focus_last_activity": None,
    "focus_status": "STOPPED",
    "last_heartbeat": None,
    "cbt_session_id": None,
    "cbt_question_index": 0,
    "cbt_started": None,
}

for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# TIME HELPERS
# ============================================================

def now():

    return datetime.now()


def parse_datetime(value):

    if not value:
        return None

    try:
        return datetime.fromisoformat(value)

    except Exception:

        return None


def format_duration(seconds):

    seconds = max(
        0,
        int(seconds),
    )

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = seconds % 60

    if hours:

        return (
            f"{hours}h "
            f"{minutes}m "
            f"{secs}s"
        )

    return (
        f"{minutes}m "
        f"{secs}s"
    )


# ============================================================
# FOCUS FUNCTIONS
# ============================================================

def create_focus_session(
    user_id,
    category,
):

    timestamp = now().isoformat()

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO focus_sessions
        (
            user_id,
            category,
            start_time,
            status,
            last_heartbeat,
            active_seconds,
            paused_seconds,
            last_activity
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            category,
            timestamp,
            "ACTIVE",
            timestamp,
            0,
            0,
            timestamp,
        ),
    )

    session_id = cur.lastrowid

    conn.execute(
        """
        INSERT INTO study_events
        (
            user_id,
            session_id,
            event_type,
            event_time,
            category,
            duration_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            session_id,
            "SESSION_STARTED",
            timestamp,
            category,
            0,
        ),
    )

    conn.commit()

    conn.close()

    return session_id


def confirm_focus_activity(
    user_id,
    session_id,
):

    current = now()

    conn = get_db()

    session = conn.execute(
        """
        SELECT *
        FROM focus_sessions
        WHERE id = ?
        AND user_id = ?
        """,
        (
            session_id,
            user_id,
        ),
    ).fetchone()

    if not session:

        conn.close()

        return False

    previous = parse_datetime(
        session["last_activity"]
    )

    increment = 0

    if previous:

        elapsed = (
            current - previous
        ).total_seconds()

        increment = min(
            max(
                0,
                int(elapsed),
            ),
            SESSION_TIMEOUT_SECONDS,
        )

    active_seconds = (
        session["active_seconds"] or 0
    ) + increment

    conn.execute(
        """
        UPDATE focus_sessions
        SET
            status = 'ACTIVE',
            last_activity = ?,
            last_heartbeat = ?,
            active_seconds = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            current.isoformat(),
            current.isoformat(),
            active_seconds,
            session_id,
            user_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO study_events
        (
            user_id,
            session_id,
            event_type,
            event_time,
            category,
            duration_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            session_id,
            "ACTIVITY_CONFIRMED",
            current.isoformat(),
            session["category"],
            increment,
        ),
    )

    conn.commit()

    conn.close()

    return True


def check_focus_inactivity(
    user_id,
    session_id,
):

    current = now()

    conn = get_db()

    session = conn.execute(
        """
        SELECT *
        FROM focus_sessions
        WHERE id = ?
        AND user_id = ?
        """,
        (
            session_id,
            user_id,
        ),
    ).fetchone()

    if not session:

        conn.close()

        return False

    last_activity = parse_datetime(
        session["last_activity"]
    )

    if last_activity:

        inactive_seconds = (
            current - last_activity
        ).total_seconds()

        if (
            inactive_seconds
            > SESSION_TIMEOUT_SECONDS
            and session["status"] == "ACTIVE"
        ):

            conn.execute(
                """
                UPDATE focus_sessions
                SET status = 'PAUSED_INACTIVE'
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    session_id,
                    user_id,
                ),
            )

            conn.execute(
                """
                INSERT INTO study_events
                (
                    user_id,
                    session_id,
                    event_type,
                    event_time,
                    category
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    "AUTO_PAUSED_INACTIVE",
                    current.isoformat(),
                    session["category"],
                ),
            )

            conn.commit()

            conn.close()

            return True

    conn.close()

    return False


def pause_focus_session(
    user_id,
    session_id,
):

    conn = get_db()

    conn.execute(
        """
        UPDATE focus_sessions
        SET status = 'PAUSED_MANUAL'
        WHERE id = ?
        AND user_id = ?
        """,
        (
            session_id,
            user_id,
        ),
    )

    conn.commit()

    conn.close()


def resume_focus_session(
    user_id,
    session_id,
):

    timestamp = now().isoformat()

    conn = get_db()

    conn.execute(
        """
        UPDATE focus_sessions
        SET
            status = 'ACTIVE',
            last_activity = ?,
            last_heartbeat = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            timestamp,
            timestamp,
            session_id,
            user_id,
        ),
    )

    conn.commit()

    conn.close()


def finalize_focus_session(
    user_id,
):

    session_id = (
        st.session_state.focus_session_id
    )

    if not session_id:
        return

    current = now()

    conn = get_db()

    session = conn.execute(
        """
        SELECT *
        FROM focus_sessions
        WHERE id = ?
        AND user_id = ?
        """,
        (
            session_id,
            user_id,
        ),
    ).fetchone()

    if session:

        active_seconds = (
            session["active_seconds"] or 0
        )

        last_activity = parse_datetime(
            session["last_activity"]
        )

        if (
            last_activity
            and session["status"] == "ACTIVE"
        ):

            additional = min(
                max(
                    0,
                    int(
                        (
                            current
                            - last_activity
                        ).total_seconds()
                    ),
                ),
                SESSION_TIMEOUT_SECONDS,
            )

            active_seconds += additional

        duration_minutes = (
            active_seconds // 60
        )

        conn.execute(
            """
            UPDATE focus_sessions
            SET
                end_time = ?,
                active_seconds = ?,
                duration_minutes = ?,
                status = 'COMPLETED'
            WHERE id = ?
            AND user_id = ?
            """,
            (
                current.isoformat(),
                active_seconds,
                duration_minutes,
                session_id,
                user_id,
            ),
        )

        conn.commit()

    conn.close()

    st.session_state.focus_running = False
    st.session_state.focus_session_id = None
    st.session_state.focus_category = None
    st.session_state.focus_start = None
    st.session_state.focus_last_activity = None
    st.session_state.focus_status = "STOPPED"
    st.session_state.last_heartbeat = None


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


# ============================================================
# AUTHENTICATION SCREEN
# ============================================================

def authentication_screen():

    st.title("⚙️ GATE ME")

    st.subheader(
        "Mechanical Engineering Preparation Platform"
    )

    login_tab, register_tab = st.tabs(
        [
            "🔐 Login",
            "📝 Create Account",
        ]
    )

    with login_tab:

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

                st.rerun()

            else:

                st.error(
                    "Invalid email or password."
                )

    with register_tab:

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

        confirm = st.text_input(
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

                st.error(
                    "Enter your full name."
                )

            elif "@" not in email:

                st.error(
                    "Enter a valid email address."
                )

            elif len(password) < 8:

                st.error(
                    "Password must contain at least 8 characters."
                )

            elif password != confirm:

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
                "📊 Analytics",
                "🧠 Adaptive Engine",
                "📝 CBT Test",
                "🗓️ Study Planner",
                "👤 Profile",
            ],
        )

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True,
        ):

            if st.session_state.focus_running:

                finalize_focus_session(
                    user["id"]
                )

            for key, value in DEFAULT_STATE.items():

                st.session_state[key] = value

            st.rerun()

    return page


# ============================================================
# FOCUS STATISTICS
# ============================================================

def get_focus_statistics(user_id):

    today = date.today()

    today_start = datetime.combine(
        today,
        datetime.min.time(),
    )

    tomorrow = (
        today_start
        + timedelta(days=1)
    )

    week_start = (
        today_start
        - timedelta(days=today.weekday())
    )

    conn = get_db()

    today_row = conn.execute(
        """
        SELECT COALESCE(
            SUM(active_seconds), 0
        ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        AND start_time >= ?
        AND start_time < ?
        """,
        (
            user_id,
            today_start.isoformat(),
            tomorrow.isoformat(),
        ),
    ).fetchone()

    week_row = conn.execute(
        """
        SELECT COALESCE(
            SUM(active_seconds), 0
        ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        AND start_time >= ?
        AND start_time < ?
        """,
        (
            user_id,
            week_start.isoformat(),
            tomorrow.isoformat(),
        ),
    ).fetchone()

    total_row = conn.execute(
        """
        SELECT COALESCE(
            SUM(active_seconds), 0
        ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()

    categories = conn.execute(
        """
        SELECT
            category,
            COALESCE(
                SUM(active_seconds),
                0
            ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        GROUP BY category
        ORDER BY seconds DESC
        """,
        (
            user_id,
        ),
    ).fetchall()

    daily = conn.execute(
        """
        SELECT
            substr(start_time,1,10)
            AS study_date,
            COALESCE(
                SUM(active_seconds),
                0
            ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        GROUP BY substr(start_time,1,10)
        ORDER BY study_date DESC
        LIMIT 14
        """,
        (
            user_id,
        ),
    ).fetchall()

    conn.close()

    return {
        "today": today_row["seconds"] or 0,
        "week": week_row["seconds"] or 0,
        "total": total_row["seconds"] or 0,
        "categories": [
            dict(x)
            for x in categories
        ],
        "daily": [
            dict(x)
            for x in daily
        ],
    }


# ============================================================
# DASHBOARD
# ============================================================

def dashboard(user):

    st.title("🏠 Dashboard")

    stats = get_focus_statistics(
        user["id"]
    )

    today = stats["today"]

    week = stats["week"]

    daily_target = (
        user["daily_target"]
        * 60
    )

    weekly_target = (
        user["weekly_target"]
        * 60
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Today's Focus",
        format_duration(today),
    )

    c2.metric(
        "Weekly Focus",
        format_duration(week),
    )

    c3.metric(
        "Daily Target",
        f"{user['daily_target']} min",
    )

    c4.metric(
        "Weekly Target",
        f"{user['weekly_target']} min",
    )

    st.divider()

    st.subheader(
        "🎯 Daily Target"
    )

    daily_ratio = min(
        1.0,
        today / max(
            1,
            daily_target,
        ),
    )

    st.progress(
        daily_ratio,
        text=(
            f"{today // 60} / "
            f"{user['daily_target']} minutes"
        ),
    )

    st.subheader(
        "📅 Weekly Target"
    )

    weekly_ratio = min(
        1.0,
        week / max(
            1,
            weekly_target,
        ),
    )

    st.progress(
        weekly_ratio,
        text=(
            f"{week // 60} / "
            f"{user['weekly_target']} minutes"
        ),
    )

    st.divider()

    st.subheader(
        "🧠 Adaptive Learning Status"
    )

    mastery = get_mastery_statistics(
        user["id"]
    )

    a, b, c = st.columns(3)

    a.metric(
        "Topics Attempted",
        mastery["attempted"],
    )

    b.metric(
        "Strong Topics",
        mastery["strong"],
    )

    c.metric(
        "Weak Topics",
        mastery["weak"],
    )


# ============================================================
# SYLLABUS
# ============================================================

def syllabus_page():

    st.title(
        "📚 GATE Mechanical Engineering Syllabus"
    )

    for subject, topics in SYLLABUS.items():

        with st.expander(
            f"⚙️ {subject}"
        ):

            for topic in topics:

                st.checkbox(
                    topic,
                    key=(
                        "syllabus_"
                        + subject
                        + "_"
                        + topic
                    ),
                )


# ============================================================
# FOCUS MODE
# ============================================================

def focus_mode(user):

    st.title("⏱️ Focus Mode")

    if not st.session_state.focus_running:

        category = st.selectbox(
            "Study Category",
            FOCUS_CATEGORIES,
        )

        st.info(
            "Start a session when you are ready to study."
        )

        if st.button(
            "▶ START FOCUS SESSION",
            type="primary",
            use_container_width=True,
        ):

            session_id = create_focus_session(
                user["id"],
                category,
            )

            current = now()

            st.session_state.focus_running = True
            st.session_state.focus_session_id = session_id
            st.session_state.focus_category = category
            st.session_state.focus_start = current
            st.session_state.focus_last_activity = current
            st.session_state.focus_status = "ACTIVE"

            st.rerun()

    else:

        session_id = (
            st.session_state.focus_session_id
        )

        check_focus_inactivity(
            user["id"],
            session_id,
        )

        conn = get_db()

        session = conn.execute(
            """
            SELECT *
            FROM focus_sessions
            WHERE id = ?
            AND user_id = ?
            """,
            (
                session_id,
                user["id"],
            ),
        ).fetchone()

        conn.close()

        if not session:

            st.session_state.focus_running = False

            st.rerun()

        status = session["status"]

        active_seconds = (
            session["active_seconds"]
            or 0
        )

        st.metric(
            "Verified Active Time",
            format_duration(
                active_seconds
            ),
        )

        st.metric(
            "Status",
            status.replace(
                "_",
                " ",
            ),
        )

        if status == "ACTIVE":

            st.success(
                "🟢 FOCUS SESSION ACTIVE"
            )

            st.write(
                "Confirm your activity periodically "
                "to keep the session active."
            )

            if st.button(
                "✓ I'M STILL STUDYING",
                type="primary",
                use_container_width=True,
            ):

                confirm_focus_activity(
                    user["id"],
                    session_id,
                )

                st.rerun()

            if st.button(
                "⏸ PAUSE SESSION",
                use_container_width=True,
            ):

                pause_focus_session(
                    user["id"],
                    session_id,
                )

                st.rerun()

        elif status == "PAUSED_INACTIVE":

            st.warning(
                "⏸ Session automatically paused "
                "after more than 5 minutes without "
                "confirmed activity."
            )

            if st.button(
                "▶ RESUME",
                type="primary",
                use_container_width=True,
            ):

                resume_focus_session(
                    user["id"],
                    session_id,
                )

                st.rerun()

        else:

            if st.button(
                "▶ RESUME",
                use_container_width=True,
            ):

                resume_focus_session(
                    user["id"],
                    session_id,
                )

                st.rerun()

        st.divider()

        if st.button(
            "■ STOP & SAVE SESSION",
            type="primary",
            use_container_width=True,
        ):

            finalize_focus_session(
                user["id"]
            )

            st.success(
                "Focus session saved."
            )

            st.rerun()


# ============================================================
# QUESTION FUNCTIONS
# ============================================================

def get_questions(
    subject=None,
    topic=None,
    question_type=None,
    user_id=None,
    limit=10,
):

    conn = get_db()

    query = """
        SELECT *
        FROM questions
        WHERE 1 = 1
    """

    params = []

    if subject:

        query += """
            AND subject = ?
        """

        params.append(subject)

    if topic:

        query += """
            AND topic = ?
        """

        params.append(topic)

    if question_type:

        query += """
            AND question_type = ?
        """

        params.append(question_type)

    if user_id:

        query += """
            AND id NOT IN (
                SELECT question_id
                FROM question_responses
                WHERE user_id = ?
                ORDER BY attempted_at DESC
                LIMIT 5
            )
        """

        params.append(user_id)

    query += """
        ORDER BY RANDOM()
        LIMIT ?
    """

    params.append(limit)

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def save_question_response(
    user_id,
    question_id,
    selected_answer,
    response_time,
):

    conn = get_db()

    question = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE id = ?
        """,
        (
            question_id,
        ),
    ).fetchone()

    if not question:

        conn.close()

        return False

    correct = (
        selected_answer.strip().upper()
        == question["correct_answer"]
        .strip()
        .upper()
    )

    conn.execute(
        """
        INSERT INTO question_responses
        (
            user_id,
            question_id,
            selected_answer,
            is_correct,
            response_time_seconds,
            attempted_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            question_id,
            selected_answer,
            1 if correct else 0,
            response_time,
            now().isoformat(),
        ),
    )

    conn.commit()

    conn.close()

    update_topic_mastery(
        user_id,
        question["subject"],
        question["topic"],
    )

    return correct


# ============================================================
# TOPIC MASTERY
# ============================================================

def update_topic_mastery(
    user_id,
    subject,
    topic,
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT
            COUNT(*) AS attempts,
            COALESCE(
                SUM(is_correct),
                0
            ) AS correct
        FROM question_responses qr
        JOIN questions q
            ON qr.question_id = q.id
        WHERE qr.user_id = ?
        AND q.subject = ?
        AND q.topic = ?
        """,
        (
            user_id,
            subject,
            topic,
        ),
    ).fetchone()

    attempts = row["attempts"]

    correct = row["correct"]

    accuracy = (
        correct / attempts * 100
        if attempts
        else 0
    )

    if attempts == 0:

        status = "NOT_STARTED"
        weakness = 0

    elif accuracy >= MASTERY_THRESHOLD:

        status = "STRONG"
        weakness = 0

    elif accuracy >= 70:

        status = "NEEDS_REVISION"
        weakness = 50

    else:

        status = "WEAK"
        weakness = 100 - accuracy

    existing = conn.execute(
        """
        SELECT id
        FROM study_progress
        WHERE user_id = ?
        AND subject = ?
        AND topic = ?
        """,
        (
            user_id,
            subject,
            topic,
        ),
    ).fetchone()

    if existing:

        conn.execute(
            """
            UPDATE study_progress
            SET
                status = ?,
                mastery_status = ?,
                accuracy = ?,
                attempts = ?,
                correct = ?,
                weakness_score = ?,
                last_attempt_at = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                status,
                status,
                accuracy,
                attempts,
                correct,
                weakness,
                now().isoformat(),
                existing["id"],
                user_id,
            ),
        )

    else:

        conn.execute(
            """
            INSERT INTO study_progress
            (
                user_id,
                subject,
                topic,
                status,
                mastery_status,
                accuracy,
                attempts,
                correct,
                weakness_score,
                last_attempt_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                subject,
                topic,
                status,
                status,
                accuracy,
                attempts,
                correct,
                weakness,
                now().isoformat(),
            ),
        )

    conn.commit()

    conn.close()

    update_revision_queue(
        user_id,
        subject,
        topic,
        accuracy,
    )


# ============================================================
# REVISION QUEUE GENERATION
# ============================================================

def update_revision_queue(
    user_id,
    subject,
    topic,
    accuracy,
):

    conn = get_db()

    existing = conn.execute(
        """
        SELECT id
        FROM revision_queue
        WHERE user_id = ?
        AND subject = ?
        AND topic = ?
        AND status = 'PENDING'
        """,
        (
            user_id,
            subject,
            topic,
        ),
    ).fetchone()

    if accuracy < MASTERY_THRESHOLD:

        if accuracy < 50:

            priority = 5

            days = 1

        elif accuracy < 70:

            priority = 4

            days = 2

        else:

            priority = 3

            days = 4

        next_revision = (
            date.today()
            + timedelta(days=days)
        ).isoformat()

        if existing:

            conn.execute(
                """
                UPDATE revision_queue
                SET
                    priority = ?,
                    next_revision = ?
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    priority,
                    next_revision,
                    existing["id"],
                    user_id,
                ),
            )

        else:

            conn.execute(
                """
                INSERT INTO revision_queue
                (
                    user_id,
                    subject,
                    topic,
                    priority,
                    next_revision,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
                """,
                (
                    user_id,
                    subject,
                    topic,
                    priority,
                    next_revision,
                    now().isoformat(),
                ),
            )

    else:

        conn.execute(
            """
            UPDATE revision_queue
            SET status = 'MASTERED'
            WHERE user_id = ?
            AND subject = ?
            AND topic = ?
            AND status = 'PENDING'
            """,
            (
                user_id,
                subject,
                topic,
            ),
        )

    conn.commit()

    conn.close()


def get_mastery_statistics(user_id):

    conn = get_db()

    attempted = conn.execute(
        """
        SELECT COUNT(*)
        FROM study_progress
        WHERE user_id = ?
        AND attempts > 0
        """,
        (
            user_id,
        ),
    ).fetchone()[0]

    strong = conn.execute(
        """
        SELECT COUNT(*)
        FROM study_progress
        WHERE user_id = ?
        AND mastery_status = 'STRONG'
        """,
        (
            user_id,
        ),
    ).fetchone()[0]

    weak = conn.execute(
        """
        SELECT COUNT(*)
        FROM study_progress
        WHERE user_id = ?
        AND mastery_status IN
        ('WEAK', 'NEEDS_REVISION')
        """,
        (
            user_id,
        ),
    ).fetchone()[0]

    conn.close()

    return {
        "attempted": attempted,
        "strong": strong,
        "weak": weak,
    }


# ============================================================
# PRACTICE PAGE
# ============================================================

def practice_page(user):

    st.title("📝 Adaptive Practice")

    subjects = list(SYLLABUS.keys())

    subject = st.selectbox(
        "Subject",
        subjects,
    )

    topic = st.selectbox(
        "Topic",
        SYLLABUS[subject],
    )

    question_type = st.selectbox(
        "Question Type",
        QUESTION_TYPES,
    )

    if st.button(
        "🎯 Find Adaptive Questions",
        type="primary",
        use_container_width=True,
    ):

        questions = get_questions(
            subject=subject,
            topic=topic,
            question_type="MCQ",
            user_id=user["id"],
            limit=5,
        )

        if questions:

            st.session_state.practice_questions = questions

            st.session_state.practice_index = 0

            st.session_state.practice_started = datetime.now()

            st.rerun()

        else:

            st.warning(
                "No questions are currently available "
                "for this exact subject/topic/type."
            )

    if (
        "practice_questions"
        not in st.session_state
    ):

        st.info(
            "Select a topic and start an adaptive practice set."
        )

        return

    questions = st.session_state.practice_questions

    index = st.session_state.practice_index

    if index >= len(questions):

        st.success(
            "Practice set completed."
        )

        del st.session_state.practice_questions

        return

    question = questions[index]

    st.divider()

    st.caption(
        f"Question {index + 1} of {len(questions)}"
    )

    st.subheader(
        question["question_text"]
    )

    options = {
        "A": question["option_a"],
        "B": question["option_b"],
        "C": question["option_c"],
        "D": question["option_d"],
    }

    selected = st.radio(
        "Select your answer",
        [
            f"A — {options['A']}",
            f"B — {options['B']}",
            f"C — {options['C']}",
            f"D — {options['D']}",
        ],
    )

    if st.button(
        "Submit Answer",
        type="primary",
        use_container_width=True,
    ):

        answer = selected[0]

        started = st.session_state.get(
            "practice_started",
            datetime.now(),
        )

        response_time = int(
            (
                datetime.now()
                - started
            ).total_seconds()
        )

        correct = save_question_response(
            user["id"],
            question["id"],
            answer,
            response_time,
        )

        if correct:

            st.success(
                "✅ Correct answer."
            )

        else:

            st.error(
                "❌ Incorrect answer."
            )

        st.info(
            "Explanation: "
            + question["explanation"]
        )

        st.session_state.practice_index += 1

        st.session_state.practice_started = (
            datetime.now()
        )

        st.rerun()


# ============================================================
# REVISION PAGE
# ============================================================

def revision_page(user):

    st.title("🔄 Revision Engine")

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            subject,
            topic,
            priority,
            next_revision,
            status
        FROM revision_queue
        WHERE user_id = ?
        AND status = 'PENDING'
        ORDER BY
            priority DESC,
            next_revision ASC
        """,
        (
            user["id"],
        ),
    ).fetchall()

    conn.close()

    if not rows:

        st.success(
            "No pending weak-topic revisions."
        )

        return

    data = []

    for row in rows:

        data.append(
            {
                "Subject": row["subject"],
                "Topic": row["topic"],
                "Priority": row["priority"],
                "Next Revision": row["next_revision"],
                "Status": row["status"],
            }
        )

    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Priority is generated from observed topic performance."
    )


# ============================================================
# ADAPTIVE ENGINE
# ============================================================

def adaptive_engine_page(user):

    st.title("🧠 Adaptive GATE Engine")

    st.caption(
        "The system uses your actual question performance "
        "to identify topics requiring additional work."
    )

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            subject,
            topic,
            accuracy,
            attempts,
            correct,
            mastery_status,
            weakness_score,
            last_attempt_at
        FROM study_progress
        WHERE user_id = ?
        AND attempts > 0
        ORDER BY weakness_score DESC
        """,
        (
            user["id"],
        ),
    ).fetchall()

    conn.close()

    if not rows:

        st.info(
            "Complete some practice questions first. "
            "The adaptive engine will then calculate "
            "topic performance."
        )

        return

    st.subheader(
        "📊 Topic Mastery"
    )

    data = []

    for row in rows:

        data.append(
            {
                "Subject": row["subject"],
                "Topic": row["topic"],
                "Attempts": row["attempts"],
                "Correct": row["correct"],
                "Accuracy (%)": round(
                    row["accuracy"],
                    1,
                ),
                "Mastery": row[
                    "mastery_status"
                ],
                "Weakness": round(
                    row["weakness_score"],
                    1,
                ),
            }
        )

    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader(
        "🎯 Recommended Next Topics"
    )

    weak_rows = sorted(
        data,
        key=lambda x: x["Weakness"],
        reverse=True,
    )

    for item in weak_rows[:5]:

        if item["Weakness"] > 0:

            st.warning(
                f"**{item['Subject']} → "
                f"{item['Topic']}** — "
                f"{item['Accuracy (%)']}% accuracy"
            )


# ============================================================
# PYQ PAGE
# ============================================================

def pyq_page():

    st.title(
        "📄 GATE Previous Year Questions"
    )

    st.info(
        "PYQ infrastructure is separated from the original "
        "practice-question bank. Official PYQs should be "
        "loaded from a properly sourced/licensed dataset."
    )

    st.selectbox(
        "Select Subject",
        list(SYLLABUS.keys()),
    )

    st.selectbox(
        "Question Type",
        QUESTION_TYPES,
    )


# ============================================================
# CBT ENGINE
# ============================================================

def create_cbt_session(
    user_id,
    question_count,
):

    questions = get_questions(
        user_id=user_id,
        limit=question_count,
    )

    if not questions:

        return None

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO cbt_sessions
        (
            user_id,
            session_type,
            started_at,
            total_questions,
            status
        )
        VALUES (?, ?, ?, ?, 'ACTIVE')
        """,
        (
            user_id,
            "ADAPTIVE_CBT",
            now().isoformat(),
            len(questions),
        ),
    )

    session_id = cur.lastrowid

    for index, question in enumerate(
        questions
    ):

        conn.execute(
            """
            INSERT INTO cbt_session_questions
            (
                cbt_session_id,
                question_id,
                question_order
            )
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                question["id"],
                index,
            ),
        )

    conn.commit()

    conn.close()

    return session_id


def cbt_page(user):

    st.title("📝 CBT Test")

    if not st.session_state.cbt_session_id:

        st.write(
            "Adaptive CBT-style test using the available "
            "original GATE-style question bank."
        )

        question_count = st.selectbox(
            "Number of Questions",
            [5, 10],
        )

        if st.button(
            "▶ START CBT",
            type="primary",
            use_container_width=True,
        ):

            session_id = create_cbt_session(
                user["id"],
                question_count,
            )

            if session_id:

                st.session_state.cbt_session_id = (
                    session_id
                )

                st.session_state.cbt_question_index = (
                    0
                )

                st.session_state.cbt_started = (
                    datetime.now()
                )

                st.rerun()

            else:

                st.error(
                    "Not enough questions available."
                )

        return

    session_id = (
        st.session_state.cbt_session_id
    )

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            csq.id,
            csq.question_order,
            csq.selected_answer,
            csq.answered,
            q.*
        FROM cbt_session_questions csq
        JOIN questions q
            ON csq.question_id = q.id
        WHERE csq.cbt_session_id = ?
        ORDER BY csq.question_order
        """,
        (
            session_id,
        ),
    ).fetchall()

    conn.close()

    index = (
        st.session_state.cbt_question_index
    )

    if index >= len(rows):

        finish_cbt(
            user["id"],
            session_id,
        )

        return

    question = dict(
        rows[index]
    )

    st.caption(
        f"Question {index + 1} / {len(rows)}"
    )

    st.progress(
        (index + 1) / len(rows)
    )

    st.subheader(
        question["question_text"]
    )

    options = {
        "A": question["option_a"],
        "B": question["option_b"],
        "C": question["option_c"],
        "D": question["option_d"],
    }

    selected = st.radio(
        "Answer",
        [
            f"A — {options['A']}",
            f"B — {options['B']}",
            f"C — {options['C']}",
            f"D — {options['D']}",
        ],
        key=f"cbt_{session_id}_{index}",
    )

    if st.button(
        "Submit & Next",
        type="primary",
        use_container_width=True,
    ):

        answer = selected[0]

        correct = (
            answer
            == question["correct_answer"]
        )

        conn = get_db()

        conn.execute(
            """
            UPDATE cbt_session_questions
            SET
                selected_answer = ?,
                is_correct = ?,
                answered = 1
            WHERE id = ?
            """,
            (
                answer,
                1 if correct else 0,
                question["id"],
            ),
        )

        conn.commit()

        conn.close()

        save_question_response(
            user["id"],
            question["id"],
            answer,
            0,
        )

        st.session_state.cbt_question_index += 1

        st.rerun()


def finish_cbt(
    user_id,
    session_id,
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(answered) AS attempted,
            SUM(
                CASE
                    WHEN is_correct = 1
                    THEN 1
                    ELSE 0
                END
            ) AS correct
        FROM cbt_session_questions
        WHERE cbt_session_id = ?
        """,
        (
            session_id,
        ),
    ).fetchone()

    total = row["total"] or 0

    attempted = row["attempted"] or 0

    correct = row["correct"] or 0

    score = (
        correct / total * 100
        if total
        else 0
    )

    conn.execute(
        """
        UPDATE cbt_sessions
        SET
            completed_at = ?,
            attempted_questions = ?,
            correct_questions = ?,
            score = ?,
            status = 'COMPLETED'
        WHERE id = ?
        AND user_id = ?
        """,
        (
            now().isoformat(),
            attempted,
            correct,
            score,
            session_id,
            user_id,
        ),
    )

    conn.commit()

    conn.close()

    st.success(
        "🎉 CBT completed."
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Questions",
        total,
    )

    c2.metric(
        "Correct",
        correct,
    )

    c3.metric(
        "Score",
        f"{score:.1f}%",
    )

    if score >= MASTERY_THRESHOLD:

        st.success(
            "Performance reached the current "
            "mastery threshold."
        )

    else:

        st.warning(
            "Topics associated with incorrect answers "
            "will remain candidates for revision."
        )

    if st.button(
        "Start New CBT",
        use_container_width=True,
    ):

        st.session_state.cbt_session_id = None

        st.session_state.cbt_question_index = 0

        st.rerun()


# ============================================================
# ANALYTICS
# ============================================================

def analytics_page(user):

    st.title("📊 Study Analytics")

    stats = get_focus_statistics(
        user["id"]
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Today",
        format_duration(
            stats["today"]
        ),
    )

    c2.metric(
        "This Week",
        format_duration(
            stats["week"]
        ),
    )

    c3.metric(
        "Lifetime",
        format_duration(
            stats["total"]
        ),
    )

    st.divider()

    # --------------------------------------------------------
    # CATEGORY TABLE
    # --------------------------------------------------------

    st.subheader(
        "📚 Study Time by Category"
    )

    if stats["categories"]:

        category_rows = []

        for item in stats["categories"]:

            category_rows.append(
                {
                    "Study Category":
                        item["category"]
                        .replace(
                            "_",
                            " ",
                        ),
                    "Time (minutes)":
                        round(
                            item["seconds"]
                            / 60,
                            1,
                        ),
                }
            )

        # Horizontal table instead of chart-key rendering.
        st.dataframe(
            category_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.bar_chart(
            {
                "Minutes": {
                    item["category"]
                    .replace("_", " "):
                    round(
                        item["seconds"] / 60,
                        1,
                    )
                    for item
                    in stats["categories"]
                }
            }
        )

    else:

        st.info(
            "Complete focus sessions to generate category analytics."
        )

    st.divider()

    # --------------------------------------------------------
    # DAILY TABLE
    # --------------------------------------------------------

    st.subheader(
        "📅 Daily Study History"
    )

    if stats["daily"]:

        daily_rows = []

        for item in reversed(
            stats["daily"]
        ):

            daily_rows.append(
                {
                    "Date":
                        item["study_date"],
                    "Study Time (minutes)":
                        round(
                            item["seconds"]
                            / 60,
                            1,
                        ),
                }
            )

        st.dataframe(
            daily_rows,
            use_container_width=True,
            hide_index=True,
        )

        daily_chart = {}

        for item in reversed(
            stats["daily"]
        ):

            daily_chart[
                item["study_date"]
            ] = round(
                item["seconds"] / 60,
                1,
            )

        st.line_chart(
            daily_chart
        )

    else:

        st.info(
            "Daily study history will appear after focus sessions."
        )

    st.divider()

    # --------------------------------------------------------
    # MASTERY
    # --------------------------------------------------------

    st.subheader(
        "🧠 Topic Performance"
    )

    conn = get_db()

    mastery_rows = conn.execute(
        """
        SELECT
            subject,
            topic,
            attempts,
            correct,
            accuracy,
            mastery_status,
            weakness_score
        FROM study_progress
        WHERE user_id = ?
        AND attempts > 0
        ORDER BY weakness_score DESC
        """,
        (
            user["id"],
        ),
    ).fetchall()

    conn.close()

    if mastery_rows:

        mastery_data = []

        for row in mastery_rows:

            mastery_data.append(
                {
                    "Subject": row["subject"],
                    "Topic": row["topic"],
                    "Attempts": row["attempts"],
                    "Correct": row["correct"],
                    "Accuracy (%)": round(
                        row["accuracy"],
                        1,
                    ),
                    "Mastery": row[
                        "mastery_status"
                    ],
                    "Weakness Score": round(
                        row["weakness_score"],
                        1,
                    ),
                }
            )

        st.dataframe(
            mastery_data,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Solve practice questions to generate topic mastery data."
        )


# ============================================================
# STUDY PLANNER
# ============================================================

def study_planner_page(user):

    st.title("🗓️ Study Planner")

    selected_date = st.date_input(
        "Study Date",
        value=date.today(),
    )

    subject = st.selectbox(
        "Subject",
        list(SYLLABUS.keys()),
    )

    topic = st.selectbox(
        "Topic",
        SYLLABUS[subject],
    )

    minutes = st.number_input(
        "Planned Minutes",
        min_value=15,
        max_value=720,
        value=60,
        step=15,
    )

    if st.button(
        "➕ Add Plan",
        type="primary",
        use_container_width=True,
    ):

        conn = get_db()

        conn.execute(
            """
            INSERT INTO study_plan
            (
                user_id,
                plan_date,
                subject,
                topic,
                planned_minutes,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'PLANNED', ?)
            """,
            (
                user["id"],
                selected_date.isoformat(),
                subject,
                topic,
                minutes,
                now().isoformat(),
            ),
        )

        conn.commit()

        conn.close()

        st.success(
            "Study plan added."
        )

        st.rerun()

    st.divider()

    conn = get_db()

    plans = conn.execute(
        """
        SELECT
            plan_date,
            subject,
            topic,
            planned_minutes,
            status
        FROM study_plan
        WHERE user_id = ?
        ORDER BY plan_date ASC
        """,
        (
            user["id"],
        ),
    ).fetchall()

    conn.close()

    if plans:

        data = []

        for row in plans:

            data.append(
                {
                    "Date": row["plan_date"],
                    "Subject": row["subject"],
                    "Topic": row["topic"],
                    "Planned Minutes":
                        row["planned_minutes"],
                    "Status": row["status"],
                }
            )

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No study plans yet."
        )


# ============================================================
# PROFILE
# ============================================================

def profile_page(user):

    st.title("👤 Profile")

    with st.form(
        "profile_form"
    ):

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

            conn.execute(
                """
                UPDATE users
                SET
                    full_name = ?,
                    gate_branch = ?,
                    target_year = ?,
                    daily_target = ?,
                    weekly_target = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    branch.strip(),
                    year,
                    daily,
                    weekly,
                    user["id"],
                ),
            )

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

    if not user:

        for key, value in DEFAULT_STATE.items():

            st.session_state[key] = value

        st.rerun()

    page = sidebar(user)

    if page == "🏠 Dashboard":

        dashboard(user)

    elif page == "📚 Syllabus":

        syllabus_page()

    elif page == "⏱️ Focus Mode":

        focus_mode(user)

    elif page == "📝 Practice":

        practice_page(user)

    elif page == "📄 PYQs":

        pyq_page()

    elif page == "🔄 Revision":

        revision_page(user)

    elif page == "📊 Analytics":

        analytics_page(user)

    elif page == "🧠 Adaptive Engine":

        adaptive_engine_page(user)

    elif page == "📝 CBT Test":

        cbt_page(user)

    elif page == "🗓️ Study Planner":

        study_planner_page(user)

    elif page == "👤 Profile":

        profile_page(user)
