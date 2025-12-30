"""
Football Statistics Dashboard - Streamlit App
Production-ready dashboard for football analytics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
from datetime import datetime

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
    return pd.read_sql(query, engine)


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


def get_recent_matches(limit=20):
    """Get recent matches"""
    query = f"""
    SELECT 
        match_date,
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
            ["📊 Overview", "🏆 Competition Analysis", "👥 Team Performance", "📈 Match Analysis", "🔍 Team Deep Dive"],
            label_visibility="collapsed"
        )
        
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
        recent = get_recent_matches(10)
        
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
            recent_display = recent.copy()
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
        
        # Filter by competition
        selected_comp = st.selectbox(
            "Select Competition",
            team_perf['competition_name'].unique()
        )
        
        filtered_teams = team_perf[team_perf['competition_name'] == selected_comp].copy()
        
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
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<p style='text-align: center; color: #666;'>"
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Data source: Football-Data.org API"
        f"</p>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
