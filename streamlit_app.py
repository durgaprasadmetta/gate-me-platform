import streamlit as st
import sqlite3
import hashlib
import secrets
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


def column_exists(conn, table_name, column_name):
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
            ADD COLUMN {column_name} {column_definition}
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
    # TOPIC REVISION
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
    # PHASE 3 MIGRATION COLUMNS
    # --------------------------------------------------------

    add_column_if_missing(
        conn,
        "focus_sessions",
        "status",
        "TEXT DEFAULT 'COMPLETED'",
    )

    add_column_if_missing(
        conn,
        "focus_sessions",
        "last_heartbeat",
        "TEXT",
    )

    add_column_if_missing(
        conn,
        "focus_sessions",
        "active_seconds",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        conn,
        "focus_sessions",
        "paused_seconds",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        conn,
        "focus_sessions",
        "last_activity",
        "TEXT",
    )

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

        password_hash = hash_password(password)

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

DEFAULT_SESSION_VALUES = {
    "logged_in": False,
    "user_id": None,
    "focus_running": False,
    "focus_session_id": None,
    "focus_category": None,
    "focus_start": None,
    "focus_last_activity": None,
    "focus_active_seconds": 0,
    "focus_status": "STOPPED",
    "last_heartbeat": None,
}

for key, value in DEFAULT_SESSION_VALUES.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# LOGIN / REGISTER
# ============================================================


def authentication_screen():

    st.title("⚙️ GATE ME")

    st.subheader(
        "Mechanical Engineering Preparation Platform"
    )

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

                st.success(
                    "Login successful."
                )

                st.rerun()

            else:

                st.error(
                    "Invalid email or password."
                )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    with register_tab:

        st.subheader(
            "Create Student Account"
        )

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
                "📊 Analytics",
                "🗓️ Study Planner",
                "👤 Profile",
            ],
        )

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True,
        ):

            # Stop an unfinished focus session safely.
            if st.session_state.focus_running:
                finalize_focus_session(
                    user["id"],
                    reason="LOGOUT",
                )

            for key, value in DEFAULT_SESSION_VALUES.items():
                st.session_state[key] = value

            st.rerun()

    return page


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


def seconds_between(
    start,
    end,
):

    if not start or not end:
        return 0

    difference = (
        end - start
    ).total_seconds()

    return max(
        0,
        int(difference),
    )


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

    if hours > 0:

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
# FOCUS DATABASE FUNCTIONS
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

    cur.execute(
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


def update_focus_heartbeat(
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

    last_heartbeat = parse_datetime(
        session["last_heartbeat"]
    )

    # --------------------------------------------------------
    # INACTIVITY CHECK
    # --------------------------------------------------------

    if last_activity:

        inactivity = (
            current - last_activity
        ).total_seconds()

        if inactivity > SESSION_TIMEOUT_SECONDS:

            conn.execute(
                """
                UPDATE focus_sessions
                SET
                    status = 'PAUSED_INACTIVE',
                    last_heartbeat = ?
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    current.isoformat(),
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
                    "AUTO_PAUSED_INACTIVE",
                    current.isoformat(),
                    session["category"],
                    0,
                ),
            )

            conn.commit()
            conn.close()

            return "INACTIVE"

    # --------------------------------------------------------
    # HEARTBEAT
    # --------------------------------------------------------

    increment = 0

    if last_heartbeat:

        elapsed = (
            current - last_heartbeat
        ).total_seconds()

        # Only accept reasonable heartbeat intervals.
        if 0 < elapsed <= 90:

            increment = int(elapsed)

    active_seconds = (
        session["active_seconds"] or 0
    ) + increment

    conn.execute(
        """
        UPDATE focus_sessions
        SET
            last_heartbeat = ?,
            active_seconds = ?,
            last_activity = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            current.isoformat(),
            active_seconds,
            session["last_activity"],
            session_id,
            user_id,
        ),
    )

    conn.commit()
    conn.close()

    return True


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

    previous_activity = parse_datetime(
        session["last_activity"]
    )

    previous_heartbeat = parse_datetime(
        session["last_heartbeat"]
    )

    increment = 0

    if previous_activity:

        elapsed = (
            current - previous_activity
        ).total_seconds()

        # Do not credit more than five minutes
        # from a single confirmation.
        increment = min(
            max(0, int(elapsed)),
            SESSION_TIMEOUT_SECONDS,
        )

    elif previous_heartbeat:

        elapsed = (
            current - previous_heartbeat
        ).total_seconds()

        increment = min(
            max(0, int(elapsed)),
            SESSION_TIMEOUT_SECONDS,
        )

    new_active_seconds = (
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
            new_active_seconds,
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


def pause_focus_session(
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

    if session:

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
                "MANUAL_PAUSE",
                current.isoformat(),
                session["category"],
                0,
            ),
        )

    conn.commit()
    conn.close()


def resume_focus_session(
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

    if session:

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
                current.isoformat(),
                current.isoformat(),
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
                "SESSION_RESUMED",
                current.isoformat(),
                session["category"],
                0,
            ),
        )

    conn.commit()
    conn.close()


