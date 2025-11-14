import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import os
from dotenv import load_dotenv

# -------------------------------
# Streamlit Config
# -------------------------------
st.set_page_config(
    page_title="Valorant Player Statistics Tracker",
    page_icon="https://img.icons8.com/?size=100&id=aUZxT3Erwill&format=png&color=000000",
    layout="wide",
)

# -------------------------------
# Env + DB
# -------------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=RealDictCursor)

# -------------------------------
# AUTH HELPERS
# -------------------------------
def get_user(username):
    query = "SELECT * FROM users WHERE username = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (username,))
            return cur.fetchone()

def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def register_user(username, password):
    """Register new player user"""
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'player')",
                    (username, hashed),
                )
                conn.commit()
                return True
    except Exception as e:
        st.error(f"Error registering user: {e}")
        return False

def login(username, password):
    user = get_user(username)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None

# -------------------------------
# MATCH HELPERS
# -------------------------------
def calculate_kd_ratio(kills, deaths):
    return kills if deaths == 0 else kills / deaths

def add_match(user_id, player_name, win_loss, map_name, agent, current_rank, acs, econ_rating, kills, deaths, assists):
    query = """
        INSERT INTO matches (user_id, player_name, win_loss, map_name, agent, current_rank, acs, econ_rating, kills, deaths, assists)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, player_name, win_loss, map_name, agent, current_rank, acs, econ_rating, kills, deaths, assists))
            conn.commit()

def delete_match(record_id, user):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user["role"] == "player":
                cur.execute("DELETE FROM matches WHERE id = %s AND user_id = %s", (record_id, user["id"]))
            else:
                cur.execute("DELETE FROM matches WHERE id = %s", (record_id,))
            conn.commit()

def fetch_matches_by_user(username):
    query = "SELECT * FROM matches WHERE player_name = %s ORDER BY id DESC"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (username,))
            return cur.fetchall()

def fetch_all_matches():
    query = "SELECT * FROM matches ORDER BY id DESC"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()

def aggregate_player_stats(data):
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["K/D Ratio"] = df.apply(lambda row: calculate_kd_ratio(row["kills"], row["deaths"]), axis=1)
    aggregated_df = (
        df.groupby("player_name")
        .agg({
            "acs": "mean",
            "econ_rating": "mean",
            "kills": "sum",
            "deaths": "sum",
            "assists": "sum",
            "K/D Ratio": "mean",
            "win_loss": "count"
        })
        .reset_index()
        .rename(columns={"win_loss": "matches_played", "acs": "avg_acs", "econ_rating": "avg_econ_rating"})
    )
    return aggregated_df.round(2)

def rank_players(aggregated_df):
    ranked_df = aggregated_df.sort_values(by="avg_acs", ascending=False).reset_index(drop=True)
    ranked_df.index += 1
    return ranked_df

# -------------------------------
# LOGIN / REGISTER SCREEN
# -------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Register"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login"):
            user = login(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Welcome {user['username']} ({user['role'].capitalize()})")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        st.subheader("Player Registration")
        new_user = st.text_input("Choose a Username", key="reg_user")
        new_pass = st.text_input("Choose a Password", type="password", key="reg_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="reg_confirm")

        if st.button("Register"):
            if new_pass != confirm_pass:
                st.error("Passwords do not match.")
            elif get_user(new_user):
                st.error("Username already exists.")
            else:
                if register_user(new_user, new_pass):
                    st.success("✅ Registration successful! You can now log in.")
    st.stop()

# -------------------------------
# MAIN APP (Authenticated)
# -------------------------------
user = st.session_state.user

st.sidebar.write(f"👋 Logged in as **{user['username']}**")
st.sidebar.write(f"🛠️ Role: **{user['role'].capitalize()}**")
st.sidebar.write("---")
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

st.title("🎯 Valorant Player Statistics Tracker")

# -------------------------------
# ADD MATCH SECTION
# -------------------------------
with st.form("match_form"):
    st.subheader("Enter Match Details")

    is_player = user["role"] == "player"
    player_name = st.text_input(
        "Player Name",
        value=user["username"] if is_player else "",
        disabled=is_player,
        key="player_name_input"
    )

    win_loss = st.selectbox("Win/Loss", ["Win", "Loss"])
    map_name = st.selectbox("Map", ["Bind", "Split", "Ascent", "Haven", "Breeze", "Fracture", "Icebox", "Pearl", "Sunset", "Abyss"])
    agent = st.selectbox("Agent", ["Astra", "Breach", "Brimstone", "Chamber", "Clove", "Cypher", "Deadlock", "Harbor", "Iso", "Jett", "Kay/O", "Killjoy", "Neon", "Omen", "Phoenix", "Raze", "Reyna", "Sage", "Skye", "Sova", "Viper", "Vyse", "Yoru"])
    current_rank = st.selectbox("Current Rank", ["Unranked", "Iron 1", "Iron 2", "Iron 3", "Bronze 1", "Bronze 2", "Bronze 3", "Silver 1", "Silver 2", "Silver 3", "Gold 1", "Gold 2", "Gold 3", "Platinum 1", "Platinum 2", "Platinum 3", "Diamond 1", "Diamond 2", "Diamond 3", "Ascendant 1", "Ascendant 2", "Ascendant 3", "Immortal 1", "Immortal 2", "Immortal 3", "Radiant"])
    acs = st.number_input("Average Combat Score (ACS)", min_value=0)
    econ_rating = st.number_input("Econ Rating", min_value=0.0)
    kills = st.number_input("Kills", min_value=0)
    deaths = st.number_input("Deaths", min_value=0)
    assists = st.number_input("Assists", min_value=0)
    submitted = st.form_submit_button("Add Match")

    if submitted:
        if is_player:
            player_name = user["username"]
        if not player_name:
            st.error("Player name is required.")
        if not acs or kills is None or deaths is None or assists is None:
            st.error("Please fill in all required fields.")
        else:
            add_match(user["id"], player_name, win_loss, map_name, agent, current_rank, acs, econ_rating, kills, deaths, assists)
            st.success("✅ Match details added successfully!")

# -------------------------------
# DELETE MATCH SECTION
# -------------------------------
with st.form("delete_form"):
    st.subheader("Delete a Record")
    match_data = fetch_matches_by_user(user["username"]) if user["role"] == "player" else fetch_all_matches()
    if match_data:
        df = pd.DataFrame(match_data)
        # record_options = df.apply(lambda row: f"{row['id']} | {row['player_name']} | {row['map_name']} | {row['agent']} | {row['current_rank']} | {row['kills']}/{row['deaths']}", axis=1)
        record_options = df.apply(lambda row: f"{row['player_name']} | {row['map_name']} | {row['agent']} | {row['current_rank']} | {row['kills']}/{row['deaths']}", axis=1)
        record_to_delete = st.selectbox("Select Record to Delete", record_options)
        if st.form_submit_button("Delete Record"):
            record_id = int(record_to_delete.split(" | ")[0])
            delete_match(record_id, user)
            st.success("🗑️ Record deleted successfully!")

# -------------------------------
# DISPLAY SECTION
# -------------------------------
if user["role"] == "admin":
    match_data = fetch_all_matches()
else:
    match_data = fetch_matches_by_user(user["username"])

# Always fetch all for leaderboard
all_match_data = fetch_all_matches()

if match_data:
    df = pd.DataFrame(match_data)
    df["K/D Ratio"] = df.apply(lambda row: calculate_kd_ratio(row["kills"], row["deaths"]), axis=1)

    st.subheader("🎯 Your Match Records" if user["role"] == "player" else "🎯 All Match Records")
    st.dataframe(df.drop(columns=["user_id", "id"]), width='stretch')
else:
    st.info("No match data available. Please add match details.")

if all_match_data:
    aggregated_df = aggregate_player_stats(all_match_data)
    if not aggregated_df.empty:
        st.subheader("🏆 Leaderboard: Ranked Players by Avg ACS")
        ranked_df = rank_players(aggregated_df)
        st.dataframe(ranked_df, width='stretch')
else:
    st.info("No leaderboard data available.")
