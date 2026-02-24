"""
Football Statistics Dashboard - Streamlit App
Production-ready dashboard for football analytics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np

# Elasticsearch (optional)
try:
    from elasticsearch import Elasticsearch
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="⚽ Football Stats Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Load environment
load_dotenv()

# Database connection
@st.cache_resource
def get_database_connection():
    """Create database connection"""
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'football_stats_db'),
        'user': os.getenv('DB_USER', 'football_user'),
        'password': os.getenv('DB_PASS')
    }
    
    conn_string = (
        f"postgresql://{db_config['user']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )
    
    return create_engine(conn_string)


@st.cache_data(ttl=3600)
def load_data(query: str):
    """Load data from database with caching"""
    engine = get_database_connection()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn)


# ============================================================================
# DATA LOADING QUERIES
# ============================================================================

def get_competition_stats():
    """Get competition statistics"""
    query = """
    SELECT * FROM gold.agg_competition_stats
    ORDER BY match_year DESC, competition_code
    """
    return load_data(query)


def get_team_performance():
    """Get team performance statistics"""
    query = """
    SELECT * FROM gold.agg_team_performance
    ORDER BY total_points DESC, goal_difference DESC
    """
    return load_data(query)


def get_recent_matches(limit=100):
    """Get recent matches"""
    query = f"""
    SELECT 
        match_date,
        match_year,
        competition_name,
        home_team_name,
        away_team_name,
        fulltime_home_score,
        fulltime_away_score,
        match_outcome
    FROM gold.fact_matches
    ORDER BY match_date DESC
    LIMIT {limit}
    """
    return load_data(query)


def get_matches_by_team(team_name):
    """Get matches for a specific team"""
    query = f"""
    SELECT 
        match_date,
        competition_name,
        home_team_name,
        away_team_name,
        fulltime_home_score,
        fulltime_away_score,
        match_outcome,
        CASE 
            WHEN home_team_name = '{team_name}' AND winner = 'HOME_TEAM' THEN 'Win'
            WHEN away_team_name = '{team_name}' AND winner = 'AWAY_TEAM' THEN 'Win'
            WHEN winner = 'DRAW' THEN 'Draw'
            ELSE 'Loss'
        END as result
    FROM gold.fact_matches
    WHERE home_team_name = '{team_name}' OR away_team_name = '{team_name}'
    ORDER BY match_date DESC
    """
    return load_data(query)


@st.cache_resource(ttl=3600)
def train_match_predictor():
    """Fetches ML features and trains a model"""
    query = """
    SELECT 
        match_result_encoded, 
        value_advantage_pct, 
        home_team_win_rate, 
        away_team_win_rate,
        home_advantage_score,
        temperature, 
        rain_mm
    FROM gold.mart_prediction_features
    WHERE match_result_encoded IS NOT NULL
    """
    df = load_data(query)
    
    if df.empty or len(df) < 50:
        return None, None
        
    df.fillna(0, inplace=True)
    
    features = ['value_advantage_pct', 'home_team_win_rate', 'away_team_win_rate', 'home_advantage_score', 'temperature', 'rain_mm']
    X = df[features]
    y = df['match_result_encoded']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train, y_train)
    
    acc = accuracy_score(y_test, model.predict(X_test))
    
    return model, acc


def get_latest_team_stats(team_name, is_home):
    """Fetches the latest stats for a given team to use in prediction"""
    query = f"""
    SELECT 
        (SELECT COALESCE(win_rate, 0) FROM gold.mart_team_stats WHERE team_name = '{team_name}' LIMIT 1) as win_pct,
        (SELECT COALESCE(
            CASE WHEN home_team_name = '{team_name}' THEN home_market_value ELSE away_market_value END, 
        0) FROM gold.fact_matches_full WHERE home_team_name = '{team_name}' OR away_team_name = '{team_name}' ORDER BY match_date DESC LIMIT 1) as team_market_value
    """
    df = load_data(query)
    if not df.empty:
        return float(df.iloc[0]['win_pct'] or 0.0), float(df.iloc[0]['team_market_value'] or 0.0)
    return 0.0, 0.0


# ============================================================================
# DASHBOARD LAYOUT
# ============================================================================

def main():
    
    # Header
    st.markdown('<h1 class="main-header">⚽ Football Statistics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/football2--v1.png", width=100)
        st.title("Navigation")
        
        page = st.radio(
            "Select View",
            ["📊 Overview", "🏆 Competition Analysis", "👥 Team Performance", "📈 Match Analysis", "🔍 Team Deep Dive", "🔮 Match Probability", "📰 News Search"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("### 🎯 Filters")
        
        # Get dynamic options directly from data
        try:
            comp_stats_for_filters = get_competition_stats()
            # Year filter
            available_years = sorted(comp_stats_for_filters['match_year'].unique().tolist(), reverse=True)
            selected_year = st.selectbox(
                "📅 Select Season",
                options=["All Years"] + available_years,
                index=0
            )
            
            # Competition filter
            available_competitions = sorted(comp_stats_for_filters['competition_name'].unique().tolist())
            selected_competition_filter = st.selectbox(
                "🏆 Select Competition",
                options=["All Competitions"] + available_competitions,
                index=0
            )
        except Exception as e:
            # Fallback in case of DB issues
            selected_year = "All Years"
            selected_competition_filter = "All Competitions"
            st.error("Could not load filters from database")
        
        st.markdown("---")
        st.markdown("### 📅 Data Refresh")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.success("Data refreshed!")
        
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.info("This dashboard displays football statistics from Premier League, La Liga, and Ligue 1.")
    
    # ========================================================================
    # PAGE: OVERVIEW
    # ========================================================================
    
    if page == "📊 Overview":
        st.header("📊 Overall Statistics")
        
        # Load data
        comp_stats = get_competition_stats()
        team_perf = get_team_performance()
        recent = get_recent_matches(100)
        
        # Apply year filter
        if selected_year != "All Years":
            comp_stats = comp_stats[comp_stats['match_year'] == int(selected_year)]
            recent = recent[recent['match_year'] == int(selected_year)]
        
        # Apply competition filter
        if selected_competition_filter != "All Competitions":
            comp_stats = comp_stats[comp_stats['competition_name'] == selected_competition_filter]
            recent = recent[recent['competition_name'] == selected_competition_filter]
            if not comp_stats.empty:
                comp_code = comp_stats['competition_code'].iloc[0]
                team_perf = team_perf[team_perf['competition_code'] == comp_code]
            else:
                team_perf = pd.DataFrame(columns=team_perf.columns)
        
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_matches = comp_stats['total_matches'].sum()
            st.metric("Total Matches", f"{total_matches:,}")
        
        with col2:
            total_goals = comp_stats['total_goals'].sum()
            st.metric("Total Goals", f"{total_goals:,}")
        
        with col3:
            avg_goals = comp_stats['avg_goals_per_match'].mean()
            st.metric("Avg Goals/Match", f"{avg_goals:.2f}")
        
        with col4:
            total_teams = len(team_perf)
            st.metric("Total Teams", total_teams)
        
        st.markdown("---")
        
        # Recent Matches
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🔥 Recent Matches")
            
            # Format recent matches for display
            recent_display = recent.head(10).copy()
            
            if not recent_display.empty:
                recent_display['Match'] = (
                    recent_display['home_team_name'] + ' ' +
                    recent_display['fulltime_home_score'].astype(str) + ' - ' +
                    recent_display['fulltime_away_score'].astype(str) + ' ' +
                    recent_display['away_team_name']
                )
                
                st.dataframe(
                    recent_display[['match_date', 'competition_name', 'Match', 'match_outcome']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No recent matches found for this filter.")
        
        with col2:
            st.subheader("📈 Competition Distribution")
            comp_dist = comp_stats.groupby('competition_name')['total_matches'].sum()
            
            fig = px.pie(
                values=comp_dist.values,
                names=comp_dist.index,
                title="Matches by Competition"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # PAGE: COMPETITION ANALYSIS
    # ========================================================================
    
    elif page == "🏆 Competition Analysis":
        st.header("🏆 Competition Analysis")
        
        comp_stats = get_competition_stats()
        
        # Apply year filter from sidebar
        if selected_year != "All Years":
            comp_stats = comp_stats[comp_stats['match_year'] == int(selected_year)]
        
        # Filter by competition
        selected_comp = st.selectbox(
            "Select Competition",
            comp_stats['competition_name'].unique()
        )
        
        comp_data = comp_stats[comp_stats['competition_name'] == selected_comp]
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Matches", comp_data['total_matches'].sum())
        
        with col2:
            st.metric("Total Goals", comp_data['total_goals'].sum())
        
        with col3:
            st.metric("Avg Goals/Match", f"{comp_data['avg_goals_per_match'].mean():.2f}")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 Home Advantage Analysis")
            
            fig = go.Figure(data=[
                go.Bar(name='Home Wins', x=comp_data['match_year'], y=comp_data['home_win_percentage']),
                go.Bar(name='Away Wins', x=comp_data['match_year'], y=comp_data['away_win_percentage']),
                go.Bar(name='Draws', x=comp_data['match_year'], y=comp_data['draw_percentage'])
            ])
            
            fig.update_layout(barmode='group', yaxis_title='Percentage (%)')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("⚽ Goals Trend")
            
            fig = px.line(
                comp_data,
                x='match_year',
                y='avg_goals_per_match',
                markers=True,
                title='Average Goals per Match by Year'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Detailed stats table
        st.subheader("📊 Detailed Statistics")
        st.dataframe(comp_data, use_container_width=True, hide_index=True)
    
    # ========================================================================
    # PAGE: TEAM PERFORMANCE
    # ========================================================================
    
    elif page == "👥 Team Performance":
        st.header("👥 Team Performance Rankings")
        
        team_perf = get_team_performance()
        
        # Apply competition filter from sidebar if set
        if selected_competition_filter != "All Competitions":
            full_stats = get_competition_stats()
            comp_code_row = full_stats[full_stats['competition_name'] == selected_competition_filter]
            comp_code = comp_code_row['competition_code'].iloc[0] if not comp_code_row.empty else None
            team_perf = team_perf[team_perf['competition_code'] == comp_code]
        
        # Filter by competition (page level)
        selected_comp = st.selectbox(
            "Select Competition",
            team_perf['competition_code'].unique()
        )
        
        filtered_teams = team_perf[team_perf['competition_code'] == selected_comp].copy()
        
        # Top performers
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("🥇 Most Points")
            top_points = filtered_teams.nlargest(5, 'total_points')[['team_name', 'total_points']]
            st.dataframe(top_points, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("⚽ Most Goals")
            top_goals = filtered_teams.nlargest(5, 'total_goals_scored')[['team_name', 'total_goals_scored']]
            st.dataframe(top_goals, use_container_width=True, hide_index=True)
        
        with col3:
            st.subheader("🛡️ Best Defense")
            best_defense = filtered_teams.nsmallest(5, 'total_goals_conceded')[['team_name', 'total_goals_conceded']]
            st.dataframe(best_defense, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Standings visualization
        st.subheader("📊 League Standings")
        
        fig = px.bar(
            filtered_teams.head(20),
            x='total_points',
            y='team_name',
            orientation='h',
            color='goal_difference',
            title='Team Rankings by Points',
            labels={'total_points': 'Points', 'team_name': 'Team', 'goal_difference': 'Goal Diff'}
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
        
        # Full table
        st.subheader("📋 Complete Standings")
        
        display_cols = [
            'team_name', 'total_matches', 'total_wins', 'total_draws', 'total_losses',
            'total_goals_scored', 'total_goals_conceded', 'goal_difference', 'total_points',
            'win_percentage', 'points_per_match'
        ]
        
        st.dataframe(
            filtered_teams[display_cols],
            use_container_width=True,
            hide_index=True
        )
    
    # ========================================================================
    # PAGE: MATCH ANALYSIS
    # ========================================================================
    
    elif page == "📈 Match Analysis":
        st.header("📈 Match Statistics Analysis")
        
        comp_stats = get_competition_stats()
        
        # Apply year filter from sidebar
        if selected_year != "All Years":
            comp_stats = comp_stats[comp_stats['match_year'] == int(selected_year)]
        
        # Apply competition filter from sidebar
        if selected_competition_filter != "All Competitions":
            comp_stats = comp_stats[comp_stats['competition_name'] == selected_competition_filter]
        
        # High scoring matches analysis
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 High Scoring Matches")
            
            fig = px.bar(
                comp_stats,
                x='competition_name',
                y='high_scoring_percentage',
                color='match_year',
                barmode='group',
                title='High Scoring Matches (>3 goals) by Competition',
                labels={'high_scoring_percentage': 'Percentage (%)', 'competition_name': 'Competition'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📊 Goals Distribution")
            
            fig = px.box(
                comp_stats,
                x='competition_name',
                y='avg_goals_per_match',
                color='competition_name',
                title='Goals per Match Distribution'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Home vs Away analysis
        st.subheader("🏠 Home vs Away Performance")
        
        home_away_data = comp_stats.groupby('competition_name').agg({
            'home_win_percentage': 'mean',
            'away_win_percentage': 'mean',
            'draw_percentage': 'mean'
        }).reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=home_away_data['competition_name'], y=home_away_data['home_win_percentage'], name='Home Wins'))
        fig.add_trace(go.Bar(x=home_away_data['competition_name'], y=home_away_data['away_win_percentage'], name='Away Wins'))
        fig.add_trace(go.Bar(x=home_away_data['competition_name'], y=home_away_data['draw_percentage'], name='Draws'))
        
        fig.update_layout(barmode='stack', yaxis_title='Percentage (%)', title='Match Outcomes by Competition')
        st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # PAGE: TEAM DEEP DIVE
    # ========================================================================
    
    elif page == "🔍 Team Deep Dive":
        st.header("🔍 Team Deep Dive Analysis")
        
        team_perf = get_team_performance()
        
        # Apply competition filter from sidebar
        if selected_competition_filter != "All Competitions":
            full_stats = get_competition_stats()
            comp_code_row = full_stats[full_stats['competition_name'] == selected_competition_filter]
            comp_code = comp_code_row['competition_code'].iloc[0] if not comp_code_row.empty else None
            team_perf = team_perf[team_perf['competition_code'] == comp_code]
        
        # Team selector
        selected_team = st.selectbox(
            "Select Team",
            sorted(team_perf['team_name'].unique())
        )
        
        # Get team data
        team_data = team_perf[team_perf['team_name'] == selected_team].iloc[0]
        team_matches = get_matches_by_team(selected_team)
        
        # Team overview metrics
        st.subheader(f"📊 {selected_team} - Season Overview")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Matches Played", int(team_data['total_matches']))
        
        with col2:
            st.metric("Total Points", int(team_data['total_points']))
        
        with col3:
            st.metric("Win Rate", f"{team_data['win_percentage']:.1f}%")
        
        with col4:
            st.metric("Goals Scored", int(team_data['total_goals_scored']))
        
        with col5:
            st.metric("Goal Difference", int(team_data['goal_difference']))
        
        st.markdown("---")
        
        # Performance breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Win/Draw/Loss")
            
            wdl_data = pd.DataFrame({
                'Result': ['Wins', 'Draws', 'Losses'],
                'Count': [team_data['total_wins'], team_data['total_draws'], team_data['total_losses']]
            })
            
            fig = px.pie(wdl_data, values='Count', names='Result', 
                        color_discrete_sequence=['#2ecc71', '#f39c12', '#e74c3c'])
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("🏠 Home vs Away")
            
            home_away = pd.DataFrame({
                'Venue': ['Home', 'Away'],
                'Wins': [team_data['home_wins'], team_data['away_wins']],
                'Matches': [team_data['home_matches'], team_data['away_matches']]
            })
            
            fig = go.Figure(data=[
                go.Bar(name='Wins', x=home_away['Venue'], y=home_away['Wins']),
                go.Bar(name='Matches', x=home_away['Venue'], y=home_away['Matches'])
            ])
            fig.update_layout(barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        
        # Recent form
        st.subheader("📅 Recent Matches")
        
        if not team_matches.empty:
            team_matches_display = team_matches.copy()
            team_matches_display['Score'] = (
                team_matches_display['fulltime_home_score'].astype(str) + ' - ' +
                team_matches_display['fulltime_away_score'].astype(str)
            )
            
            st.dataframe(
                team_matches_display[['match_date', 'competition_name', 'home_team_name', 'away_team_name', 'Score', 'result']].head(20),
                use_container_width=True,
                hide_index=True
            )
            
            # Form chart
            recent_form = team_matches.head(10)['result'].value_counts()
            
            fig = px.bar(
                x=recent_form.index,
                y=recent_form.values,
                title='Last 10 Matches Form',
                labels={'x': 'Result', 'y': 'Count'},
                color=recent_form.index,
                color_discrete_map={'Win': '#2ecc71', 'Draw': '#f39c12', 'Loss': '#e74c3c'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No match data available for this team")
    
    # ========================================================================
    # PAGE: MATCH PREDICTION
    # ========================================================================
    
    elif page == "🔮 Match Probability":
        st.header("🔮 Match Probability Calculator")
        st.markdown("Calculate the statistical probability of a match outcome based on historical market value, team form, and weather conditions.")
        
        with st.spinner("Processing Historical Data..."):
            model, accuracy = train_match_predictor()
            
        if model:
            st.success(f"Data processed successfully! (Confidence Score: {accuracy*100:.1f}%)")
            
            # Fetch all teams to populate dropdowns
            teams_df = get_team_performance()
            all_teams = sorted(teams_df['team_name'].unique()) if not teams_df.empty else ["Team A", "Team B"]
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🏠 Home Team")
                home_input = st.selectbox("Select Home Team", all_teams, index=0)
                
            with col2:
                st.subheader("✈️ Away Team")
                away_input = st.selectbox("Select Away Team", all_teams, index=min(1, len(all_teams)-1))
                
            st.markdown("---")
            st.subheader("🌦️ Match Conditions")
            col3, col4 = st.columns(2)
            with col3:
                temp_input = st.slider("Temperature (°C)", -5, 40, 15)
            with col4:
                rain_input = st.slider("Rain (mm/h)", 0.0, 50.0, 0.0)
                
            if st.button("🔮 Predict Match Outcome", type="primary"):
                if home_input == away_input:
                    st.error("Please select two different teams!")
                else:
                    # Get pseudo-live stats
                    home_win_pct, home_mv = get_latest_team_stats(home_input, True)
                    away_win_pct, away_mv = get_latest_team_stats(away_input, False)
                    
                    # Compute derived features like in dbt
                    combined_mv = home_mv + away_mv
                    if combined_mv > 0:
                        value_adv = (home_mv - away_mv) / combined_mv
                    else:
                        value_adv = 0.0
                        
                    # Simulate a basic home advantage score
                    home_adv_score = value_adv * 10 
                    
                    # Construct feature array
                    # Order: 'value_advantage_pct', 'home_team_win_rate', 'away_team_win_rate', 'home_advantage_score', 'temperature', 'rain_mm'
                    X_pred = np.array([[value_adv, home_win_pct, away_win_pct, home_adv_score, temp_input, rain_input]])
                    
                    # Predict probabilities
                    probs = model.predict_proba(X_pred)[0]
                    classes = model.classes_  # e.g., [-1, 0, 1]
                    
                    # Map classes to outcome labels
                    # We know from DBT: 1=home win, 0=draw, -1=away win
                    prob_dict = {c: p for c, p in zip(classes, probs)}
                    
                    home_prob = prob_dict.get(1, 0)
                    draw_prob = prob_dict.get(0, 0)
                    away_prob = prob_dict.get(-1, 0)
                    
                    # Display Results
                    st.markdown("### 📊 Prediction Results")
                    
                    res_col1, res_col2, res_col3 = st.columns(3)
                    with res_col1:
                        st.metric(f"🏠 {home_input} Win", f"{home_prob*100:.1f}%")
                    with res_col2:
                         st.metric("🤝 Draw", f"{draw_prob*100:.1f}%")
                    with res_col3:
                        st.metric(f"✈️ {away_input} Win", f"{away_prob*100:.1f}%")
                        
                    # Visualise
                    prob_df = pd.DataFrame({
                        "Outcome": [f"{home_input} Win", "Draw", f"{away_input} Win"],
                        "Probability": [home_prob, draw_prob, away_prob]
                    })
                    
                    fig = px.bar(
                        prob_df, 
                        x="Probability", 
                        y="Outcome", 
                        orientation="h",
                        color="Outcome",
                        color_discrete_map={f"{home_input} Win": "#2ecc71", "Draw": "#f39c12", f"{away_input} Win": "#e74c3c"},
                        title="Win Probabilities"
                    )
                    fig.update_layout(xaxis=dict(tickformat=".0%"))
                    st.plotly_chart(fig, use_container_width=True)
                    
        else:
            st.warning("Not enough historical data to train model yet. Ensure dbt models have run.")

    elif page == "📰 News Search":
        st.header("📰 Football News Search")
        st.markdown("Search football news from BBC, ESPN, L'Equipe, Marca, Guardian and more.")
        
        es_host = os.getenv('ES_HOST', 'localhost')
        es_port = os.getenv('ES_PORT', '9200')
        
        if not ES_AVAILABLE:
            st.error("❌ `elasticsearch` Python package not installed. Run: `pip install elasticsearch`")
        else:
            try:
                es = Elasticsearch([f"http://{es_host}:{es_port}"], request_timeout=10)
                es_connected = es.ping()
            except Exception:
                es_connected = False
            
            if not es_connected:
                st.warning(f"⚠️ Cannot connect to Elasticsearch at {es_host}:{es_port}. Make sure it's running.")
                st.info("💡 Start with: `docker-compose up -d elasticsearch`")
            else:
                # Check if index exists
                index_exists = es.indices.exists(index="football_news")
                
                if not index_exists:
                    st.warning("⚠️ No news indexed yet. Run the news extractor first:")
                    st.code("python extractor/fetch_football_news.py", language="bash")
                else:
                    # Get index stats
                    try:
                        news_count = es.count(index="football_news")["count"]
                        st.success(f"✅ Connected to Elasticsearch — **{news_count:,}** articles indexed")
                    except Exception:
                        news_count = 0
                    
                    col_search, col_lang = st.columns([3, 1])
                    with col_search:
                        search_query = st.text_input(
                            "🔍 Search football news",
                            placeholder="e.g. Mbappé transfer, Arsenal derby, Ligue 1 résultats...",
                            key="news_search"
                        )
                    with col_lang:
                        lang_filter = st.selectbox(
                            "🌐 Language",
                            ["All", "English", "French", "Spanish"],
                            index=0
                        )
                    
                    col_f1, col_f2, col_f3 = st.columns(3)
                    with col_f1:
                        league_filter = st.multiselect(
                            "🏆 League",
                            ["PL", "FL1", "PD", "CL", "UEL"],
                            default=[]
                        )
                    with col_f2:
                        # Get available sources from ES
                        try:
                            src_agg = es.search(
                                index="football_news",
                                body={"size": 0, "aggs": {"sources": {"terms": {"field": "source_name", "size": 20}}}},
                            )
                            available_sources = [b["key"] for b in src_agg["aggregations"]["sources"]["buckets"]]
                        except Exception:
                            available_sources = []
                        source_filter = st.multiselect("📡 Source", available_sources, default=[])
                    with col_f3:
                        max_results = st.slider("📄 Max results", 5, 50, 20)
                    
                    if search_query:
                        must_clauses = [
                            {
                                "multi_match": {
                                    "query": search_query,
                                    "fields": ["title^3", "description^2", "content_text"],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO",
                                }
                            }
                        ]
                        filter_clauses = []
                        
                        lang_map = {"English": "en", "French": "fr", "Spanish": "es"}
                        if lang_filter != "All":
                            filter_clauses.append({"term": {"source_language": lang_map[lang_filter]}})
                        if league_filter:
                            filter_clauses.append({"terms": {"leagues_mentioned": league_filter}})
                        if source_filter:
                            filter_clauses.append({"terms": {"source_name": source_filter}})
                        
                        body = {
                            "query": {
                                "bool": {
                                    "must": must_clauses,
                                    "filter": filter_clauses,
                                }
                            },
                            "size": max_results,
                            "sort": [{"_score": "desc"}, {"published_at": "desc"}],
                            "highlight": {
                                "fields": {
                                    "title": {"number_of_fragments": 0},
                                    "description": {"fragment_size": 250, "number_of_fragments": 2},
                                },
                                "pre_tags": ["**"],
                                "post_tags": ["**"],
                            },
                        }
                        
                        try:
                            results = es.search(index="football_news", body=body)
                            hits = results["hits"]["hits"]
                            total = results["hits"]["total"]["value"]
                            
                            st.markdown(f"### 📋 {total} result{'s' if total != 1 else ''} for *\"{search_query}\"*")
                            
                            if not hits:
                                st.info("No articles found. Try different keywords or broader filters.")
                            
                            for hit in hits:
                                src = hit["_source"]
                                score = hit["_score"]
                                highlights = hit.get("highlight", {})
                                
                                # Use highlighted title if available
                                title = highlights.get("title", [src.get("title", "Untitled")])[0]
                                desc = highlights.get("description", [src.get("description", "")])[0]
                                try:
                                    pub_date = datetime.fromisoformat(src.get("published_at", "")).strftime("%d %b %Y %H:%M")
                                except Exception:
                                    pub_date = src.get("published_at", "Unknown")
                                
                                teams = src.get("teams_mentioned", [])
                                leagues = src.get("leagues_mentioned", [])
                                link = src.get("link", "#")
                                source_name = src.get("source_name", "Unknown")
                                lang = src.get("source_language", "")
                                lang_flag = {"en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸"}.get(lang, "🌐")
                                
                                with st.container():
                                    st.markdown(f"#### [{title}]({link})")
                                    st.markdown(f"{desc}" if desc else "")
                                    
                                    meta_parts = [f"{lang_flag} **{source_name}**", f"📅 {pub_date}", f"🎯 Score: {score:.1f}"]
                                    if teams:
                                        meta_parts.append(f"⚽ {', '.join(teams[:5])}")
                                    if leagues:
                                        meta_parts.append(f"🏆 {', '.join(leagues)}")
                                    
                                    st.caption(" | ".join(meta_parts))
                                    st.markdown("---")
                        
                        except Exception as e:
                            st.error(f"Search error: {e}")
                    
                    else:
                        st.markdown("### 📊 News Index Overview")
                        
                        try:
                            stats_body = {
                                "size": 0,
                                "aggs": {
                                    "by_source": {"terms": {"field": "source_name", "size": 20}},
                                    "by_language": {"terms": {"field": "source_language", "size": 10}},
                                    "by_team": {"terms": {"field": "teams_mentioned", "size": 15}},
                                    "by_league": {"terms": {"field": "leagues_mentioned", "size": 10}},
                                },
                            }
                            stats_result = es.search(index="football_news", body=stats_body)
                            aggs = stats_result["aggregations"]
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Articles by source
                                src_data = pd.DataFrame(
                                    [{"Source": b["key"], "Articles": b["doc_count"]} for b in aggs["by_source"]["buckets"]]
                                )
                                if not src_data.empty:
                                    fig_src = px.bar(src_data, x="Articles", y="Source", orientation="h",
                                                     title="Articles by Source", color="Articles",
                                                     color_continuous_scale="blues")
                                    fig_src.update_layout(height=350, showlegend=False)
                                    st.plotly_chart(fig_src, use_container_width=True)
                            
                            with col2:
                                # Most mentioned teams
                                team_data = pd.DataFrame(
                                    [{"Team": b["key"], "Mentions": b["doc_count"]} for b in aggs["by_team"]["buckets"]]
                                )
                                if not team_data.empty:
                                    fig_team = px.bar(team_data, x="Mentions", y="Team", orientation="h",
                                                      title="Most Mentioned Teams", color="Mentions",
                                                      color_continuous_scale="greens")
                                    fig_team.update_layout(height=350, showlegend=False)
                                    st.plotly_chart(fig_team, use_container_width=True)
                            
                            # Language distribution
                            lang_data = pd.DataFrame(
                                [{"Language": {"en": "English 🇬🇧", "fr": "French 🇫🇷", "es": "Spanish 🇪🇸"}.get(b["key"], b["key"]),
                                  "Count": b["doc_count"]} for b in aggs["by_language"]["buckets"]]
                            )
                            if not lang_data.empty:
                                fig_lang = px.pie(lang_data, values="Count", names="Language",
                                                  title="Articles by Language")
                                fig_lang.update_layout(height=300)
                                st.plotly_chart(fig_lang, use_container_width=True)
                        
                        except Exception as e:
                            st.warning(f"Could not load stats: {e}")
                        
                        # Show latest articles
                        st.markdown("### 📄 Latest Articles")
                        try:
                            latest = es.search(
                                index="football_news",
                                body={"query": {"match_all": {}}, "size": 10, "sort": [{"published_at": "desc"}]},
                            )
                            for hit in latest["hits"]["hits"]:
                                src = hit["_source"]
                                title = src.get("title", "Untitled")
                                link = src.get("link", "#")
                                source_name = src.get("source_name", "Unknown")
                                lang = src.get("source_language", "")
                                lang_flag = {"en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸"}.get(lang, "🌐")
                                teams = src.get("teams_mentioned", [])
                                try:
                                    pub_date = datetime.fromisoformat(src.get("published_at", "")).strftime("%d %b %Y")
                                except Exception:
                                    pub_date = ""
                                
                                team_tags = f" — ⚽ {', '.join(teams[:3])}" if teams else ""
                                st.markdown(f"- {lang_flag} [{title}]({link}) — *{source_name}* ({pub_date}){team_tags}")
                        
                        except Exception as e:
                            st.warning(f"Could not load latest articles: {e}")

    # Footer
    st.markdown("---")
    st.markdown(
        f"<p style='text-align: center; color: #666;'>"
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Data source: Football-Data.org API + RSS News Feeds"
        f"</p>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
