import streamlit as st
import folium
from streamlit_folium import folium_static

st.title("TEST SIMPLE")

# Créer une carte simple
m = folium.Map(location=[6.5, 1.2], zoom_start=7)

# Ajouter un marqueur
folium.Marker([6.5, 1.2], popup="Test").add_to(m)

# Afficher la carte
folium_static(m, width=800, height=500)

st.success("Si vous voyez la carte, le problème vient d'ailleurs")