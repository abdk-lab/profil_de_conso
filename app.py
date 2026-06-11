import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import linprog
import plotly.graph_objects as go
import io

st.set_page_config(page_title="Industrial Load Optimizer", layout="wide")

# Style CSS pour faire des belles cartes KPI
st.markdown("""
    <style>
    .kpi-card {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center;
    }
    .kpi-title { color: #888888; font-size: 13px; font-weight: 600; text-transform: uppercase; }
    .kpi-value { font-size: 28px; font-weight: bold; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("🏭 Dashboard d'Optimisation de Courbe de Charge (Horizon 2028)")
st.caption("Ajustez vos paramètres industriels dans la barre latérale pour mettre à jour le tableau de bord.")

# BARRE LATÉRALE
st.sidebar.header("🎛️ Configuration Usine")

# Lecture automatique du fichier prix.csv
try:
    # On tente d'abord de lire avec un séparateur point-virgule (Excel français)
    try:
        df_complet = pd.read_csv("prix.csv", sep=";")
        if "Prix" not in df_complet.columns:
            raise ValueError
    except:
        # Si ça échoue, on tente le séparateur virgule standard
        df_complet = pd.read_csv("prix.csv", sep=",")

    df_complet['Date'] = pd.to_datetime(df_complet['Date'])
    df_ref = df_complet[df_complet['Annee'] == 2024].sort_values(by=['Date', 'Heure']).reset_index(drop=True)
    prices_ref = df_ref['Prix'].values
    N_hours = len(prices_ref)
    st.sidebar.success(f"✅ Base de prix 2024 chargée ({N_hours} heures)")
except Exception as e:
    st.sidebar.error("❌ Erreur de lecture du fichier 'prix.csv'. Vérifiez sa structure.")
    st.stop()

# Curseurs de réglages
slider_vol = st.sidebar.slider("Volume annuel cible (GWh) :", min_value=1.0, max_value=120.0, value=25.0, step=1.0)
slider_pmax = st.sidebar.slider("Puissance Max Usine (MW) :", min_value=1.0, max_value=25.0, value=8.0, step=0.5)
slider_talon = st.sidebar.slider("Talon Permanent (MW) :", min_value=0.0, max_value=5.0, value=0.5, step=0.1)

vol_mwh = slider_vol * 1000

# Vérifications de sécurité
if vol_mwh < slider_talon * N_hours:
    st.error("❌ Erreur : Volume annuel trop faible pour maintenir le talon permanent !")
elif vol_mwh > slider_pmax * N_hours:
    st.error("❌ Erreur : Volume supérieur à la capacité maximale de l'usine (Pmax) !")
else:
    # Moteur d'optimisation
    bounds = [(slider_talon, slider_pmax) for _ in range(N_hours)]
    res = linprog(prices_ref, A_eq=[np.ones(N_hours)], b_eq=[vol_mwh], bounds=bounds, method='highs')
    
    if res.success:
        conso_mw = res.x
        facture_totale = np.sum(conso_mw * prices_ref)
        prix_moyen_optimise = facture_totale / vol_mwh
        prix_moyen_marche = prices_ref.mean()
        economie = (prix_moyen_marche - prix_moyen_optimise) * vol_mwh
        
        # Section 1 : Les 4 Cartes KPI
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="kpi-card" style="border-top:5px solid #2196F3;"><div class="kpi-title">Volume</div><div class="kpi-value" style="color:#2196F3;">{slider_vol:.0f} GWh</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="kpi-card" style="border-top:5px solid #E91E63;"><div class="kpi-title">Facture Énergie</div><div class="kpi-value" style="color:#E91E63;">{facture_totale:,.0f} €</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="kpi-card" style="border-top:5px solid #4CAF50;"><div class="kpi-title">Votre Prix Moyen</div><div class="kpi-value" style="color:#4CAF50;">{prix_moyen_optimise:.2f} €</div></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="kpi-card" style="border-top:5px solid #00BCD4;"><div class="kpi-title">Économie Réalisée</div><div class="kpi-value" style="color:#00BCD4;">{economie:,.0f} €</div></div>', unsafe_allow_html=True)
            
        st.write("<br>", unsafe_allow_html=True)
        
        # Section 2 : Les Graphiques
        g1, g2 = st.columns(2)
        
        with g1:
            df_ref['Conso_MW'] = conso_mw
            # Sélection de mois pour le graphique d'illustration (on vérifie s'ils existent)
            mois_dispo = df_ref['Mois'].unique()
            mois_ete = [m for m in ['April', 'May', 'June', 'July', 'August', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août'] if m in mois_dispo]
            if len(mois_ete) == 0: mois_ete = [mois_dispo[0]]
            
            df_h = df_ref[df_ref['Mois'].isin(mois_ete)].groupby('Heure').mean(numeric_only=True).reset_index()
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(x=df_h['Heure'], y=df_h['Conso_MW'], name="Conso Usine (MW)", yaxis="y1", marker_color="#4CAF50", opacity=0.7))
            fig1.add_trace(go.Scatter(x=df_h['Heure'], y=df_h['Prix'], name="Prix (€/MWh)", yaxis="y2", line=dict(color="#2196F3", width=2.5)))
            fig1.update_layout(
                title="<b>Profil horaire moyen (Période sélectionnée)</b>",
                yaxis=dict(title="Puissance Usine (MW)", titlefont=dict(color="#4CAF50")),
                yaxis2=dict(title="Prix Spot (€/MWh)", titlefont=dict(color="#2196F3"), overlaying="y", side="right"),
                template="plotly_white", legend=dict(x=0.01, y=0.99)
            )
            st.plotly_chart(fig1, use_container_width=True)
            
        with g2:
            df_ref['Mois_Num'] = df_ref['Date'].dt.month
            df_m = df_ref.groupby(['Mois_Num', 'Mois'])['Conso_MW'].sum().reset_index().sort_values('Mois_Num')
            fig2 = go.Bar(x=df_m['Mois'], y=df_m['Conso_MW']/1000, marker_color="#9C27B0", opacity=0.7)
            fig_layout = go.Layout(title="<b>Volume d'énergie consommé par mois (GWh)</b>", template="plotly_white")
            st.plotly_chart(go.Figure(data=[fig2], layout=fig_layout), use_container_width=True)
            
        # Section 3 : Export
        df_export = df_ref.copy()
        df_export['Date_2028'] = df_export['Date'].apply(lambda x: x.replace(year=2028))
        csv_buf = io.StringIO()
        df_export[['Date_2028', 'Heure', 'Mois', 'Prix', 'Conso_MW']].to_csv(csv_buf, index=False, sep=';')
        
        st.sidebar.markdown("---")
        st.sidebar.download_button("📥 Exporter la courbe (.CSV)", data=csv_buf.getvalue(), file_name="courbe_charge_2028.csv", mime="text/csv")