def finalize_focus_session(
    user_id,
    reason="STOPPED",
):

    session_id = st.session_state.focus_session_id

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

        # Capture the last confirmed active interval,
        # but never more than the inactivity threshold.
        last_activity = parse_datetime(
            session["last_activity"]
        )

        active_seconds = (
            session["active_seconds"] or 0
        )

        if (
            last_activity
            and session["status"] == "ACTIVE"
        ):

            final_increment = min(
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

            active_seconds += final_increment

        duration_minutes = max(
            0,
            active_seconds // 60,
        )

        status = (
            "COMPLETED"
            if reason == "STOPPED"
            else reason
        )

        conn.execute(
            """
            UPDATE focus_sessions
            SET
                end_time = ?,
                duration_minutes = ?,
                active_seconds = ?,
                status = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                current.isoformat(),
                duration_minutes,
                active_seconds,
                status,
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
                "SESSION_FINISHED",
                current.isoformat(),
                session["category"],
                active_seconds,
            ),
        )

    conn.commit()
    conn.close()

    # Reset frontend session state.
    st.session_state.focus_running = False
    st.session_state.focus_session_id = None
    st.session_state.focus_category = None
    st.session_state.focus_start = None
    st.session_state.focus_last_activity = None
    st.session_state.focus_active_seconds = 0
    st.session_state.focus_status = "STOPPED"
    st.session_state.last_heartbeat = None


# ============================================================
# FOCUS STATISTICS
# ============================================================


def get_focus_statistics(
    user_id,
):

    today = date.today()

    today_start = datetime.combine(
        today,
        datetime.min.time(),
    )

    tomorrow_start = (
        today_start
        + timedelta(days=1)
    )

    week_start = (
        today_start
        - timedelta(
            days=today.weekday()
        )
    )

    conn = get_db()

    today_row = conn.execute(
        """
        SELECT
            COALESCE(
                SUM(active_seconds),
                0
            ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        AND start_time >= ?
        AND start_time < ?
        """,
        (
            user_id,
            today_start.isoformat(),
            tomorrow_start.isoformat(),
        ),
    ).fetchone()

    week_row = conn.execute(
        """
        SELECT
            COALESCE(
                SUM(active_seconds),
                0
            ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        AND start_time >= ?
        AND start_time < ?
        """,
        (
            user_id,
            week_start.isoformat(),
            tomorrow_start.isoformat(),
        ),
    ).fetchone()

    total_row = conn.execute(
        """
        SELECT
            COALESCE(
                SUM(active_seconds),
                0
            ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()

    category_rows = conn.execute(
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

    recent_rows = conn.execute(
        """
        SELECT
            category,
            start_time,
            end_time,
            active_seconds,
            duration_minutes,
            status
        FROM focus_sessions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 15
        """,
        (
            user_id,
        ),
    ).fetchall()

    daily_rows = conn.execute(
        """
        SELECT
            substr(start_time, 1, 10)
                AS study_date,
            COALESCE(
                SUM(active_seconds),
                0
            ) AS seconds
        FROM focus_sessions
        WHERE user_id = ?
        GROUP BY substr(start_time, 1, 10)
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
            dict(row)
            for row in category_rows
        ],
        "recent": [
            dict(row)
            for row in recent_rows
        ],
        "daily": [
            dict(row)
            for row in daily_rows
        ],
    }


# ============================================================
# DASHBOARD
# ============================================================


def dashboard(user):

    st.title("🏠 Dashboard")

    st.caption(
        "Your personal GATE Mechanical Engineering workspace."
    )

    stats = get_focus_statistics(
        user["id"]
    )

    today_seconds = stats["today"]
    week_seconds = stats["week"]

    daily_target_seconds = (
        user["daily_target"] * 60
    )

    weekly_target_seconds = (
        user["weekly_target"] * 60
    )

    daily_percentage = min(
        1.0,
        today_seconds
        / max(
            1,
            daily_target_seconds,
        ),
    )

    weekly_percentage = min(
        1.0,
        week_seconds
        / max(
            1,
            weekly_target_seconds,
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Today's Focus",
        format_duration(
            today_seconds
        ),
    )

    col2.metric(
        "Weekly Focus",
        format_duration(
            week_seconds
        ),
    )

    col3.metric(
        "Daily Target",
        f"{user['daily_target']} min",
    )

    col4.metric(
        "Weekly Target",
        f"{user['weekly_target']} min",
    )

    st.divider()

    st.subheader(
        "🎯 Today's Target"
    )

    st.progress(
        daily_percentage,
        text=(
            f"{today_seconds // 60} / "
            f"{user['daily_target']} minutes"
        ),
    )

    if today_seconds >= daily_target_seconds:

        st.success(
            "Daily study target completed."
        )

    else:

        remaining = (
            daily_target_seconds
            - today_seconds
        )

        st.info(
            f"{remaining // 60} minutes remaining "
            "for today's target."
        )

    st.subheader(
        "📅 Weekly Target"
    )

    st.progress(
        weekly_percentage,
        text=(
            f"{week_seconds // 60} / "
            f"{user['weekly_target']} minutes"
        ),
    )

    remaining_week = max(
        0,
        weekly_target_seconds
        - week_seconds,
    )

    st.caption(
        f"{remaining_week // 60} minutes remaining "
        "for this week's target."
    )

    st.divider()

    st.subheader(
        "📊 Study Categories"
    )

    category_columns = st.columns(
        len(FOCUS_CATEGORIES)
    )

    category_map = {
        item["category"]: item["seconds"]
        for item in stats["categories"]
    }

    for index, category in enumerate(
        FOCUS_CATEGORIES
    ):

        with category_columns[index]:

            seconds = category_map.get(
                category,
                0,
            )

            st.metric(
                category.replace(
                    "_",
                    " ",
                ),
                format_duration(seconds),
            )

    st.divider()

    st.subheader(
        "🧠 Learning Workspace"
    )

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
            "Review concepts that need attention."
        )

    st.divider()

    st.subheader(
        "📈 Recent Study Activity"
    )

    if stats["recent"]:

        display_rows = []

        for row in stats["recent"]:

            display_rows.append(
                {
                    "Category": row[
                        "category"
                    ].replace(
                        "_",
                        " ",
                    ),
                    "Start": row[
                        "start_time"
                    ],
                    "Duration": format_duration(
                        row[
                            "active_seconds"
                        ]
                    ),
                    "Status": row[
                        "status"
                    ],
                }
            )

        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No study sessions recorded yet."
        )


# ============================================================
# SYLLABUS PAGE
# ============================================================


def syllabus_page():

    st.title(
        "📚 GATE Mechanical Engineering Syllabus"
    )

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
                    key=(
                        f"syllabus_"
                        f"{subject}_"
                        f"{topic}"
                    ),
                )


# ============================================================
# FOCUS MODE
# ============================================================


def focus_mode(user):

    st.title("⏱️ Focus Mode")

    st.caption(
        "Phase 3 Study Intelligence — "
        "verified active study tracking."
    )

    # --------------------------------------------------------
    # ACTIVE SESSION
    # --------------------------------------------------------

    if st.session_state.focus_running:

        session_id = (
            st.session_state.focus_session_id
        )

        result = update_focus_heartbeat(
            user["id"],
            session_id,
        )

        if result == "INACTIVE":

            st.session_state.focus_status = (
                "PAUSED_INACTIVE"
            )

        # ----------------------------------------------------
        # GET CURRENT SESSION
        # ----------------------------------------------------

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

        st.subheader(
            "Current Focus Session"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Category",
                session["category"].replace(
                    "_",
                    " ",
                ),
            )

        with c2:

            st.metric(
                "Verified Active Time",
                format_duration(
                    active_seconds
                ),
            )

        with c3:

            st.metric(
                "Session Status",
                status.replace(
                    "_",
                    " ",
                ),
            )

        # ----------------------------------------------------
        # INACTIVE
        # ----------------------------------------------------

        if status == "PAUSED_INACTIVE":

            st.error(
                "⏸️ Session automatically paused "
                "because no activity was confirmed "
                "for more than 5 minutes."
            )

            st.write(
                "Resume only when you are ready to continue studying."
            )

            if st.button(
                "▶ RESUME STUDY",
                type="primary",
                use_container_width=True,
            ):

                resume_focus_session(
                    user["id"],
                    session_id,
                )

                st.session_state.focus_status = (
                    "ACTIVE"
                )

                st.success(
                    "Focus session resumed."
                )

                st.rerun()

        # ----------------------------------------------------
        # ACTIVE
        # ----------------------------------------------------

        elif status == "ACTIVE":

            st.success(
                "🟢 FOCUS SESSION ACTIVE"
            )

            st.warning(
                "The application does not treat an "
                "open browser tab as proof of studying."
            )

            st.write(
                "Use the confirmation below while you are actively studying."
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

                st.success(
                    "Activity confirmed."
                )

                st.rerun()

        # ----------------------------------------------------
        # CONTROLS
        # ----------------------------------------------------

        st.divider()

        c1, c2 = st.columns(2)

        with c1:

            if status == "ACTIVE":

                if st.button(
                    "⏸ PAUSE SESSION",
                    use_container_width=True,
                ):

                    pause_focus_session(
                        user["id"],
                        session_id,
                    )

                    st.rerun()

            else:

                if st.button(
                    "▶ RESUME SESSION",
                    use_container_width=True,
                ):

                    resume_focus_session(
                        user["id"],
                        session_id,
                    )

                    st.rerun()

        with c2:

            if st.button(
                "■ STOP & SAVE SESSION",
                type="primary",
                use_container_width=True,
            ):

                final_seconds = (
                    active_seconds
                )

                finalize_focus_session(
                    user["id"],
                    reason="STOPPED",
                )

                st.success(
                    "Focus session saved: "
                    + format_duration(
                        final_seconds
                    )
                )

                st.rerun()

        # ----------------------------------------------------
        # 30-SECOND HEARTBEAT INFORMATION
        # ----------------------------------------------------

        st.divider()

        st.caption(
            "System heartbeat: approximately every "
            f"{HEARTBEAT_SECONDS} seconds."
        )

        st.caption(
            "Inactivity timeout: "
            f"{SESSION_TIMEOUT_SECONDS // 60} minutes."
        )

        # Streamlit fragment automatically reruns
        # this section periodically on supported versions.
        try:

            @st.fragment(
                run_every=f"{HEARTBEAT_SECONDS}s"
            )
            def live_status():

                if (
                    st.session_state.focus_running
                ):

                    st.caption(
                        f"Last system check: "
                        f"{datetime.now().strftime('%H:%M:%S')}"
                    )

            live_status()

        except Exception:

            st.caption(
                "Live heartbeat refresh will be "
                "available with the current Streamlit version."
            )

    # --------------------------------------------------------
    # NO ACTIVE SESSION
    # --------------------------------------------------------

    else:

        st.info(
            "No focus session is currently running."
        )

        category = st.selectbox(
            "Study Category",
            FOCUS_CATEGORIES,
        )

        st.write(
            "Choose what you are studying before starting."
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
            st.session_state.focus_session_id = (
                session_id
            )
            st.session_state.focus_category = (
                category
            )
            st.session_state.focus_start = current
            st.session_state.focus_last_activity = (
                current
            )
            st.session_state.focus_active_seconds = (
                0
            )
            st.session_state.focus_status = (
                "ACTIVE"
            )
            st.session_state.last_heartbeat = (
                current
            )

            st.success(
                "Focus session started."
            )

            st.rerun()

    # --------------------------------------------------------
    # RECENT SESSIONS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "📋 Recent Focus Sessions"
    )

    conn = get_db()

    sessions = conn.execute(
        """
        SELECT
            category,
            start_time,
            end_time,
            active_seconds,
            status
        FROM focus_sessions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 15
        """,
        (
            user["id"],
        ),
    ).fetchall()

    conn.close()

    if sessions:

        rows = []

        for session in sessions:

            rows.append(
                {
                    "Category": session[
                        "category"
                    ].replace(
                        "_",
                        " ",
                    ),
                    "Start": session[
                        "start_time"
                    ],
                    "End": session[
                        "end_time"
                    ]
                    or "-",
                    "Active Time": format_duration(
                        session[
                            "active_seconds"
                        ]
                        or 0
                    ),
                    "Status": session[
                        "status"
                    ],
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No completed focus sessions yet."
        )


# ============================================================
# PRACTICE
# ============================================================


def practice_page():

    st.title("📝 Practice")

    st.info(
        "Practice engine foundation. "
        "Question evaluation will be expanded in Phase 4."
    )

    subject = st.selectbox(
        "Subject",
        list(SYLLABUS.keys()),
    )

    topic = st.selectbox(
        "Topic",
        SYLLABUS[subject],
    )

    notes = st.text_area(
        "Practice notes",
        placeholder=(
            "Write your solution, "
            "formula, mistake or doubt here..."
        ),
    )

    if st.button(
        "Save Practice Session",
        use_container_width=True,
    ):

        conn = get_db()

        conn.execute(
            """
            INSERT INTO study_progress
            (
                user_id,
                subject,
                topic,
                status,
                attempts
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                st.session_state.user_id,
                subject,
                topic,
                "IN_PROGRESS",
                1,
            ),
        )

        conn.commit()
        conn.close()

        st.success(
            "Practice activity recorded."
        )


# ============================================================
# PYQ
# ============================================================


def pyq_page():

    st.title(
        "📄 GATE Previous Year Questions"
    )

    st.info(
        "PYQ/CBT engine will be expanded with "
        "MCQ, MSQ and NAT evaluation."
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

    if st.button(
        "Start PYQ Session",
        type="primary",
        use_container_width=True,
    ):

        st.info(
            "PYQ session framework initialized."
        )


# ============================================================
# REVISION
# ============================================================


def revision_page():

    st.title("🔄 Revision")

    st.caption(
        "Phase 3 revision scheduling foundation."
    )

    user_id = st.session_state.user_id

    conn = get_db()

    revisions = conn.execute(
        """
        SELECT
            subject,
            topic,
            priority,
            next_revision,
            status
        FROM revision_queue
        WHERE user_id = ?
        ORDER BY
            priority DESC,
            next_revision ASC
        """,
        (
            user_id,
        ),
    ).fetchall()

    conn.close()

    if revisions:

        rows = []

        for item in revisions:

            rows.append(
                {
                    "Subject": item[
                        "subject"
                    ],
                    "Topic": item[
                        "topic"
                    ],
                    "Priority": item[
                        "priority"
                    ],
                    "Next Revision": item[
                        "next_revision"
                    ],
                    "Status": item[
                        "status"
                    ],
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No revision items have been generated yet."
        )

        st.write(
            "The adaptive weakness/retest engine will "
            "populate this queue in Phase 4."
        )


# ============================================================
# ANALYTICS
# ============================================================


def analytics_page(user):

    st.title("📊 Study Analytics")

    stats = get_focus_statistics(
        user["id"]
    )

    # --------------------------------------------------------
    # TOP METRICS
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Today",
            format_duration(
                stats["today"]
            ),
        )

    with col2:

        st.metric(
            "This Week",
            format_duration(
                stats["week"]
            ),
        )

    with col3:

        st.metric(
            "Lifetime",
            format_duration(
                stats["total"]
            ),
        )

    st.divider()

    # --------------------------------------------------------
    # CATEGORY ANALYSIS
    # --------------------------------------------------------

    st.subheader(
        "📚 Time by Study Category"
    )

    if stats["categories"]:

        category_data = []

        for row in stats["categories"]:

            category_data.append(
                {
                    "Category": row[
                        "category"
                    ].replace(
                        "_",
                        " ",
                    ),
                    "Minutes": round(
                        row["seconds"]
                        / 60,
                        1,
                    ),
                }
            )

        st.bar_chart(
            {
                item["Category"]: item["Minutes"]
                for item in category_data
            }
        )

    else:

        st.info(
            "Study-category analytics will appear "
            "after you complete focus sessions."
        )

    st.divider()

    # --------------------------------------------------------
    # DAILY ANALYSIS
    # --------------------------------------------------------

    st.subheader(
        "📅 Recent Daily Study Time"
    )

    if stats["daily"]:

        daily_data = {}

        for row in reversed(
            stats["daily"]
        ):

            daily_data[
                row["study_date"]
            ] = round(
                row["seconds"]
                / 60,
                1,
            )

        st.line_chart(
            daily_data
        )

    else:

        st.info(
            "Daily analytics will appear after study activity."
        )

    st.divider()

    # --------------------------------------------------------
    # TARGET ANALYSIS
    # --------------------------------------------------------

    st.subheader(
        "🎯 Target Analysis"
    )

    daily_target = user[
        "daily_target"
    ]

    weekly_target = user[
        "weekly_target"
    ]

    today_minutes = (
        stats["today"] // 60
    )

    week_minutes = (
        stats["week"] // 60
    )

    target_rows = [
        {
            "Target": "Daily",
            "Target Minutes": daily_target,
            "Completed Minutes": today_minutes,
            "Remaining": max(
                0,
                daily_target
                - today_minutes,
            ),
        },
        {
            "Target": "Weekly",
            "Target Minutes": weekly_target,
            "Completed Minutes": week_minutes,
            "Remaining": max(
                0,
                weekly_target
                - week_minutes,
            ),
        },
    ]

    st.dataframe(
        target_rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# STUDY PLANNER
# ============================================================


def study_planner_page(user):

    st.title("🗓️ Study Planner")

    st.caption(
        "Create a personal study plan using your actual targets."
    )

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

    planned_minutes = st.number_input(
        "Planned Study Time (minutes)",
        min_value=15,
        max_value=720,
        value=60,
        step=15,
    )

    if st.button(
        "➕ Add Study Plan",
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
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                selected_date.isoformat(),
                subject,
                topic,
                planned_minutes,
                "PLANNED",
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

    st.subheader(
        "📋 Your Study Plan"
    )

    conn = get_db()

    plans = conn.execute(
        """
        SELECT
            id,
            plan_date,
            subject,
            topic,
            planned_minutes,
            status
        FROM study_plan
        WHERE user_id = ?
        ORDER BY
            plan_date ASC,
            id ASC
        """,
        (
            user["id"],
        ),
    ).fetchall()

    conn.close()

    if plans:

        rows = []

        for plan in plans:

            rows.append(
                {
                    "Date": plan[
                        "plan_date"
                    ],
                    "Subject": plan[
                        "subject"
                    ],
                    "Topic": plan[
                        "topic"
                    ],
                    "Planned Minutes": plan[
                        "planned_minutes"
                    ],
                    "Status": plan[
                        "status"
                    ],
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No study plans created yet."
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

        submitted = st.form_submit_button(
            "Save Profile",
            use_container_width=True,
        )

        if submitted:

            if weekly < daily:

                st.error(
                    "Weekly target should normally be "
                    "greater than or equal to the daily target."
                )

            else:

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

    if user is None:

        for key, value in DEFAULT_SESSION_VALUES.items():
            st.session_state[key] = value

        st.rerun()

    page = sidebar(user)

    # --------------------------------------------------------
    # ROUTING
    # --------------------------------------------------------

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

    elif page == "📊 Analytics":

        analytics_page(user)

    elif page == "🗓️ Study Planner":

        study_planner_page(user)

    elif page == "👤 Profile":

        profile_page(user)
